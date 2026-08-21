#!/usr/bin/env python3
"""Mine real merged commits that ARE mandated-wide-radius changes.

A candidate is a commit whose diff is dominated by one mechanical
substitution (rename / signature change / API migration) across many files —
the task family where an agent cannot design around the width, because the
instruction IS the sweep. These become tasks: instruction derived from the
substitution, gold = the commit's own diff, oracle = build/tests at the
commit plus site-completeness vs gold.

Detection per commit:
  - >= MIN_FILES changed code files (docs/vendor excluded)
  - extract paired -/+ lines; find the most common single-token (old,new)
    substitution among them
  - mechanical ratio = pairs explained by that substitution / all pairs
  - keep if ratio >= MIN_RATIO and sites >= MIN_SITES

Usage: python3 mine_wide_sweeps.py <repo_dir>... [--out candidates.json]
"""
from __future__ import annotations
import difflib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

MIN_FILES = 6
MIN_SITES = 15
MIN_RATIO = 0.6
MAX_COMMITS = 4000
CODE_EXT = {".py", ".go", ".ts", ".tsx", ".js", ".java", ".rs", ".cs", ".php", ".c", ".cc", ".cpp", ".h"}
SKIP_DIR = re.compile(r"(^|/)(vendor|node_modules|third_party|dist|build|\.git)(/|$)")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=300).stdout


def token_sub(before: str, after: str):
    """If after == before with exactly one token replaced (possibly at several
    positions), return (old, new). Else None."""
    bt, at = TOKEN.findall(before), TOKEN.findall(after)
    if len(bt) != len(at):
        return None
    diffs = [(x, y) for x, y in zip(bt, at) if x != y]
    if not diffs:
        return None
    pairs = set(diffs)
    if len(pairs) != 1:
        return None
    old, new = next(iter(pairs))
    # replacing old->new in before must yield after (word-boundary)
    if re.sub(rf"\b{re.escape(old)}\b", new, before) != after:
        return None
    return old, new


def analyze_commit(repo: Path, sha: str):
    diff = sh("git", "-C", str(repo), "show", "--format=", "-U0", sha)
    if not diff or len(diff) > 2_000_000:
        return None
    files, minus, plus = set(), [], []
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            p = Path(cur)
            if SKIP_DIR.search(cur) or p.suffix not in CODE_EXT:
                cur = None
            else:
                files.add(cur)
        elif cur and line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:])
        elif cur and line.startswith("+") and not line.startswith("+++"):
            plus.append(line[1:])
    if len(files) < MIN_FILES:
        return None
    # pair up -/+ lines order-wise (U0 hunks are local, so zip is a fair proxy)
    n = min(len(minus), len(plus))
    if n < MIN_SITES:
        return None
    subs = Counter()
    for b, a in zip(minus[:800], plus[:800]):
        s = token_sub(b, a)
        if s:
            subs[s] += 1
    if not subs:
        return None
    (old, new), hits = subs.most_common(1)[0]
    ratio = hits / n
    if hits < MIN_SITES or ratio < MIN_RATIO:
        return None
    return {"sha": sha, "old": old, "new": new, "sites": hits,
            "pairs": n, "ratio": round(ratio, 2), "files": len(files)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = "wide-sweep-candidates.json"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    results = []
    for repo_s in args:
        repo = Path(repo_s)
        if not (repo / ".git").exists():
            continue
        shas = sh("git", "-C", str(repo), "log", "--no-merges",
                  f"--max-count={MAX_COMMITS}", "--format=%H").split()
        found = 0
        for sha in shas:
            try:
                r = analyze_commit(repo, sha)
            except Exception:
                continue
            if r:
                subject = sh("git", "-C", str(repo), "show", "-s", "--format=%s", sha).strip()
                r.update({"repo": repo.name, "repo_path": str(repo), "subject": subject[:100]})
                results.append(r)
                found += 1
                print(f"  {repo.name} {sha[:10]} files={r['files']:3} sites={r['sites']:4} "
                      f"ratio={r['ratio']:.2f}  {r['old']} -> {r['new']}  | {subject[:60]}", flush=True)
        print(f"[{repo.name}] {found} candidates from {len(shas)} commits", flush=True)
    results.sort(key=lambda r: -r["sites"])
    json.dump(results, open(out, "w"), indent=1)
    print(f"\n{len(results)} total -> {out}")


main()
