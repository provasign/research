"""Re-grade every stored snapshot with the current graders.

The reason this exists: grading is deterministic and offline, so when an oracle
bug is found mid-study the fix does NOT require re-running a single agent. The
snapshots are the evidence; the score is a pure function of them. Re-grading is
free and, unlike re-running, cannot introduce fresh LLM noise.

Run it only when no cell is executing — it is CPU-heavy and would otherwise
inflate the wall-clock of an in-flight turn, which is a headline metric.

  python3 -m tickr_harness.regrade          # both conditions
  python3 -m tickr_harness.regrade small
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tickr_harness import graders  # noqa: E402

ROOT = Path.home() / "tickr-ab"


def regrade(cond: str) -> None:
    sfx = "" if cond == "small" else f"-{cond}"
    out = ROOT / f"results{sfx}"
    snaps = ROOT / f"snapshots{sfx}"
    if not out.is_dir():
        print(f"[{cond}] no results")
        return
    recs = sorted(out.glob("*--*.json"))
    print(f"[{cond}] re-grading {len(recs)} records")
    changed = 0
    for p in recs:
        rec = json.loads(p.read_text())
        snap = snaps / f"{rec['arm']}-t{rec['trial']}--{rec['turn_id']}"
        if not snap.is_dir():
            print(f"  MISSING snapshot for {p.name}")
            continue
        before = rec["grade"]["conformance"]["score"], rec["grade"]["broken_sites"]
        t0 = time.monotonic()
        rec["grade"] = graders.grade(snap, rec["turn"])
        rec["grade_s"] = round(time.monotonic() - t0, 1)
        rec["regraded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        after = rec["grade"]["conformance"]["score"], rec["grade"]["broken_sites"]
        p.write_text(json.dumps(rec, indent=2))
        if before != after:
            changed += 1
            print(f"  {rec['arm']}-t{rec['trial']} {rec['turn_id']}: "
                  f"conf {before[0]:.3f}->{after[0]:.3f}  "
                  f"broken {before[1]}->{after[1]}")
    print(f"[{cond}] {changed} record(s) changed")


if __name__ == "__main__":
    for c in (sys.argv[1:] or ["small", "large"]):
        regrade(c)
