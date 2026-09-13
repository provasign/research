#!/usr/bin/env python3
"""Mine real merged commits whose token-substitution rename crosses the
code/framework-artifact boundary: at least one hit in a .java file AND at
least one hit in a template (.html/.jsp/.ftl) or *Repository.java (JPA
derived-query) file. This is the routing-program bed gap identified
2026-08-29 (ROUTING-PROGRAM.md): the fanout bed's existing pallets tasks are
grep-saturated because every gold site is a same-file-type textual match;
these tasks require the agent to follow a NAME-DERIVED framework reference
out of the .java files it would naturally grep first.

Same token-substitution detection as mine_wide_sweeps.py, cross-artifact
gate added, thresholds lowered for smaller repos (petclinic-scale).

Usage: python3 mine_framework_crossings.py <repo_dir>... [--out FILE]
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

MIN_FILES = 2
MIN_SITES = 3
MIN_RATIO = 0.5
MAX_COMMITS = 6000
CODE_EXT = {".java"}
TEMPLATE_EXT = {".html", ".jsp", ".ftl", ".htm"}
SKIP_DIR = re.compile(r"(^|/)(vendor|node_modules|target|build|test|\.git)(/|$)")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=300).stdout


def token_sub(before, after):
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
    if re.sub(rf"\b{re.escape(old)}\b", new, before) != after:
        return None
    return old, new


def kind_of(path: str) -> str:
    p = Path(path)
    if p.suffix in TEMPLATE_EXT:
        return "template"
    if p.name.endswith("Repository.java"):
        return "jparepo"
    if p.suffix in CODE_EXT:
        return "java"
    return "other"


def analyze_commit(repo: Path, sha: str):
    diff = sh("git", "-C", str(repo), "show", "--format=", "-U0", sha)
    if not diff or len(diff) > 1_500_000:
        return None
    file_kind = {}
    cur = None
    minus, plus, site_file = [], [], []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            k = kind_of(cur)
            if SKIP_DIR.search(cur) or k == "other":
                cur = None
            else:
                file_kind[cur] = k
        elif cur and line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:]); site_file.append(cur)
        elif cur and line.startswith("+") and not line.startswith("+++"):
            plus.append(line[1:])
    if len(file_kind) < MIN_FILES:
        return None
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
    kinds_hit = {file_kind[f] for f, (b, a) in zip(site_file, zip(minus, plus))
                 if token_sub(b, a) == (old, new)}
    if "java" not in kinds_hit or not (kinds_hit & {"template", "jparepo"}):
        return None  # not cross-artifact
    return {"sha": sha, "old": old, "new": new, "sites": hits, "pairs": n,
            "ratio": round(ratio, 2), "files": len(file_kind),
            "kinds": sorted(kinds_hit)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = "framework-crossing-candidates.json"
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
                parent = sh("git", "-C", str(repo), "rev-parse", f"{sha}^").strip()
                r.update({"repo": repo.name, "repo_path": str(repo),
                          "subject": subject[:100], "parent": parent})
                results.append(r)
                found += 1
                print(f"  {repo.name} {sha[:10]} files={r['files']:3} sites={r['sites']:4} "
                      f"kinds={r['kinds']} {r['old']}->{r['new']} | {subject[:55]}", flush=True)
        print(f"[{repo.name}] {found} candidates from {len(shas)} commits", flush=True)
    results.sort(key=lambda r: -r["sites"])
    json.dump(results, open(out, "w"), indent=1)
    print(f"\n{len(results)} total -> {out}")


main()
