#!/usr/bin/env python3
"""Seeded DEEP tasks: authored signature/type changes too wide and too
context-dependent for one text substitution (add a required parameter,
change a return type, move a type to another package).

Each recipe below makes the gold change mechanically in a fresh checkout:
declarations by pattern, call sites from the compiler's own error list
(Java/Go/TS) or by a resolved-name scan (Python), repeated until the build
is clean. The result is written as a gold patch plus a build_wide.py spec
(site_mode="shapes"); build_wide then measures base/gold shape counts, picks
pass_to_pass, and proves gold resolves, the empty patch fails and a partial
patch (gold minus a few sites, also made here) fails.

usage:
  build_deep.py gold <task-id>      # make gold + partial patches and the spec
  build_deep.py build <task-id>     # gold, then build_wide (writes tasks/e2e/<id>.json)
  build_deep.py list
Work dirs live under $DEEP_WORK (default ~/.cache/deep-tasks).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

H = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(H / "build"))
sys.path.insert(0, str(H / "scoring"))
import deep_edit as de  # noqa: E402

WORK = Path(os.environ.get("DEEP_WORK", Path.home() / ".cache" / "deep-tasks"))
CORPUS = Path.home() / "gvg-corpus"
M2 = Path.home() / ".m2-eval"

RECIPES: dict[str, dict] = {}


def recipe(**meta):
    def deco(fn):
        RECIPES[meta["instance_id"]] = dict(meta, make=fn)
        return fn
    return deco


# ---------------------------------------------------------------- checkout

def checkout(repo: Path, base: str, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    de.git("clone", "--local", "--no-checkout", "--quiet", str(repo), str(dest))
    de.git("-C", str(dest), "checkout", "--detach", "-f", "-q", base)
    return dest


def diff_of(wt: Path, exclude=("pom.xml",)) -> str:
    de.git("-C", str(wt), "add", "-A")
    ex = [f":(exclude){e}" for e in exclude]
    return de.git("-C", str(wt), "diff", "--cached", "--", ".", *ex)


def read(wt: Path, f: str) -> str:
    return (wt / f).read_text()


def write(wt: Path, f: str, text: str) -> None:
    (wt / f).write_text(text)


# ---------------------------------------------------------------- java

JAVA_ERR = re.compile(r"^\[ERROR\] /w/(\S+\.java):\[(\d+),(\d+)\] (.*)$", re.M)


def java_compile(wt: Path, image: str = "maven:3.9-eclipse-temurin-17") -> tuple[bool, list, str]:
    """mvn test-compile in docker; (ok, [(file, line, col, msg)], tail)."""
    import java_eval
    java_eval._pin_snapshot_parent(wt)
    cmd = "set -o pipefail; mvn -q -nsu test-compile 2>&1 | tail -400"
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w", "-v", f"{M2}:/root/.m2",
                        "-w", "/w", image, "bash", "-lc", cmd],
                       capture_output=True, text=True, timeout=3600)
    out = r.stdout + r.stderr
    errs = [(m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)) for m in JAVA_ERR.finditer(out)]
    # de-dup (maven prints the list twice)
    seen, uniq = set(), []
    for e in errs:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return r.returncode == 0, uniq, out[-3000:]


def line_offset(text: str, line: int, col: int = 1) -> int:
    off = 0
    for _ in range(line - 1):
        off = text.index("\n", off) + 1
    return off + col - 1


def calls_near(wt: Path, f: str, name: str, line: int) -> list:
    """Calls/decls of name whose name starts on the given line or (javac
    points at the receiver's dot) the line after."""
    raw = read(wt, f)
    m = de.mask(raw, f)
    out = []
    for c in de.find_calls(raw, m, name):
        ln = raw.count("\n", 0, c.name_start) + 1
        if ln in (line, line + 1):
            out.append(c)
    return out


def ensure_java_import(text: str, fqn: str) -> str:
    simple = fqn.rsplit(".", 1)[1]
    pkg = re.search(r"^package\s+([\w.]+);", text, re.M)
    if pkg and pkg.group(1) == fqn.rsplit(".", 1)[0]:
        return text
    if re.search(rf"^import\s+{re.escape(fqn)};", text, re.M):
        return text
    if re.search(rf"^import\s+{re.escape(fqn.rsplit('.', 1)[0])}\.\*;", text, re.M):
        return text
    if re.search(rf"^import\s+[\w.]+\.{simple};", text, re.M):
        raise RuntimeError(f"conflicting import for {simple}")
    imps = list(re.finditer(r"^import\s+(static\s+)?[\w.*]+;\s*$", text, re.M))
    non_static = [m for m in imps if not m.group(1)]
    anchor = (non_static or imps)
    if anchor:
        pos = anchor[-1].end()
        return text[:pos] + f"\nimport {fqn};" + text[pos:]
    pkg_m = re.search(r"^package\s+[\w.]+;\s*$", text, re.M)
    pos = pkg_m.end()
    return text[:pos] + f"\n\nimport {fqn};" + text[pos:]


def enclosing_java_params(raw: str, masked: str, pos: int) -> str:
    """The parameter list text of the method enclosing pos (best effort:
    the nearest preceding `name(...) [throws ...] {` whose body contains pos)."""
    best = ""
    for m in re.finditer(r"\b([\w$]+)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*(?:throws[\w\s.,]+)?\{", masked[:pos]):
        if m.group(1) in ("if", "for", "while", "switch", "catch", "synchronized", "try", "return", "new"):
            continue
        prev = de.prev_token(masked, m.start(1))
        if not (prev and (prev[-1].isalnum() or prev[-1] in "_$>]")) or prev in ("new", "return", "else", "throw"):
            continue
        # body brace balance from the "{" to pos must stay > 0
        depth = 0
        ok = True
        for ch in masked[m.end() - 1:pos]:
            depth += ch == "{"
            depth -= ch == "}"
            if depth <= 0:
                ok = False
                break
        if ok:
            best = raw[m.start(2):m.end(2)]
    return best


# ---------------------------------------------------------------- driver

def task_dir(tid: str) -> Path:
    return WORK / tid


def make_gold(tid: str) -> dict:
    r = RECIPES[tid]
    d = task_dir(tid)
    d.mkdir(parents=True, exist_ok=True)
    wt = checkout(r["repo_dir"], r["base_commit"], d / "wt")
    info = r["make"](wt) or {}
    gold = diff_of(wt)
    (d / "gold.patch").write_text(gold)
    partial = make_partial(wt, r, gold, info)
    (d / "partial.patch").write_text(partial)
    spec = {k: r[k] for k in ("instance_id", "repo", "lang", "base_commit", "instruction", "shapes")}
    spec.update(source="seeded", site_mode="shapes", gold_patch=str(d / "gold.patch"),
                partial_patch=str(d / "partial.patch"), gold_tool=r["gold_tool"],
                change=r["change"], notes=r.get("notes", "") + (" " + info.get("notes", "") if info.get("notes") else ""))
    for k in ("test_classes", "test_functions", "test_modules", "typecheck_cmd", "pytest_args"):
        if k in r:
            spec[k] = r[k]
    (d / "spec.json").write_text(json.dumps(spec, indent=1))
    return spec


def make_partial(wt: Path, r: dict, gold: str, info: dict) -> str:
    """Gold minus the hunks the recipe names (info["partial_drop"] = list of
    (file, substring-in-hunk)), or by default the last hunk of the two
    gold files with the most hunks -- a call/override update the agent
    'forgot'. Built by reverting those hunks in the gold tree."""
    files = re.split(r"(?m)^(?=diff --git )", gold)
    files = [f for f in files if f.strip()]
    drops = info.get("partial_drop")
    out = []
    dropped = []
    if drops is None:
        # files with >= 2 hunks, not the declaration file(s)
        cand = []
        for fd in files:
            name = re.search(r"^\+\+\+ b/(\S+)", fd, re.M)
            if not name:
                continue
            n = len(re.findall(r"(?m)^@@", fd))
            if n >= 2 and name.group(1) not in r.get("decl_files", []):
                cand.append((n, name.group(1)))
        cand.sort(reverse=True)
        drops = [(f, None) for _, f in cand[:2]]
        if not drops:
            drops = [(re.search(r"^\+\+\+ b/(\S+)", files[-1], re.M).group(1), None)]
    dropmap = {}
    for f, sub in drops:
        dropmap.setdefault(f, []).append(sub)
    for fd in files:
        name = re.search(r"^\+\+\+ b/(\S+)", fd, re.M)
        fname = name.group(1) if name else None
        if fname not in dropmap:
            out.append(fd)
            continue
        head, *hunks = re.split(r"(?m)^(?=@@)", fd)
        keep = []
        subs = dropmap[fname]
        for h in hunks:
            hit = None
            for s in subs:
                if (s is None and h is hunks[-1]) or (s is not None and s in h):
                    hit = s
                    break
            if hit is not None or (None in subs and h is hunks[-1]):
                dropped.append(f"{fname}: {h.splitlines()[0]}")
                continue
            keep.append(h)
        if keep:
            out.append(head + "".join(keep))
    info.setdefault("dropped", dropped)
    (task_dir(r["instance_id"]) / "partial.dropped.txt").write_text("\n".join(dropped))
    return "".join(out)


def build(tid: str) -> None:
    spec = make_gold(tid) if not (task_dir(tid) / "spec.json").exists() or "--regold" in sys.argv \
        else json.loads((task_dir(tid) / "spec.json").read_text())
    import build_wide
    t = build_wide.build(dict(spec))
    print(json.dumps({k: t.get(k) for k in ("instance_id", "gold_sites", "gold_site_files", "gold_files",
                                            "gold_test_outcomes", "validation")}, indent=1)[:3000])


def load_recipes() -> None:
    """Recipes live in deep_recipes_<lang>.py and deephard_recipes_<lang>.py
    (high-turn variants), which register via @recipe."""
    for mod in ("deep_recipes_java", "deep_recipes_go", "deep_recipes_ts", "deep_recipes_py",
                "deephard_recipes_java", "deephard_recipes_go", "deephard_recipes_ts", "deephard_recipes_py"):
        try:
            __import__(mod)
        except ModuleNotFoundError as e:
            if e.name != mod:
                raise


def main(argv: list[str]) -> None:
    load_recipes()
    cmd = argv[1]
    if cmd == "list":
        for k, v in RECIPES.items():
            print(k, v["change"])
    elif cmd == "gold":
        print(json.dumps(make_gold(argv[2]), indent=1)[:2000])
    elif cmd == "build":
        build(argv[2])


if __name__ == "__main__":
    import build_deep  # one module instance: recipes register into build_deep.RECIPES
    build_deep.main(sys.argv)
