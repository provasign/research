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
    base = RUNS_DIR / task.id
    # Opus lives at runs/<task>/; other models at runs/<task>/<model>/.
    dirs = [base] + sorted(
        d for d in base.iterdir() if d.is_dir() and (d / "summary.json").exists()
    )
    total = 0
    for out in dirs:
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
            (out / f"{c['arm']}.t{c['trial']}.json").write_text(
                json.dumps(c, indent=2) + "\n")
        (out / "summary.json").write_text(json.dumps(summ, indent=2) + "\n")
        label = out.name if out != base else "opus"
        total += len(ok)
        print(f"  [{label}] rescored {len(ok)} runs")
    print(f"[rescored] {total} runs across {len(dirs)} model dir(s) in {base}")


if __name__ == "__main__":
    main()
