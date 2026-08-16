#!/usr/bin/env python3
"""Is the benchmark bed clean? Check before trusting any number off it.

This exists because the bed has been silently wrong at least three times,
and every failure was invisible in the results:

  - the /tmp repo cache was purged by macOS's periodic cleaner, leaving
    repos that LOOKED present but whose checkout silently no-opped; a smoke
    ran 64 turns on the wrong code before a human noticed;
  - worktrees shared refs with the cache, so `git log --all` reached the
    GOLD FIX -- 21 of 228 cells did archaeology, 16:5 baseline-skewed;
  - the prism arm carried a grep denial from a reverted release for three
    versions, which made "the agent chose prism" unfalsifiable.

All three are fixed in swebench_ab.py. This asserts they STAY fixed, and
adds the check none of them had: that the fix is actually absent from the
tree the agent edits.

    python3 audit_bed.py runs/swebench-live/slice-ab38.json            # tasks
    python3 audit_bed.py runs/swebench-live/slice-ab38.json --wt       # + live worktrees

Exit 1 if anything is wrong.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WT_ROOT = Path("/tmp/swebench-wt")
REPO_CACHE = Path.home() / ".cache" / "prism-research" / "swebench-repos"


def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True)


def check_tasks(tasks: list[dict]) -> list[str]:
    """Task-level problems: missing fields, and solution leakage into the
    prompt. The agent sees problem_statement verbatim; an issue body that
    contains the patch turns the benchmark into a copying exercise."""
    bad = []
    for t in tasks:
        tid = t.get("instance_id", "?")
        for k in ("instance_id", "repo", "base_commit", "problem_statement", "patch"):
            if not t.get(k):
                bad.append(f"{tid}: missing {k}")
        ps = t.get("problem_statement", "")
        # A diff in the issue body hands the answer over.
        if re.search(r"^\+\+\+ b/|^diff --git ", ps, re.M):
            bad.append(f"{tid}: problem_statement CONTAINS A DIFF — the fix is in the prompt")
        # Long verbatim overlap between the issue text and the gold patch's
        # added lines is the softer version of the same leak.
        adds = [l[1:].strip() for l in t.get("patch", "").split("\n")
                if l.startswith("+") and not l.startswith("+++") and len(l) > 40]
        leaked = [a for a in adds if a in ps]
        if len(leaked) >= 3:
            bad.append(f"{tid}: {len(leaked)} gold-patch lines appear verbatim in problem_statement")
    return bad


def check_worktree(t: dict, wt: Path) -> list[str]:
    """Worktree-level problems for one live cell."""
    bad = []
    tid = t["instance_id"]
    head = sh("git", "-C", str(wt), "rev-parse", "HEAD").stdout.strip()
    if head != t["base_commit"]:
        bad.append(f"{tid}: HEAD {head[:12]} != base {t['base_commit'][:12]} — WRONG CODE")
        return bad  # everything downstream is meaningless

    # Gold-fix reachability. Refs and the remote are stripped at setup so
    # `git log --all` cannot surface the fixing commit; verify, don't assume.
    refs = sh("git", "-C", str(wt), "for-each-ref", "--format=%(refname)").stdout.split()
    if refs:
        bad.append(f"{tid}: {len(refs)} refs present — `git log --all` can reach the gold fix")
    if sh("git", "-C", str(wt), "remote").stdout.strip():
        bad.append(f"{tid}: a remote is configured — the fix is fetchable")
    newer = sh("git", "-C", str(wt), "log", "--all", "--oneline", "--not", t["base_commit"]).stdout.strip()
    if newer:
        bad.append(f"{tid}: {len(newer.splitlines())} commits reachable beyond base")

    # THE check the earlier audits lacked: is the fix actually absent from
    # the tree? A gold patch that still applies forward proves it is. Line
    # comparison is not enough -- patches legitimately re-add lines that
    # already exist elsewhere in the file (measured: 8 of 62 on
    # browser-use-2480, which is nonetheless clean).
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as fh:
        fh.write(t["patch"])
        patch = fh.name
    fwd = sh("git", "-C", str(wt), "apply", "--check", patch)
    if fwd.returncode != 0:
        bad.append(f"{tid}: gold patch does NOT apply to the checkout — "
                   f"the tree is not at a clean pre-fix state ({fwd.stderr.strip()[:90]})")
    Path(patch).unlink(missing_ok=True)

    # Arm isolation: the baseline worktree must carry zero prism.
    arm = wt.name.rsplit("__", 1)[-1]
    if arm in ("no-prism", "baseline"):
        for stray in (".mcp.json", ".grove", ".cursor/mcp.json"):
            if (wt / stray).exists():
                bad.append(f"{tid}: baseline arm contains {stray} — arm isolation broken")
        cm = wt / "CLAUDE.md"
        if cm.exists() and "prism" in cm.read_text(errors="ignore").lower():
            bad.append(f"{tid}: baseline CLAUDE.md mentions prism — arm isolation broken")
    else:
        sp = wt / ".claude" / "settings.json"
        if sp.exists():
            deny = json.loads(sp.read_text()).get("permissions", {}).get("deny", [])
            if deny:
                bad.append(f"{tid}: prism arm has deny rules {deny} — "
                           f"not the shipped config; adoption becomes unfalsifiable")
    return bad


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    tasks = json.load(open(sys.argv[1]))
    check_wt = "--wt" in sys.argv
    problems = check_tasks(tasks)
    print(f"tasks: {len(tasks)}   task-level problems: {len(problems)}")

    # The cache must not live in /tmp, and must be a real git repo.
    if str(REPO_CACHE).startswith("/tmp"):
        problems.append("repo cache is under /tmp — macOS purges it mid-run")
    if REPO_CACHE.exists():
        broken = [d.name for d in REPO_CACHE.iterdir()
                  if d.is_dir() and not (d / "HEAD").exists() and not (d / ".git").exists()]
        if broken:
            problems.append(f"cached clones with no git metadata (silent checkout no-op): {broken[:5]}")
        print(f"repo cache: {REPO_CACHE} ({len(list(REPO_CACHE.iterdir()))} clones)")

    if check_wt:
        by_id = {t["instance_id"]: t for t in tasks}
        live = [d for d in WT_ROOT.glob("*") if d.is_dir()] if WT_ROOT.exists() else []
        print(f"live worktrees: {len(live)}")
        for wt in live:
            tid = wt.name
            for suf in ("__no-prism", "__prism", "__baseline", "__prism-cli"):
                if tid.endswith(suf):
                    tid = tid[: -len(suf)]
                    break
            if tid in by_id:
                problems += check_worktree(by_id[tid], wt)

    print()
    if problems:
        print(f"!! {len(problems)} PROBLEM(S)")
        for p in problems:
            print(f"   {p}")
        sys.exit(1)
    print("bed is clean on every check")


if __name__ == "__main__":
    main()
