"""End-to-end benchmark runner: 4 arms x 3 models over validated 2026 tasks.

One cell = (task, arm, model). Each cell runs the agent in a throwaway worktree
at base_commit, captures its NON-test diff, and scores it with docker_eval
(apply test_patch + agent diff -> FAIL_TO_PASS pass & no PASS_TO_PASS regress).
The model is the only thing that varies across model rows; the arm is the only
thing that varies across arm columns (tool exposure from ab_endtoend_arms).

Backends (no ANTHROPIC_API_KEY here):
  - sonnet/haiku : `claude -p` (subscription) with the arm's --allowedTools +
    --mcp-config -- the proven ab_agentic_mcp pattern, now end-to-end.
  - local        : run_local_agent.py over ollama (no rate limit).

Resumable + auto-pause: every finished cell writes a result JSON and is skipped
on restart. On an Anthropic usage/rate-limit the cloud path writes a pause
marker (runs/e2e/PAUSED.json) and the process exits 42; the caller re-invokes
after the reset (ScheduleWakeup). Run local first (free, always completes), then
cloud.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import docker_eval
import run_local_agent
from ab_endtoend_arms import ARMS

OUT = Path("runs/e2e")
OUT.mkdir(parents=True, exist_ok=True)
RATE_HINTS = ("rate limit", "usage limit", "429", "too many requests",
              "overloaded", "please try again later")


class RateLimited(Exception):
    pass


def _worktree(task):
    repo = docker_eval._repo_dir(task)
    wt = Path(tempfile.mkdtemp(prefix="e2e-run-"))
    docker_eval._sh("git", "-C", str(repo), "worktree", "add", "--force",
                    "--detach", str(wt), task["base_commit"], timeout=300)
    return repo, wt


# Index/tool artifacts the context tools drop into the worktree. They MUST be
# excluded from the agent diff: git apply is atomic, so a single binary stub
# (e.g. .grove/grove.db) makes the whole patch unappliable and silently zeroes
# the score (this invalidated every prism-arm cell before 2026-07-14).
TOOL_ARTIFACTS = (".grove", ".codegraph", ".prism", "prism.yaml", ".p.diff",
                  ".shale")  # mason's evidence trail


def _agent_diff(wt: Path, task) -> str:
    """The agent's change to NON-test files (test_patch is the harness's job)."""
    docker_eval._sh("git", "-C", str(wt), "add", "-A", check=False)
    excludes = [f":(exclude){m}" for m in task["test_modules"]]
    excludes += [f":(exclude){a}" for a in TOOL_ARTIFACTS]
    return docker_eval._sh("git", "-C", str(wt), "diff", "--cached", "--", ".",
                           *excludes, check=False)


def _index_graph(wt: Path, arm: str):
    if arm.startswith("prism"):
        subprocess.run(["prism", "index", str(wt)], capture_output=True, timeout=300)
    if arm.startswith("codegraph"):
        subprocess.run(["codegraph", "index", str(wt)], capture_output=True, timeout=300)


TASK_TAIL = ("\n\nFix the SOURCE code in this repository so the issue is resolved "
             "and the project's tests pass. Edit source files only; do NOT modify "
             "any test files. Make the smallest change that works, then stop.")


def _run_cloud(model: str, arm: str, wt: Path, task) -> dict:
    spec = ARMS[arm]
    prompt = spec["guidance"] + "\n\nISSUE:\n" + task["problem_statement"] + TASK_TAIL
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--allowedTools", *spec["allowed"]]
    if spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"], "--strict-mcp-config"]
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=1800)
    blob = (r.stdout + r.stderr).lower()
    if r.returncode != 0 and any(h in blob for h in RATE_HINTS):
        raise RateLimited(blob[-300:])
    rec = {"wall_s": round(time.monotonic() - t0, 1)}
    try:
        j = json.loads(r.stdout)
        rec.update(turns=j.get("num_turns"), cost_usd=j.get("total_cost_usd"))
    except Exception:
        if any(h in blob for h in RATE_HINTS):
            raise RateLimited(blob[-300:])
        rec["agent_error"] = (r.stderr or r.stdout)[-200:]
    return rec


def _run_mason(wt: Path, task) -> dict:
    """The competent-local-harness arm: mason (Prism baked in, self-indexes).
    Output is teed to a visible per-cell log; capped at 30 min — the SAME
    budget the cloud arms get (subprocess timeout 1800). The old 600s cap
    killed 11/15 mason v0.28 cells mid-flight: the completeness gate and
    prepare obligations do strictly more engine work per task, and a slow
    local model pays for it in wall-clock, not correctness."""
    prompt = task["problem_statement"] + TASK_TAIL
    log = OUT / f"{task['instance_id']}.mason.transcript.txt"
    t0 = time.monotonic()
    timed_out = False
    with open(log, "w") as fh:
        p = subprocess.Popen(["mason", "--yes", "--model", "ollama:qwen3-coder:30b",
                              prompt], cwd=wt, stdout=fh, stderr=subprocess.STDOUT, text=True)
        try:
            p.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(); timed_out = True
    return {"wall_s": round(time.monotonic() - t0, 1), "timed_out": timed_out,
            "transcript": str(log)}


def _save_diff(task, model: str, arm: str, tag: str, diff: str):
    """Persist the agent diff next to the cell JSON so failed fixes can be
    inspected after the worktree is gone."""
    (OUT / f"{task['instance_id']}.{model}.{arm}{tag}.diff").write_text(diff)


def run_cell(task: dict, arm: str, model: str, tag: str = "") -> dict:
    repo, wt = _worktree(task)
    try:
        if arm == "mason":
            meta = _run_mason(wt, task)
            diff = _agent_diff(wt, task)
            _save_diff(task, model, arm, tag, diff)
            docker_eval._sh("git", "-C", str(repo), "worktree", "remove",
                            "--force", str(wt), check=False)
            sc = docker_eval.score(task, diff) if diff.strip() else {"resolved": False, "empty_diff": True}
            return {"task": task["instance_id"], "arm": arm, "model": model,
                    "kind": task.get("kind"), "resolved": sc.get("resolved"),
                    "diff_lines": diff.count("\n"), **meta, "score": sc}
        _index_graph(wt, arm)
        if model == "local":
            prompt = task["problem_statement"] + TASK_TAIL
            res = run_local_agent.run("qwen3-coder:30b", arm, str(wt), prompt)
            meta = {"turns": res.get("turns"), "wall_s": res.get("wall_s"),
                    "trace": res.get("trace"), "agent_error": res.get("error")}
        else:
            meta = _run_cloud(model, arm, wt, task)
        diff = _agent_diff(wt, task)
        _save_diff(task, model, arm, tag, diff)
    finally:
        docker_eval._sh("git", "-C", str(repo), "worktree", "remove", "--force",
                        str(wt), check=False)
    sc = docker_eval.score(task, diff) if diff.strip() else {"resolved": False, "empty_diff": True}
    return {"task": task["instance_id"], "arm": arm, "model": model,
            "kind": task.get("kind"), "resolved": sc.get("resolved"),
            "diff_lines": diff.count("\n"), **meta, "score": sc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--models", default="local,haiku,sonnet")
    ap.add_argument("--arms", default="baseline,prism_g,prism_gstar,codegraph")
    ap.add_argument("--trials", type=int, default=1,
                    help="trials per cell; trial 1 keeps the unsuffixed cell name "
                         "(cache-compatible), trials 2..N write .t<n>.json")
    a = ap.parse_args()
    tasks = [json.loads((Path("tasks-e2e") / f"{i}.json").read_text())
             for i in json.loads(Path(a.manifest).read_text())]
    print(f"# {len(tasks)} tasks x {a.arms} x {a.models}", flush=True)
    import os
    wait_on_limit = os.environ.get("E2E_WAIT_ON_LIMIT") == "1"
    sleep_s = int(os.environ.get("E2E_LIMIT_SLEEP", "1200"))
    for model in a.models.split(","):
        for task in tasks:
            for arm in a.arms.split(","):
                for trial in range(1, a.trials + 1):
                    tag = "" if trial == 1 else f".t{trial}"
                    f = OUT / f"{task['instance_id']}.{model}.{arm}{tag}.json"
                    if f.exists():
                        print(f"  (cached) {f.name}", flush=True); continue
                    while True:  # retry the SAME cell across a rate-limit window
                        try:
                            rec = run_cell(task, arm, model, tag)
                            break
                        except RateLimited as e:
                            (OUT / "PAUSED.json").write_text(json.dumps(
                                {"at": f.name, "reason": str(e)[:200], "ts": int(time.time())}))
                            if not wait_on_limit:
                                print(f"  PAUSED at {f.name}: rate-limited", flush=True)
                                sys.exit(42)
                            print(f"  RATE-LIMITED at {f.name}; sleeping {sleep_s}s then retrying",
                                  flush=True)
                            time.sleep(sleep_s)
                    (OUT / "PAUSED.json").unlink(missing_ok=True)
                    rec["trial"] = trial
                    f.write_text(json.dumps(rec, indent=2))
                    print(f"  {model:7} {arm:12} {task['instance_id'][-24:]:24} "
                          f"t{trial} resolved={rec['resolved']} turns={rec.get('turns')} "
                          f"wall={rec.get('wall_s')}s", flush=True)
    print("# done", flush=True)


if __name__ == "__main__":
    main()
