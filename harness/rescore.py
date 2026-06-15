"""Re-score saved runs against the current scorer, without re-calling the agent.

Reads each ok run's saved answer (sites/complete/unresolved) and the task, then
recomputes the scorecard in place. Use after a scorer change to avoid spending
API budget on a re-run.

Usage: python rescore.py --task tasks/grafana-126004.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema import Answer, Site, Task
from score import score

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    args = ap.parse_args()
    task = Task.load(args.task)
    out = RUNS_DIR / task.id
    summ = json.loads((out / "summary.json").read_text())
    ok = summ["ok"]
    for c in ok:
        ans = c["answer"]
        answer = Answer(
            sites=[Site.parse(s) for s in ans["sites"]],
            complete=ans["complete"],
            unresolved=ans.get("unresolved", []),
        )
        card = score(task, answer, c["arm"], c["trial"])
        c.update(card.to_dict())
        (out / f"{c['arm']}.t{c['trial']}.json").write_text(json.dumps(c, indent=2) + "\n")
        print(f"  {c['arm']}.t{c['trial']}  r={c['recall']} p={c['precision']} "
              f"f1={c['f1']} extra={c['extra']}")
    (out / "summary.json").write_text(json.dumps(summ, indent=2) + "\n")
    print(f"[rescored] {len(ok)} runs in {out}")


if __name__ == "__main__":
    main()
