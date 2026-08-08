"""Mine post-cutoff issue->PR pairs whose fix MEANINGFULLY fans out.

The e2e pilot's task set (mine_2026_tasks.py) was contamination-clean but
localized: single-site fixes, the regime where the paper's own C1 says
graph ~= grep — a benchmark that cannot discriminate by construction. This
miner keeps every pilot gate and adds MEANINGFULNESS gates so the task
distribution contains fixes a context tool could actually help with:

  meaningful =
    - >=2 non-test source files touched, OR >=4 distinct functions changed
      (fan-out: the fix is not containable in one screenful),
    - >=30 changed source lines (not a guard-clause one-liner),
    - NOT codemod-shaped (many files, ~1 line each: rename campaigns),
    - linked issue EXISTS with >=200 chars of body (the agent prompt is the
      issue text, never the PR — the pilot's leak lesson),
    - plus the pilot gates: merged post-cutoff, source AND test churn,
      no bump/revert/typo/CI noise, bounded total size.

Output: candidates JSON + an audit table sorted by fan-out. Selection stays
outcome-blind (gates are structural, applied before any arm runs) and every
candidate still needs the Docker fail->pass promotion plus a human GT audit
before it becomes a task — this finds the haystack worth auditing.

Usage: python3 mine_meaningful_tasks.py pallets/click pallets/flask ... [--limit 150]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

BUG_RE = re.compile(r"\b(fix(e[sd])?|close[sd]?|resolve[sd]?)\b\s*:?\s*#(\d+)", re.I)
TEST_RE = re.compile(r"(^|/)(tests?|testing)/|_test\.py$|test_.*\.py$", re.I)
SRC_RE = re.compile(r"\.py$")
SKIP_RE = re.compile(r"\b(bump|merge|revert|typo|changelog|release note|pre-commit|"
                     r"github action|\bci\b|docs?\b|documentation|backport)\b", re.I)
# git diff hunk header with python function context: @@ -a,b +c,d @@ def name(
HUNK_FUNC_RE = re.compile(r"^@@ .* @@\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)

CUTOFF_YEAR = "2026"
MIN_SRC_LINES = 30
MIN_ISSUE_BODY = 200
MAX_CHURN = 600
MAX_FILES = 25


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return r.stdout


def gh_json(*args: str):
    return json.loads(gh(*args))


def linked_issue(repo: str, pr: dict) -> dict | None:
    """The issue the PR closes, with enough body to serve as the prompt.

    Uses GitHub's own closingIssuesReferences — NOT a regex over the PR
    body. Measured: pydantic's PR template contains the literal example
    text "fix #123", so a regex matched every PR and resolved them all to
    issue #123 from 2017 (template-artifact pollution, the same class of
    GT rot the PR-replay postmortem documented).
    """
    try:
        refs = gh_json("pr", "view", str(pr["number"]), "-R", repo,
                       "--json", "closingIssuesReferences")["closingIssuesReferences"]
    except RuntimeError:
        return None
    if not refs:
        return None
    num = str(refs[0]["number"])
    try:
        iss = gh_json("issue", "view", num, "-R", repo, "--json", "number,title,body,url")
    except RuntimeError:
        return None
    body = (iss.get("body") or "").strip()
    if len(body) < MIN_ISSUE_BODY:
        return None  # too thin to brief an agent without leaking the fix
    return iss


def fanout(repo: str, number: int) -> dict | None:
    """Structural shape of the fix: src files, src lines, distinct functions."""
    files = gh_json("pr", "view", str(number), "-R", repo, "--json", "files")["files"]
    paths = [f["path"] for f in files]
    if len(paths) > MAX_FILES:
        return None
    src = [f for f in files if SRC_RE.search(f["path"]) and not TEST_RE.search(f["path"])]
    tests = [f for f in files if TEST_RE.search(f["path"])]
    if not src or not tests:
        return None  # need a discriminating test AND a source change
    src_lines = sum(f.get("additions", 0) + f.get("deletions", 0) for f in src)
    total = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
    if total > MAX_CHURN or src_lines < MIN_SRC_LINES:
        return None
    # Codemod shape: >=5 src files with <=2 changed lines each — a rename
    # campaign, not a reasoning task.
    if len(src) >= 5 and all(f.get("additions", 0) + f.get("deletions", 0) <= 2 for f in src):
        return None
    try:
        diff = gh("pr", "diff", str(number), "-R", repo)
    except RuntimeError:
        diff = ""
    funcs = sorted(set(HUNK_FUNC_RE.findall(diff)))
    return {
        "src_files": len(src),
        "test_files": len(tests),
        "src_lines": src_lines,
        "functions_changed": len(funcs),
        "functions": funcs[:12],
        "src_paths": [f["path"] for f in src][:12],
    }


def mine(repo: str, limit: int) -> list[dict]:
    prs = gh_json("pr", "list", "-R", repo, "--state", "merged", "--limit", str(limit),
                  "--json", "number,title,mergedAt,labels,body,url")
    out = []
    for p in prs:
        if not (p["mergedAt"] or "").startswith(CUTOFF_YEAR):
            continue
        if SKIP_RE.search(p["title"]):
            continue
        iss = linked_issue(repo, p)
        if iss is None:
            continue
        shape = fanout(repo, p["number"])
        if shape is None:
            continue
        # THE meaningfulness gate: multi-file or multi-function.
        if shape["src_files"] < 2 and shape["functions_changed"] < 4:
            continue
        out.append({
            "repo": repo,
            "pr": p["number"],
            "pr_url": p["url"],
            "pr_title": p["title"],
            "merged_at": p["mergedAt"],
            "issue": iss["number"],
            "issue_title": iss["title"],
            "issue_url": iss["url"],
            "issue_body_chars": len((iss.get("body") or "").strip()),
            **shape,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--out", default="runs/meaningful-candidates.json")
    args = ap.parse_args()

    rows: list[dict] = []
    for repo in args.repos:
        try:
            found = mine(repo, args.limit)
        except RuntimeError as e:
            print(f"{repo}: ERROR {e}")
            continue
        print(f"{repo}: {len(found)} meaningful candidate(s)")
        rows.extend(found)

    rows.sort(key=lambda r: (r["src_files"], r["functions_changed"], r["src_lines"]),
              reverse=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rows, indent=2))

    print(f"\n{'repo':24} {'PR':>6} {'files':>5} {'funcs':>5} {'lines':>5}  title")
    for r in rows:
        print(f"{r['repo']:24} #{r['pr']:>5} {r['src_files']:>5} {r['functions_changed']:>5} "
              f"{r['src_lines']:>5}  {r['pr_title'][:60]}")
    print(f"\n{len(rows)} candidates -> {args.out}")
    print("Next: Docker fail->pass promotion (docker_eval.py) + human GT audit "
          "of each issue body for fix leakage, THEN they become tasks.")


if __name__ == "__main__":
    main()
