#!/usr/bin/env python3
"""Pre-release multi-trial check of the prism arm (ranking-signal fix RC).

Runs N fresh trials of the prism arm per model — no caching — and prints
recall/turns/tokens per trial. Release gate: recall must not regress from
the recorded 1.00 / 3-turn baseline (runs/ab-agentic/*.prism.json).
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ab_agentic_mcp import run_arm  # noqa: E402
from schema import Task  # noqa: E402
import subprocess

TASK = "tasks/jackson-jsonnode-get.json"
TRIALS = 3
OUT = Path("runs/ab-agentic/rc-trials")
OUT.mkdir(parents=True, exist_ok=True)

task = Task.load(TASK)
corpus = Path(task.workdir or task.repo)
subprocess.run(["git", "-C", str(corpus), "checkout", "-q", task.pin], capture_output=True)

for model in ("haiku", "opus"):
    print(f"\n== {task.id} / {model} / prism arm x{TRIALS} (fresh) ==")
    for t in range(1, TRIALS + 1):
        rec = run_arm("prism", task, corpus, model)
        rec["task"], rec["model"], rec["trial"] = task.id, model, t
        (OUT / f"{task.id}.{model}.prism.t{t}.json").write_text(json.dumps(rec, indent=2))
        if "error" in rec:
            print(f"  t{t}: ERROR {rec['error'][:100]}")
        else:
            print(f"  t{t}: recall={rec['recall']}  precision={rec['precision']}  "
                  f"turns={rec['turns']}  tok_in={rec['tokens_in']//1000}k  "
                  f"cost=${rec['cost_usd']:.2f}  wall={rec['wall_s']}s")
