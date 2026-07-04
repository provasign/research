"""Change-impact oracle for a Python method signature change (Jedi-resolved).

The Python sibling of java-oracle/Oracle.java and ts-oracle/oracle.mjs: given
Type.method, emit every site that must change if that method's signature
changes --

  1. the declaration + every override in the subtype closure (the family), and
  2. every call site that Jedi resolves to a family member, attributed to its
     enclosing function/method.

Family closure is AST-based (transitive subclasses defining the method).
Caller resolution is Jedi's (type inference, project-wide), NOT name matching:
a call to an unrelated same-named method on a different type is not included --
Jedi resolves it elsewhere and it is dropped. Ground truth is production
sources only (the package dir passed as --src, tests excluded).

Site format is "<repo-relative-path>:<enclosing-def-name>" (harness Site form).

Usage:
  python oracle.py --src <pkgdir> --repo <root> --target 'Console.print' --out out.json
  python oracle.py --src <pkgdir> --repo <root> --index idx.json   # line->name index
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import jedi


def py_files(src: Path) -> list[Path]:
    out = []
    for p in src.rglob("*.py"):
        rel = p.as_posix()
        if "/test" in rel or "/tests/" in rel or p.name.startswith("test_"):
            continue
        out.append(p)
    return out


def enclosing_def(tree: ast.Module, line: int) -> str:
    """Name of the innermost def/class enclosing a 1-based line."""
    best_name = "<module>"
    best_span = 10**9
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= line <= end:
                span = end - node.lineno
                if span < best_span:
                    best_span, best_name = span, node.name
    return best_name


def build_class_index(files: list[Path]) -> tuple[dict, dict]:
    """Return (class_defs, subclasses).

    class_defs: simple class name -> list of (file, ast.ClassDef).
    subclasses: simple base name -> set of simple subclass names (direct).
    """
    class_defs: dict[str, list] = {}
    subclasses: dict[str, set] = {}
    for f in files:
        try:
            tree = ast.parse(f.read_text(), filename=str(f))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_defs.setdefault(node.name, []).append((f, node))
                for base in node.bases:
                    bname = base.id if isinstance(base, ast.Name) else (
                        base.attr if isinstance(base, ast.Attribute) else None)
                    if bname:
                        subclasses.setdefault(bname, set()).add(node.name)
    return class_defs, subclasses


def method_in_class(cls: ast.ClassDef, method: str) -> ast.stmt | None:
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method:
            return item
    return None


def transitive_subclasses(root: str, subclasses: dict) -> set[str]:
    seen, frontier = set(), [root]
    while frontier:
        cur = frontier.pop()
        for sub in subclasses.get(cur, ()):
            if sub not in seen:
                seen.add(sub)
                frontier.append(sub)
    return seen


def index_mode(src: Path, repo: Path, out: Path) -> None:
    idx: dict[str, list] = {}
    for f in py_files(src):
        try:
            tree = ast.parse(f.read_text(), filename=str(f))
        except SyntaxError:
            continue
        spans = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno)
                spans.append([node.lineno, end, node.name])
        if spans:
            idx[f.relative_to(repo).as_posix()] = spans
    out.write_text(json.dumps(idx))
    print(f"[index] files={len(idx)} -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="package dir to scan")
    ap.add_argument("--repo", required=True, help="corpus root (for relpaths)")
    ap.add_argument("--target", help="Type.method")
    ap.add_argument("--out", help="output JSON")
    ap.add_argument("--index", help="write line->name index here instead")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    repo = Path(args.repo).resolve()
    if args.index:
        index_mode(src, repo, Path(args.index))
        return

    type_name, method = args.target.rsplit(".", 1)
    files = py_files(src)
    project = jedi.Project(str(repo))
    rel = lambda p: Path(p).resolve().relative_to(repo).as_posix()

    class_defs, subclasses = build_class_index(files)
    if type_name not in class_defs:
        raise SystemExit(f"target class {type_name!r} not found under {src}")

    # Family: declaration + every transitive subclass that defines `method`.
    fam_classes = [type_name] + sorted(transitive_subclasses(type_name, subclasses))
    family_defs = []  # (file, ast def node)
    for cname in fam_classes:
        for f, cls in class_defs.get(cname, []):
            m = method_in_class(cls, method)
            if m is not None:
                family_defs.append((f, m))
    if not family_defs:
        raise SystemExit(f"no class in the {type_name} hierarchy defines {method!r}")

    family_sites, caller_sites = set(), set()
    trees: dict[Path, ast.Module] = {}

    def tree_of(f: Path) -> ast.Module:
        if f not in trees:
            trees[f] = ast.parse(f.read_text(), filename=str(f))
        return trees[f]

    for f, mnode in family_defs:
        family_sites.add(f"{rel(f)}:{method}")

    # Callers: Jedi project-wide references to each family def, in call
    # position, attributed to their enclosing def. Jedi resolves the receiver
    # type, so same-named methods on unrelated classes are excluded.
    for f, mnode in family_defs:
        col = mnode.col_offset + len("async def " if isinstance(mnode, ast.AsyncFunctionDef) else "def ")
        try:
            script = jedi.Script(path=str(f), project=project)
            refs = script.get_references(mnode.lineno, col, include_builtins=False, scope="project")
        except Exception:
            continue
        for r in refs:
            if r.module_path is None:
                continue
            rp = Path(r.module_path)
            rrel = rp.as_posix()
            if "/test" in rrel or rp.name.startswith("test_"):
                continue
            try:
                rp.resolve().relative_to(repo)
            except ValueError:
                continue  # outside repo (stdlib / site-packages)
            # Exclude the definition sites themselves (def name / class body).
            try:
                line_txt = rp.read_text().splitlines()[r.line - 1]
            except (OSError, IndexError):
                continue
            after = line_txt[r.column + len(method):].lstrip()
            if not after.startswith("("):
                continue  # not a call
            if line_txt[:r.column].rstrip().endswith("def"):
                continue  # a definition, not a call
            try:
                site = f"{rel(rp)}:{enclosing_def(tree_of(rp), r.line)}"
            except (OSError, SyntaxError):
                continue
            if site not in family_sites:
                caller_sites.add(site)

    gt = sorted(family_sites | caller_sites)
    result = {
        "target": args.target,
        "family": sorted(family_sites),
        "callers": sorted(caller_sites),
        "ground_truth": gt,
        "stats": {"family": len(family_sites), "resolved_call_hits": len(caller_sites),
                  "gt_sites": len(gt), "family_classes": len(family_defs)},
    }
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["stats"]))


if __name__ == "__main__":
    main()
