#!/usr/bin/env python3
"""Build a bed of LARGE-BLAST-RADIUS tasks — the stratum prism is claimed on.

The 38-task bed has a median gold patch of 2 files and exactly 2 tasks at >=8
files. Prism's measured win (RESULTS.md §9.1) is on change sets of 8-310
sites. So that bed cannot test the claim: a pooled result over it measures
its size distribution, not the tool. Confirmed on the 2026-08-16 run — flat
overall, and no cells at all in the 10+ file stratum.

Selection, in order:
  1. gold patch touches >= MIN_FILES files
  2. NOT a mechanical sweep — a 90-file f-string rewrite (beets-5890, 73 turns
     and $4.20 in a real cell) is a script job, not a graph query, and prism
     has nothing to offer it. Screened by title language and by shape:
     many files, few lines each, adds ~= dels.
  3. repo-diverse — at most MAX_PER_REPO, because a naive top-N pick lands 4
     of 12 on instructlab and one repo's idioms then dominate the result.
  4. has a real test signal (>= 1 FAIL_TO_PASS)

    python3 select_radius_bed.py live-lite-300.json slice-radius.json [N]
"""
from __future__ import annotations

import collections
import json
import re
import sys

MIN_FILES = 4
MAX_PER_REPO = 2
SWEEP_TITLE = re.compile(
    r"update to use|migrate|rename|reformat|black|isort|lint|typo|"
    r"f-string|bump|upgrade dependenc|drop python|deprecat\w* removal|"
    r"add type hints|annotate", re.I)


def patch_shape(p: str) -> tuple[int, int, int, int]:
    files = len(re.findall(r"^\+\+\+ b/", p, re.M))
    hunks = len(re.findall(r"^@@ ", p, re.M))
    adds = sum(1 for l in p.split("\n") if l.startswith("+") and not l.startswith("+++"))
    dels = sum(1 for l in p.split("\n") if l.startswith("-") and not l.startswith("---"))
    return files, hunks, adds, dels


def is_sweep(task: dict) -> str | None:
    title = task.get("problem_statement", "").strip().split("\n")[0]
    if SWEEP_TITLE.search(title):
        return "sweep-ish title"
    f, h, a, d = patch_shape(task.get("patch", ""))
    if f >= 15 and a / max(f, 1) < 12 and d and 0.7 < a / d < 1.4:
        # Many files, a handful of lines each, additions balancing deletions:
        # the signature of the same edit repeated, not a change that propagates.
        return f"mechanical shape ({f} files, {a}+/{d}-)"
    return None


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    want = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    rows = json.load(open(src))

    cands = []
    rejected = collections.Counter()
    for t in rows:
        f, h, a, d = patch_shape(t.get("patch", ""))
        if f < MIN_FILES:
            rejected["too small"] += 1
            continue
        if not t.get("FAIL_TO_PASS"):
            rejected["no test signal"] += 1
            continue
        why = is_sweep(t)
        if why:
            rejected[f"sweep: {why.split('(')[0].strip()}"] += 1
            continue
        cands.append((f, h, a, d, t))

    # Biggest radius first, but capped per repo so no single project dominates.
    cands.sort(key=lambda x: (-x[0], -len(x[4].get("FAIL_TO_PASS", []))))
    per, out = collections.Counter(), []
    for f, h, a, d, t in cands:
        r = t["repo"]
        if per[r] >= MAX_PER_REPO:
            continue
        per[r] += 1
        out.append(t)
        print(f"  {f:3} files {h:4} hunks  {a:5}+/{d:<5}-  F2P={len(t['FAIL_TO_PASS']):<3} {t['instance_id']}")
        if len(out) >= want:
            break

    json.dump(out, open(dst, "w"))
    print(f"\nselected {len(out)} tasks across {len(per)} repos -> {dst}")
    print(f"candidates after filters: {len(cands)} of {len(rows)}")
    print("rejected:", dict(rejected.most_common()))
    fs = [patch_shape(t["patch"])[0] for t in out]
    if fs:
        print(f"blast radius of the selection: min {min(fs)}  median "
              f"{sorted(fs)[len(fs)//2]}  max {max(fs)}")


if __name__ == "__main__":
    main()
