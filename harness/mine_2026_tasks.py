"""Mine genuinely post-cutoff (2026) Python tasks with fail->pass tests.

The end-to-end benchmark needs tasks the test models could NOT have memorized.
SWE-bench-Live tops out at June 2025 (pre-cutoff); the live GitHub data universe
is at 2026, so we mine fresh merged PRs directly. This finds CANDIDATES; the
Docker fail->pass verification (needs the daemon up) is a separate step that
promotes candidates to tasks.

A candidate PR must be:
  - merged in 2026 (post-cutoff, contamination-free by date),
  - touch >=1 non-test source file AND >=1 test file (a fail->pass test exists),
  - link an issue ("Fixed #", "Closes #") for a BUG, or be labelled a feature,
  - not a merge/revert/dependency-bump, and not enormous.

Uses the authenticated `gh` CLI (no token plumbing). Read-only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess

BUG_RE = re.compile(r"\b(fix(e[sd])?|close[sd]?|resolve[sd]?)\b\s+#\d+", re.I)
TEST_RE = re.compile(r"(^|/)(tests?|testing)/|_test\.py$|test_.*\.py$", re.I)
SRC_RE = re.compile(r"\.py$")
SKIP_RE = re.compile(r"\b(bump|merge|revert|typo|changelog|release note|pre-commit|"
                     r"github action|ci)\b", re.I)


def gh_json(*args: str):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return json.loads(r.stdout)


def candidates(repo: str, limit: int, year: str = "2026"):
    prs = gh_json("pr", "list", "-R", repo, "--state", "merged", "--limit", str(limit),
                  "--json", "number,title,mergedAt,labels,body")
    out = []
    for p in prs:
        if not (p["mergedAt"] or "").startswith(year):
            continue
        title = p["title"]
        if SKIP_RE.search(title):
            continue
        labels = {l["name"].lower() for l in p.get("labels", [])}
        is_bug = bool(BUG_RE.search(title) or BUG_RE.search(p.get("body") or ""))
        is_feat = bool(labels & {"feature", "enhancement", "new feature"})
        if not (is_bug or is_feat):
            continue
        # file-level shape: needs source AND test churn, and not huge
        files = gh_json("pr", "view", str(p["number"]), "-R", repo, "--json", "files")["files"]
        paths = [f["path"] for f in files]
        has_test = any(TEST_RE.search(x) for x in paths)
        has_src = any(SRC_RE.search(x) and not TEST_RE.search(x) for x in paths)
        churn = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
        if not (has_test and has_src) or churn > 400 or len(paths) > 25:
            continue
        out.append({"instance_id": f"{repo.replace('/', '__')}__pr{p['number']}",
                    "repo": repo, "pr": p["number"], "merged_at": p["mergedAt"],
                    "kind": "bug" if is_bug else "feature", "title": title,
                    "churn": churn, "n_files": len(paths),
                    "test_files": [x for x in paths if TEST_RE.search(x)],
                    "src_files": [x for x in paths if SRC_RE.search(x) and not TEST_RE.search(x)]})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="owner/name")
    ap.add_argument("--scan", type=int, default=60, help="how many recent merged PRs to scan")
    ap.add_argument("--year", default="2026")
    a = ap.parse_args()
    cands = candidates(a.repo, a.scan, a.year)
    print(f"# {len(cands)} candidate {a.year} tasks in {a.repo} (of {a.scan} scanned)\n")
    for c in cands:
        print(f"  [{c['kind']:7}] pr#{c['pr']:<6} churn={c['churn']:<4} "
              f"{c['merged_at'][:10]}  {c['title'][:64]}")
    print(json.dumps(cands, indent=2)) if False else None
