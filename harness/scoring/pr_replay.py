#!/usr/bin/env python3
"""Phase-1 PR-replay: prove the engine's change-set matches what real engineers
merged, on real, outcome-blind-sampled PRs — no LLM, no hand-built oracle.

For each merged PR of a real project:
  1. before-state = the merge commit's first parent (what the change applied to).
  2. classify (MECHANICAL, outcome-blind): is a method signature changed or a
     method renamed, touching production code? If so record the target(s)
     Type.method and the ground-truth set (every production method the diff
     touched, mapped to its enclosing method in the before-state via grove's
     own line->method index, so GT is scored in the same coordinates the engine
     reports).
  3. reject ill-posed: a target overriding an external (JDK/dependency) contract
     — the engine self-reports this (completeness=project-local + overridesExternal).
  4. score: union change_impact over the target(s) vs GT (recall/precision).

The two independent oracles here are the merged human diff (GT) and, later in
Phase 2, the compiler. This stage uses only the diff, so it is $0.

Outcome-blind discipline: --limit takes the most recent N merged PRs in order;
the classifier filter is fixed up front. Do NOT hand-pick PRs.

Usage:
  python pr_replay.py --repo ~/gvg-corpus/netty --owner netty --name netty \
      --limit 200 --prism ~/bin/prism --out runs/pr-replay-netty.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# --- Java lexical helpers ------------------------------------------------

# A method/constructor declaration line: modifiers, a return type (or none for
# ctors), the name, and an open paren. Excludes control-flow keywords that also
# match `name(` (if/for/while/switch/catch/synchronized-block).
_CTRL = {"if", "for", "while", "switch", "catch", "synchronized", "return",
         "new", "assert", "throw", "super", "this", "else", "do"}
JAVA_DECL_RE = re.compile(
    r"^\s*(?:@\w+\s*)*"                       # leading annotations
    r"(?:(?:public|private|protected|static|final|abstract|synchronized|"
    r"native|default|strictfp)\s+)*"          # modifiers
    r"(?:<[^>]*>\s*)?"                          # generic type params
    r"(?:[\w.$]+(?:<[^;{}=]*>)?(?:\[\])*\s+)?"  # return type (optional: ctor)
    r"([A-Za-z_$][\w$]*)\s*\("                  # NAME (
)
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Generated / mock churn: never hand-written change sites (the codegen trap).
GEN_RE = re.compile(r"generated|/gen/|\.gen\.|_generated|autovalue|\bmock", re.I)


def method_name(line: str) -> str | None:
    m = JAVA_DECL_RE.match(line)
    if not m:
        return None
    name = m.group(1)
    if name in _CTRL:
        return None
    # The single most important guard: a qualified CALL (`encoder.encode(buf)`)
    # otherwise parses as `<rettype=encoder.> <name=encode>(` and gets counted
    # as a declaration — so feature PRs that only change call ARGUMENTS were
    # misflagged as signature changes. If the matched name is immediately
    # preceded by `.` it is a member access / call, not a declaration.
    if line[:m.start(1)].rstrip().endswith("."):
        return None
    head = line[:line.index("(")]
    # Real decls carry a return type or modifier token before the name (i.e.
    # at least two whitespace-separated tokens, or a leading modifier); a bare
    # `foo(...)` call statement has just the name. Constructors are the one
    # exception — the name matches the enclosing class — but those still have a
    # visibility modifier in practice, so requiring a preceding token is safe.
    if "=" in head or "return " in line or len(head.split()) < 2:
        return None
    return name


def git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args],
                          capture_output=True, text=True).stdout


def prod_java(path: str) -> bool:
    return (path.endswith(".java") and "/test/" not in path
            and "/src/test/" not in path and not GEN_RE.search(path))


# --- stage 1: mine merged PRs -------------------------------------------

def mine(owner: str, name: str, limit: int) -> list[dict]:
    """Most-recent `limit` merged PRs, in order (outcome-blind)."""
    prs, page = [], 1
    while len(prs) < limit:
        raw = subprocess.run(
            ["gh", "api",
             f"repos/{owner}/{name}/pulls?state=closed&per_page=100&page={page}"
             "&sort=updated&direction=desc"],
            capture_output=True, text=True).stdout
        batch = json.loads(raw) if raw.strip() else []
        if not batch:
            break
        for p in batch:
            if p.get("merged_at") and p.get("merge_commit_sha"):
                prs.append({"num": p["number"], "title": p["title"] or "",
                            "merge": p["merge_commit_sha"]})
                if len(prs) >= limit:
                    break
        page += 1
    return prs


# --- stage 2: classify (mechanical, outcome-blind) ----------------------

def enclosing_type(lines: list[str], idx: int) -> str | None:
    """Nearest `class|interface|enum|record NAME` at or above line idx."""
    decl = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
    for i in range(idx, -1, -1):
        m = decl.search(lines[i])
        if m:
            return m.group(1)
    return None


def classify(repo: str, merge: str, title: str = "") -> dict | None:
    """Return {targets, changed_files, base} if the PR is change-impact-shaped:
    a method signature changed or a method renamed in production code, with a
    blast radius beyond one file. Else None. Mechanical + outcome-blind."""
    base = merge + "^"
    if not git(repo, "rev-parse", "--verify", base).strip():
        return None
    # Exclude aggregate merge PRs: a real merge commit (2+ parents) or a
    # "Merge branches/forks" roll-up mixes many unrelated changes, so its diff
    # is never a single coherent task.
    if title.lower().startswith("merge ") or \
       len(git(repo, "rev-list", "--parents", "-n", "1", merge).split()) > 2:
        return None
    diff = git(repo, "diff", "--unified=0", base, merge, "--", "*.java")
    if not diff:
        return None

    cur_file, base_ln = None, 0
    removed_decls: dict[str, set[str]] = {}   # method name -> set(param-sigs) removed
    added_decls: dict[str, set[str]] = {}
    touched_prod = set()                       # files with any prod change
    base_src_cache: dict[str, list[str]] = {}
    target_files: dict[str, str] = {}          # method name -> a base file it decl'd in

    def base_lines(path: str) -> list[str]:
        if path not in base_src_cache:
            base_src_cache[path] = git(repo, "show", f"{base}:{path}").splitlines()
        return base_src_cache[path]

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:]
            continue
        if line.startswith("--- "):
            continue
        h = HUNK_RE.match(line)
        if h:
            base_ln = int(h.group(1))
            continue
        if not cur_file or not prod_java(cur_file):
            continue
        if line.startswith("-") and not line.startswith("---"):
            touched_prod.add(cur_file)
            nm = method_name(line[1:])
            if nm:
                removed_decls.setdefault(nm, set()).add(_paramsig(line[1:]))
                # record enclosing type from the base source at this line
                bl = base_lines(cur_file)
                if base_ln - 1 < len(bl):
                    t = enclosing_type(bl, min(base_ln - 1, len(bl) - 1))
                    if t:
                        target_files[nm] = f"{t}.{nm}"
        elif line.startswith("+") and not line.startswith("+++"):
            touched_prod.add(cur_file)
            nm = method_name(line[1:])
            if nm:
                added_decls.setdefault(nm, set()).add(_paramsig(line[1:]))

    # Signature change: same method name declared on both sides with a DIFFERENT
    # parameter signature.
    targets = []
    for nm, rsigs in removed_decls.items():
        asigs = added_decls.get(nm)
        if asigs and rsigs != asigs and nm in target_files:
            targets.append(target_files[nm])

    if not targets or len(touched_prod) < 2:
        return None
    # Feature-vs-refactor gate: a signature-change REFACTOR threads a changed
    # signature through existing code; a FEATURE adds net-new methods/classes
    # and only incidentally touches a signature. When a PR introduces many
    # net-new method declarations, its diff is dominated by feature work whose
    # changed methods are NOT the target's mechanical blast radius, so the
    # merged diff is not clean ground truth for change-impact. Exclude it.
    new_methods = set(added_decls) - set(removed_decls)
    if len(new_methods) > 2:
        return None
    # A focused signature change touches the declaration plus its callers, not a
    # sprawling set of unrelated files. Cap the blast radius (very large diffs
    # are features/rewrites, not a single coherent change-impact task).
    if len(touched_prod) > 12:
        return None
    return {"targets": sorted(set(targets)), "base": base,
            "changed_files": sorted(touched_prod)}


def _paramsig(decl_line: str) -> str:
    """Crude parameter signature: the text inside the first (...)."""
    i = decl_line.find("(")
    if i < 0:
        return ""
    depth, out = 0, []
    for c in decl_line[i:]:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1:
            out.append(c)
    return re.sub(r"\s+", "", "".join(out))


# --- ground truth: production methods the PR changed (base coordinates) --

def ground_truth(repo: str, prism: str, base: str, changed_files: list[str],
                 merge: str) -> set[str]:
    """Every production method touched by the diff, as file:method, mapped to
    the enclosing method in the BASE checkout (change_impact's coordinates)."""
    gt = set()
    diff = git(repo, "diff", "--unified=0", base, merge, "--", "*.java")
    cur_file, base_ln = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:]
            continue
        h = HUNK_RE.match(line)
        if h:
            base_ln = int(h.group(1))
            continue
        if not cur_file or not prod_java(cur_file):
            continue
        if line.startswith("-") and not line.startswith("---"):
            m = _method_at(repo, base, cur_file, base_ln)
            if m:
                gt.add(f"{cur_file}:{m}")
            base_ln += 1
    return gt


