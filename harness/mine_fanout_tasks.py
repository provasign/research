"""Mine issue->PR pairs whose fix is a FAN-OUT EDIT: one contract changed
across many files — the task family where completeness is load-bearing and
the need for change-impact arises INSIDE the work, never in the prompt.

This is the benchmark RESULTS.md §5 says has no citable number: real tasks
(issue-briefed, post-cutoff) where a text-search agent forgets sites at the
measured 0.62–0.75 rate. Unlike tasks-e2e-meaningful (localized fixes,
capability parity proven), these tasks are selected because their gold fix
edits the SAME identifier in >= FANOUT_FILES distinct source files.

Gates:
  - merged post-cutoff, linked issue (closingIssuesReferences) with a real
    body — the agent brief is the issue, never the PR;
  - >= MIN_SRC_FILES source files touched; churn bounded (it must be a task,
    not a rewrite);
  - a non-stopword identifier appears in the CHANGED LINES of >=
    FANOUT_FILES distinct files — the fanned-out contract, recorded per
    candidate for the audit;
  - not bump/revert/typo/docs/backport noise.

Refactors often add no tests, so no test-churn gate here. The oracle for
this family (built at validation time) is: suite stays green + the contract
actually changed + gold-site coverage. Every candidate still needs the
Docker validation + human leak audit before it is a task.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from mine_meaningful_tasks import SKIP_RE, TEST_RE, gh, gh_json, linked_issue

SRC_RE = re.compile(r"\.(py|go|ts|js|java|rb|rs)$")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOP = {
    "self", "this", "return", "import", "from", "def", "func", "class", "None",
    "True", "False", "nil", "null", "true", "false", "assert", "raise", "else",
    "elif", "print", "value", "values", "data", "name", "type", "test", "tests",
    "error", "errors", "string", "static", "public", "private", "const",
}

REFACTOR_RE = re.compile(
    r"\b(deprecat|remove|renam|replac|consolidat|unif|consisten|migrat|"
    r"thread|propagat|extract|convert|switch)\w*\b", re.I)

CUTOFF_YEAR = "2026"
MIN_SRC_FILES = 5
FANOUT_FILES = 5
MAX_CHURN = 1500
MAX_FILES = 60
MIN_ISSUE_BODY = 150


def fanout_symbols(repo: str, number: int) -> dict | None:
    """Identifiers edited across many files: {symbol: n_files}, plus shape."""
    files = gh_json("pr", "view", str(number), "-R", repo, "--json", "files")["files"]
    if len(files) > MAX_FILES:
        return None
    src = [f for f in files if SRC_RE.search(f["path"]) and not TEST_RE.search(f["path"])]
    if len(src) < MIN_SRC_FILES:
        return None
    churn = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
    if churn > MAX_CHURN:
        return None
    try:
        diff = gh("pr", "diff", str(number), "-R", repo)
    except RuntimeError:
        return None
    # Which files' changed lines mention which identifiers.
    sym_files: dict[str, set] = defaultdict(set)
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            p = line[6:]
            cur = p if (SRC_RE.search(p) and not TEST_RE.search(p)) else None
        elif cur and (line.startswith("+") or line.startswith("-")) and not line.startswith(("+++", "---")):
            for ident in set(IDENT_RE.findall(line)):
                if ident.lower() not in STOP:
                    sym_files[ident].add(cur)
    spread = {s: len(fs) for s, fs in sym_files.items() if len(fs) >= FANOUT_FILES}
    if not spread:
        return None
    top = sorted(spread.items(), key=lambda kv: -kv[1])[:8]
    return {
        "src_files": len(src),
        "churn": churn,
        "fanout_symbols": dict(top),
        "max_fanout": top[0][1],
        "src_paths": [f["path"] for f in src][:15],
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
        shape = fanout_symbols(repo, p["number"])
        if shape is None:
            continue
        iss = linked_issue(repo, p)
        # Fan-out refactors (deprecations, consistency sweeps) usually have
        # NO closing issue — a maintainer just does them (measured: 2
        # candidates from 1,800 PRs with the issue gate; the netty PR-replay
        # hit the same wall). For refactor-verb titles the PR TITLE alone is
        # a realistic brief ("Remove colorama" is what a real ticket says);
        # the body is still never used. No-issue candidates are flagged for
        # a stricter human audit.
        if iss is None and not REFACTOR_RE.search(p["title"]):
            continue
        rec = {
            "repo": repo, "pr": p["number"], "pr_url": p["url"],
            "pr_title": p["title"], "merged_at": p["mergedAt"],
            "brief": "issue" if iss else "title-only",
            **shape,
        }
        if iss:
            rec.update(issue=iss["number"], issue_title=iss["title"],
                       issue_url=iss["url"],
                       issue_body_chars=len((iss.get("body") or "").strip()))
        out.append(rec)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--out", default="runs/fanout-candidates.json")
    args = ap.parse_args()

    rows: list[dict] = []
    for repo in args.repos:
        try:
            found = mine(repo, args.limit)
        except RuntimeError as e:
            print(f"{repo}: ERROR {e}")
            continue
        print(f"{repo}: {len(found)} fan-out candidate(s)")
        rows.extend(found)

    rows.sort(key=lambda r: (-r["max_fanout"], -r["src_files"]))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rows, indent=2))
    print(f"\n{'repo':22} {'PR':>6} {'files':>5} {'fan':>4}  top symbol            title")
    for r in rows:
        top = next(iter(r["fanout_symbols"]))
        print(f"{r['repo']:22} #{r['pr']:>5} {r['src_files']:>5} {r['max_fanout']:>4}  "
              f"{top:20.20}  {r['pr_title'][:48]}")
    print(f"\n{len(rows)} candidates -> {args.out}")


if __name__ == "__main__":
    main()
