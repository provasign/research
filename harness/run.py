"""Run agent arms over Mode-A tasks and score them (design §7).

For each (task x arm x trial) this drives the `claude` CLI headlessly with the
arm's enforced tool allowlist, parses the structured answer, scores it against
the PR-derived ground truth, and writes a per-run record plus a transcript.

Non-destructive: the agent runs in a git *worktree* checked out at the task pin
(the shared corpus checkout is never moved). Graph arms pre-index the worktree
with prism so indexing time is not charged to the timed answer.

Usage:
  python run.py --task tasks/gin-4645.json --arms T G --trials 1
  python run.py --task tasks/gin-4645.json --arms T G V --trials 5
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from arms import ARMS, PRISM_BIN
from schema import Answer, Task
from score import score

HARNESS_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = Path("/tmp/gvg-corpus")
RUNS_DIR = HARNESS_DIR / "runs"
RUN_TIMEOUT_S = 600


def ensure_worktree(task: Task) -> Path:
    """Check out task.repo at task.pin in an isolated worktree (idempotent)."""
    wt = WORKTREE_ROOT / f"{task.id}"
    if (wt / ".git").exists():
        return wt
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    # Prune any stale registration, then add the worktree at the pin.
    subprocess.run(["git", "-C", task.repo, "worktree", "prune"], check=False)
    subprocess.run(
        ["git", "-C", task.repo, "worktree", "add", "--detach", str(wt), task.pin],
        check=True,
        capture_output=True,
        text=True,
    )
    return wt


def preindex(workdir: Path) -> None:
    """Warm the prism index for the worktree (graph arms only)."""
    subprocess.run(
        [PRISM_BIN, "index", str(workdir)],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        check=False,
    )


def run_agent(prompt: str, allowed: list[str], workdir: Path) -> dict:
    """Invoke `claude -p` headlessly; return parsed JSON envelope + latency."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--strict-mcp-config",  # ignore filesystem .mcp.json; arms own the tools
        "--allowedTools",
        ",".join(allowed),
    ]
    t0 = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_S,
    )
    wall = time.time() - t0
    env: dict = {}
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        env = {"result": proc.stdout, "_parse_error": True}
    env["_wall_s"] = round(wall, 2)
    env["_stderr"] = proc.stderr[-2000:]
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arms", nargs="+", default=["T", "G"])
    ap.add_argument("--trials", type=int, default=1)
    args = ap.parse_args()

    task = Task.load(args.task)
    workdir = ensure_worktree(task)
    out = RUNS_DIR / task.id
    out.mkdir(parents=True, exist_ok=True)

    needs_graph = any(a in ("G", "V") for a in args.arms)
    if needs_graph:
        print(f"[preindex] {workdir} via {PRISM_BIN}")
        preindex(workdir)

    cards = []
    for arm_name in args.arms:
        arm = ARMS[arm_name]
        for trial in range(1, args.trials + 1):
            tag = f"{arm_name}.t{trial}"
            print(f"[run] {task.id} {tag} (tools: {','.join(arm.allowed_tools)})")
            env = run_agent(arm.prompt(task.prompt), arm.allowed_tools, workdir)
            result_text = env.get("result", "")
            answer = Answer.parse(result_text)
            card = score(task, answer, arm_name, trial)

            (out / f"{tag}.transcript.txt").write_text(result_text)
            rec = {
                **card.to_dict(),
                "cost": {
                    "wall_s": env.get("_wall_s"),
                    "duration_ms": env.get("duration_ms"),
                    "num_turns": env.get("num_turns"),
                    "usage": env.get("usage"),
                    "total_cost_usd": env.get("total_cost_usd"),
                },
                "answer": {
                    "sites": [str(s) for s in answer.sites],
                    "complete": answer.complete,
                    "unresolved": answer.unresolved,
                },
            }
            (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
            cards.append(rec)
            print(
                f"      recall={card.recall} precision={card.precision} "
                f"f1={card.f1} overconfident={card.overconfident} "
                f"gap={card.surfaced_gap}"
            )

    summary = out / "summary.json"
    summary.write_text(json.dumps(cards, indent=2) + "\n")
    print(f"\n[done] {len(cards)} runs -> {summary}")
    _print_table(cards)


def _print_table(cards: list[dict]) -> None:
    print(f"\n{'arm.trial':<10} {'recall':>7} {'prec':>7} {'f1':>7} "
          f"{'overconf':>9} {'gap':>5} {'turns':>6} {'wall_s':>7}")
    for c in cards:
        cost = c.get("cost", {})
        print(
            f"{c['arm']+'.t'+str(c['trial']):<10} "
            f"{c['recall']:>7} {c['precision']:>7} {c['f1']:>7} "
            f"{str(c['overconfident']):>9} {str(c['surfaced_gap']):>5} "
            f"{str(cost.get('num_turns')):>6} {str(cost.get('wall_s')):>7}"
        )


if __name__ == "__main__":
    main()