_span_cache: dict[str, list[tuple[int, int, str]]] = {}


def _method_at(repo: str, base: str, path: str, line: int) -> str | None:
    """Enclosing Java method name for a base-file line, via a one-pass brace
    scan of the base source (no index needed; matches change_impact's
    file:methodName reporting)."""
    key = f"{base}:{path}"
    if key not in _span_cache:
        src = git(repo, "show", f"{base}:{path}").splitlines()
        spans, stack = [], []
        depth = 0
        pending = None
        for i, ln in enumerate(src, start=1):
            nm = method_name(ln)
            if nm and "{" not in ln and ";" not in ln:
                pending = (nm, i)
            for c in ln:
                if c == "{":
                    if pending and depth >= 0:
                        stack.append((pending[0], pending[1], depth))
                        pending = None
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if stack and stack[-1][2] == depth:
                        nm, start, _ = stack.pop()
                        spans.append((start, i, nm))
            if pending and ("{" in ln or ";" in ln):
                if "{" not in ln:  # abstract/interface decl: single line
                    spans.append((pending[1], i, pending[0]))
                pending = None
        _span_cache[key] = spans
    best = None
    for start, end, nm in _span_cache[key]:
        if start <= line <= end and (best is None or start > best[0]):
            best = (start, end, nm)
    return best[2] if best else None


