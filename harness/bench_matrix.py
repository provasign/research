"""Model x arm change-impact benchmark: does Prism help, per model tier, and
what does it cost in tokens/turns/time?

Matrix: {opus, sonnet, haiku, local-30B} x {baseline (grep+read), prism
(task-altitude change_impact)} x 10 tasks (Java/Go/TS/Python, 8->310 sites)
x 3 trials. Both arms are steered; the ONLY thing that varies within a model
row is the tool. Every answer is oracle-scored (Spoon/SSA/ts-morph/Jedi).

Records per cell: recall, turns, tokens_in/out, wall_s, cost_usd. Cells are
cached (resumable); cloud tiers run via `claude -p` (subscription) so a
rate-limit sleeps and retries when E2E_WAIT_ON_LIMIT=1.

Usage:
  python3 bench_matrix.py --models local,haiku,sonnet,opus --trials 3
  E2E_WAIT_ON_LIMIT=1 python3 bench_matrix.py --models opus   # long cloud run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import ab_agentic_mcp as cloud
import run_local_bench as local
from schema import Task

OUT = Path("runs/bench-matrix")
OUT.mkdir(parents=True, exist_ok=True)

# Stronger baseline steering for the cloud A/B. claude -p occasionally one-shots
# a guessed answer instead of engaging the search tools (1 turn, hallucinated
# sites, recall 0.0). Force genuine tool use so the baseline is a fair,
# tool-using control rather than a lazy guess. Both arms stay properly steered;
# only the tool available differs.
cloud.ARMS["baseline"]["guidance"] = (
    "TOOLS: ripgrep/grep/find and file reads only. This is a real code-search "
    "task — you MUST search the repository before answering; do NOT guess or "
    "answer from memory. Locate the target method, then find EVERY site that must "
    "change: its declaration, overrides/implementations, and every caller — "
    "including callers in OTHER files and indirect ones that do not contain the "
    "method name. Search for the method name AND the types involved, and READ the "
    "files to confirm each site. Submit only sites you have verified by reading "
    "the code; an unverified or guessed answer is wrong."
)

TASKS = [
    "tasks/jackson-jsonnode-get.json",       # java, 8
    "tasks/jackson-settable-set.json",       # java, 22
    "tasks/jackson-writetypeprefix.json",    # java, 38
    "tasks/jackson-serialize.json",          # java, 108
    "tasks/guava-forwarding-delegate.json",  # java, 310
    "tasks/grafana-checkhealth-impact.json", # go, 41
    "tasks/grafana-querydata-impact.json",   # go, 51
    "tasks/typeorm-driver-escape.json",      # ts, 37
    "tasks/django-quotename.json",           # py, 32
]
ARMS = ["baseline", "prism"]           # without Prism / with Prism
LOCAL_MODEL = "qwen3-coder:30b"
PRISM_BIN = str(Path.home() / "bin" / "prism")
RATE_HINTS = ("rate limit", "usage limit", "429", "too many requests",
              "overloaded", "please try again later")


def is_rate_limited(rec: dict) -> bool:
    blob = (str(rec.get("error", "")) + str(rec.get("stderr", ""))).lower()
    return any(h in blob for h in RATE_HINTS)


def is_transient_fail(rec: dict) -> bool:
    """A cloud cell that consumed ZERO input tokens didn't actually run — it is
    the rate-limit fast-fail signature (claude -p returns an empty result JSON,
    num_turns=1, no usage, ~1.5s, and NO error string, so is_rate_limited misses
    it). A genuine run always consumes input tokens, so 0 tokens == retry."""
    return (rec.get("tokens_in") or 0) == 0


def run_cell(model: str, arm: str, task: Task) -> dict:
    if model == "local":
        rec = local.run(arm, task, LOCAL_MODEL)
        rec["backend"] = rec.get("model")   # keep the ollama model id
        rec["model"] = "local"              # normalize the tier label
        return rec
    corpus = Path(task.workdir or task.repo)
    rec = cloud.run_arm(arm, task, corpus, model)   # claude -p
    rec["task"] = task.id
    rec["model"] = model
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="local,haiku,sonnet,opus")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--trials", type=int, default=3)
    a = ap.parse_args()
    wait = os.environ.get("E2E_WAIT_ON_LIMIT") == "1"
    sleep_s = int(os.environ.get("E2E_LIMIT_SLEEP", "1200"))

    tasks = [Task.load(p) for p in TASKS]
    models = a.models.split(",")
    arms = a.arms.split(",")
    print(f"# {len(tasks)} tasks x {arms} x {models} x {a.trials} trials", flush=True)

    for model in models:
        for task in tasks:
            corpus = Path(task.workdir or task.repo)
            if not corpus.exists():
                print(f"  SKIP {task.id}: corpus absent", flush=True)
                continue
            subprocess.run(["git", "-C", str(corpus), "checkout", "-q", task.pin],
                           capture_output=True)
            # The prism arm calls `prism change-impact`, which needs the corpus
            # indexed at THIS commit. Delta-index after checkout (idempotent,
            # fast once warm). Without this the first call errors "not indexed".
            if "prism" in arms:
                subprocess.run([PRISM_BIN, "index", str(corpus)],
                               capture_output=True, timeout=900)
            for arm in arms:
                for trial in range(1, a.trials + 1):
                    f = OUT / f"{task.id}.{model}.{arm}.t{trial}.json"
                    if f.exists():
                        continue
                    attempt = 0
                    while True:
                        rec = run_cell(model, arm, task)
                        if model == "local" or not wait:
                            break
                        attempt += 1
                        if is_rate_limited(rec) and attempt <= 8:
                            print(f"  RATE-LIMITED {f.name} (try {attempt}); sleep {sleep_s}s",
                                  flush=True)
                            time.sleep(sleep_s)
                            continue
                        if is_transient_fail(rec) and attempt <= 12:
                            # 0-token fast-fail (transient per-minute limit): short backoff
                            print(f"  TRANSIENT-FAIL {f.name} (0 tokens, try {attempt}); sleep 90s",
                                  flush=True)
                            time.sleep(90)
                            continue
                        break
                    rec["trial"] = trial
                    rec["lang"] = task.lang
                    rec["gt"] = len(task.ground_truth)
                    f.write_text(json.dumps(rec, indent=2))
                    print(f"  {model:7} {arm:8} {task.id[:26]:26} t{trial} "
                          f"recall={rec.get('recall')} turns={rec.get('turns')} "
                          f"in={rec.get('tokens_in', 0) // 1000}k "
                          f"out={rec.get('tokens_out', 0)} "
                          f"{rec.get('wall_s')}s", flush=True)
    print("# done", flush=True)


if __name__ == "__main__":
    main()