# --- stage 4: engine change-impact + score ------------------------------

def engine_sites(prism: str, workdir: Path, target: str) -> tuple[set[str], dict]:
    r = subprocess.run([prism, "change-impact", target, "."],
                       capture_output=True, text=True, cwd=workdir, timeout=300)
    if r.returncode != 0:
        return set(), {"error": r.stderr[:200]}
    d = json.loads(r.stdout)
    sites = set()
    for g in ("declarations", "family", "callers", "declaringTypes", "supers"):
        for s in d.get(g, []):
            fp, nm = s.get("filePath", ""), s.get("name", "")
            if fp and nm:
                sites.add(f"{fp}:{nm}")
    return sites, {"completeness": d.get("completeness"),
                   "overridesExternal": d.get("overridesExternal")}


def _base(p: str) -> str:
    return p.rsplit("/", 1)[-1]


def score_pr(gt: set[str], engine: set[str]) -> tuple[float, float, set, set]:
    """Match on method name + file basename (score.py discipline)."""
    def key(s):
        f, m = s.rsplit(":", 1)
        return (_base(f), m)
    gk = {key(s): s for s in gt}
    ek = {key(s) for s in engine}
    hit = {s for k, s in gk.items() if k in ek}
    recall = len(hit) / len(gt) if gt else 0.0
    matched_engine = {s for s in engine if key(s) in gk}
    precision = len(matched_engine) / len(engine) if engine else 0.0
    return recall, precision, gt - hit, engine - matched_engine


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo, prism = args.repo, args.prism
    prs = mine(args.owner, args.name, args.limit)
    print(f"[mine] {len(prs)} merged PRs")

    inscope, ill_posed, scored = [], 0, []
    wt_root = Path("/tmp/pr-replay-wt")
    wt_root.mkdir(exist_ok=True)
    out = open(args.out, "w")

    for i, pr in enumerate(prs):
        c = classify(repo, pr["merge"], pr["title"])
        if not c:
            continue
        inscope.append(pr["num"])
        # Index the before-state in an isolated worktree.
        wt = wt_root / f"{args.name}-{pr['num']}"
        subprocess.run(["git", "-C", repo, "worktree", "add", "--detach",
                        "-f", str(wt), c["base"]], capture_output=True, text=True)
        try:
            subprocess.run([prism, "index", "."], cwd=wt,
                           capture_output=True, text=True, timeout=600)
            gt = ground_truth(repo, prism, c["base"], c["changed_files"], pr["merge"])
            if not gt:
                continue
            all_sites, flags_any, dropped = set(), {}, False
            for tgt in c["targets"]:
                sites, flags = engine_sites(prism, wt, tgt)
                if flags.get("overridesExternal"):
                    dropped = True   # ill-posed: overrides external contract
                    break
                all_sites |= sites
                flags_any = flags
            if dropped:
                ill_posed += 1
                continue
            recall, prec, missed, extra = score_pr(gt, all_sites)
            rec = {"pr": pr["num"], "title": pr["title"][:80],
                   "targets": c["targets"], "gt": len(gt), "engine": len(all_sites),
                   "recall": round(recall, 4), "precision": round(prec, 4),
                   "missed": sorted(missed)[:8], "completeness": flags_any.get("completeness")}
            scored.append(rec)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"  PR#{pr['num']:<6} tgt={','.join(t.split('.')[-1] for t in c['targets'])[:30]:<30} "
                  f"GT={gt and len(gt):<3} rec={recall:.3f} prec={prec:.3f}")
        finally:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force",
                            str(wt)], capture_output=True, text=True)

    out.close()
    print("\n" + "=" * 60)
    print(f"total merged PRs sampled : {len(prs)}")
    print(f"in-scope (change-impact) : {len(inscope)}  ({100*len(inscope)/max(len(prs),1):.1f}% base rate)")
    print(f"ill-posed (external)     : {ill_posed}  (rejected)")
    print(f"scored                   : {len(scored)}")
    if scored:
        mr = sum(r["recall"] for r in scored) / len(scored)
        mp = sum(r["precision"] for r in scored) / len(scored)
        perfect = sum(1 for r in scored if r["recall"] >= 0.999)
        print(f"mean recall              : {mr:.4f}")
        print(f"mean precision           : {mp:.4f}")
        print(f"recall == 1.0            : {perfect}/{len(scored)}")


if __name__ == "__main__":
    main()
