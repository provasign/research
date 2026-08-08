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
import os
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import docker_eval
import fanout_eval
import seeded_refactor
import java_eval
import run_local_agent
from ab_endtoend_arms import ARMS

OUT = Path("runs/e2e")
OUT.mkdir(parents=True, exist_ok=True)


def _is_java(task) -> bool:
    return task.get("lang") == "java"


def _repo_for(task) -> Path:
    """Java tasks live in java_eval.REPO_DIR (e.g. ~/gvg-corpus/jackson-databind);
    Python tasks use docker_eval's e2e-2026 clone convention."""
    if _is_java(task):
        return java_eval.REPO_DIR[task["repo"]]
    return docker_eval._repo_dir(task)


def _score(task, diff: str) -> dict:
    """Kind- and language-aware scoring: fanout tasks are scored on
    green + gold-file coverage (fanout_eval); the rest on fail->pass."""
    if not diff.strip():
        return {"resolved": False, "empty_diff": True}
    if task.get("kind") == "fanout":
        return fanout_eval.score(task, diff)
    if task.get("kind") == "seeded_refactor":
        return seeded_refactor.score(_repo_for(task), task, diff)
    if _is_java(task):
        return java_eval.score(java_eval.REPO_DIR[task["repo"]], task, diff)
    return docker_eval.score(task, diff)
RATE_HINTS = ("rate limit", "usage limit", "429", "too many requests",
              "overloaded", "please try again later")


class RateLimited(Exception):
    pass


def _worktree(task):
    repo = _repo_for(task)
    wt = Path(tempfile.mkdtemp(prefix="e2e-run-"))
    docker_eval._sh("git", "-C", str(repo), "worktree", "add", "--force",
                    "--detach", str(wt), task["base_commit"], timeout=300)
    return repo, wt


# Index/tool artifacts the context tools drop into the worktree. They MUST be
# excluded from the agent diff: git apply is atomic, so a single binary stub
# (e.g. .grove/grove.db) makes the whole patch unappliable and silently zeroes
# the score (this invalidated every prism-arm cell before 2026-07-14).
TOOL_ARTIFACTS = (".grove", ".engine-b", ".prism", "prism.yaml", ".p.diff",
                  ".shale")  # mason's evidence trail


def _agent_diff(wt: Path, task) -> str:  # noqa: D401
    """The agent's change to NON-test files (test_patch is the harness's job)."""
    docker_eval._sh("git", "-C", str(wt), "add", "-A", check=False)
    excludes = [f":(exclude){m}" for m in task["test_modules"]]
    excludes += [f":(exclude){a}" for a in TOOL_ARTIFACTS]
    return docker_eval._sh("git", "-C", str(wt), "diff", "--cached", "--", ".",
                           *excludes, check=False)


def _index_graph(wt: Path, arm: str):
    if arm.startswith("prism"):
        r = subprocess.run(["prism", "index", str(wt)], capture_output=True,
                            text=True, timeout=300)
        if r.returncode != 0:
            print(f"  [index] WARN prism index rc={r.returncode}: {r.stderr[-200:]}")
    if arm.startswith("engine-b") or arm.startswith("codegraph"):
        # engine-b requires `init` to CREATE the index; `index` only rebuilds an
        # already-initialized one and errors out on a fresh worktree ("Run
        # engine-b init first"). With capture_output that failure is silent and
        # the arm degrades to grep-only — a crippled strawman. Use init, and fail
        # loudly if the .engine-b index did not materialize so a broken cell is
        # never scored as a real engine-b result.
        r = subprocess.run(["codegraph", "init", str(wt)], capture_output=True,
                           text=True, timeout=600)
        if not (wt / ".codegraph").exists():
            raise RuntimeError(
                f"codegraph init did not create .codegraph in {wt} "
                f"(rc={r.returncode}): {r.stdout[-300:]} {r.stderr[-300:]}")


TASK_TAIL = ("\n\nFix the SOURCE code in this repository so the issue is resolved "
             "and the project's tests pass. Edit source files only; do NOT modify "
             "any test files. Make the smallest change that works, then stop.")


# A seeded refactor needs its own closing instruction: the generic tail
# ("make the SMALLEST change that works, then stop") tells an agent facing a
# deliberately wide change to do the minimum — measured, the first baseline
# cell stopped after 4 turns. It also promises a test run that never happens
# here; the oracle is `mvn compile` over main sources only.
SEEDED_TAIL = ("\n\nUpdate the source so the project COMPILES again. Every "
               "implementation of the changed method and every call site must be "
               "updated — the change is deliberately wide, so do not stop at the "
               "first few. Verify with `mvn -q compile`. Edit main sources only; "
               "do not modify test files.")


def _run_cloud(model: str, arm: str, wt: Path, task) -> dict:
    spec = ARMS[arm]
    tail = SEEDED_TAIL if task.get("kind") == "seeded_refactor" else TASK_TAIL
    prompt = spec["guidance"] + "\n\nISSUE:\n" + task["problem_statement"] + tail
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--strict-mcp-config",
           "--allowedTools", *spec["allowed"]]
    if spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"]]
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
    rec["tool_trace"] = _tool_trace_for(wt)
    return rec


def _tool_trace_for(wt: Path) -> dict:
    """Tool-call counts for the session that just ran in worktree wt, mined
    from the claude CLI's own transcript (~/.claude/projects/<cwd-slug>/).
    The -p JSON output carries no per-tool trace; without this the routing
    question ('did the agent grep or graph?') needs manual excavation —
    measured, it was the most useful column of the 2026-08-06 analysis.
    Best-effort: {} when the transcript is not found."""
    # macOS: mkdtemp returns /var/... but the claude CLI records the RESOLVED
    # cwd (/private/var/...) — try both slugs (measured: the unresolved slug
    # matched nothing and every cell's trace came back empty).
    # Match by the worktree's BASENAME, not a computed slug: the CLI rewrites
    # more than slashes (temp names containing "_" come back hyphenated), so
    # any slug we compute here can silently miss. Globbing the basename is
    # robust to whatever transformation it applies to the prefix.
    base = Path(wt).name.replace("_", "-")
    hits = sorted(Path.home().glob(f".claude/projects/*{base}"),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    if hits:
        pdir = hits[0]
        counts: dict = {}
        scope_text = 0
        for f in pdir.glob("*.jsonl"):
            for line in f.open():
                try:
                    j = json.loads(line)
                except Exception:
                    continue
                if j.get("type") != "assistant":
                    continue
                for c in ((j.get("message") or {}).get("content") or []):
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        counts[c["name"]] = counts.get(c["name"], 0) + 1
                        if c["name"].endswith("prism_search") and \
                                (c.get("input") or {}).get("scope") == "text":
                            scope_text += 1
        if scope_text:
            counts["_prism_search_scope_text"] = scope_text
        if counts:
            return counts
    candidates = [str(wt), str(Path(wt).resolve()), "/private" + str(wt)]
    # The CLI flushes its session transcript asynchronously, so a read the
    # instant the process exits can find nothing (measured: 2 cells came back
    # with an empty trace and were briefly misread as "the agent made no
    # searches"). Retry briefly before giving up.
    pdir = None
    for _ in range(10):
        for c in candidates:
            d = Path.home() / ".claude" / "projects" / c.replace("/", "-")
            if d.exists() and any(d.glob("*.jsonl")):
                pdir = d
                break
        if pdir:
            break
        time.sleep(1)
    if pdir is None:
        return {"_trace_unavailable": 1}
    counts: dict = {}
    scope_text = 0
    for f in pdir.glob("*.jsonl"):
        for line in f.open():
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("type") != "assistant":
                continue
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    counts[c["name"]] = counts.get(c["name"], 0) + 1
                    if c["name"].endswith("prism_search") and \
                            (c.get("input") or {}).get("scope") == "text":
                        scope_text += 1
    if scope_text:
        counts["_prism_search_scope_text"] = scope_text
    return counts


def _run_mason(wt: Path, task, arm: str = "mason") -> dict:
    """The competent-local-harness arm: mason (Prism baked in, self-indexes).
    Output is teed to a visible per-cell log; capped at 30 min — the SAME
    budget the cloud arms get (subprocess timeout 1800). The old 600s cap
    killed 11/15 mason v0.28 cells mid-flight: the completeness gate and
    prepare obligations do strictly more engine work per task, and a slow
    local model pays for it in wall-clock, not correctness.

    Two arms share this driver so the ONLY variable is context delivery:
      - "mason":       default (code_context whole-neighborhood dump)
      - "mason_walk":  MASON_WALK=1 (graph_focus part-by-part walk)
    MASON_BIN selects the binary (default "mason") so an experimental build can
    be A/B'd against the released one."""
    import os as _os
    prompt = task["problem_statement"] + TASK_TAIL
    log = OUT / f"{task['instance_id']}.{arm}.transcript.txt"
    binary = _os.environ.get("MASON_BIN", "mason")
    env = dict(_os.environ)
    if arm == "mason_walk":
        env["MASON_WALK"] = "1"
    else:
        env.pop("MASON_WALK", None)
    t0 = time.monotonic()
    timed_out = False
    with open(log, "w") as fh:
        p = subprocess.Popen([binary, "--yes", "--model", "ollama:qwen3-coder:30b",
                              prompt], cwd=wt, stdout=fh, stderr=subprocess.STDOUT,
                             text=True, env=env)
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
        if arm in ("mason", "mason_walk"):
            meta = _run_mason(wt, task, arm)
            diff = _agent_diff(wt, task)
            _save_diff(task, model, arm, tag, diff)
            docker_eval._sh("git", "-C", str(repo), "worktree", "remove",
                            "--force", str(wt), check=False)
            sc = _score(task, diff)
            return {"task": task["instance_id"], "arm": arm, "model": model,
                    "kind": task.get("kind"), "resolved": sc.get("resolved"),
                    "diff_lines": diff.count("\n"), **meta, "score": sc}
        if task.get("kind") == "seeded_refactor":
            # The agent starts from the broken build, not from base.
            seeded_refactor.apply_mutation(wt, task["mutation"])
        _index_graph(wt, arm)
        if model == "local":
            prompt = task["problem_statement"] + TASK_TAIL
            res = run_local_agent.run(
                os.environ.get("LOCAL_MODEL", "qwen3-coder-ctx16k"),
                arm, str(wt), prompt)
            meta = {"turns": res.get("turns"), "wall_s": res.get("wall_s"),
                    "trace": res.get("trace"), "agent_error": res.get("error")}
        else:
            meta = _run_cloud(model, arm, wt, task)
        diff = _agent_diff(wt, task)
        _save_diff(task, model, arm, tag, diff)
    finally:
        docker_eval._sh("git", "-C", str(repo), "worktree", "remove", "--force",
                        str(wt), check=False)
    sc = _score(task, diff)
    return {"task": task["instance_id"], "arm": arm, "model": model,
            "kind": task.get("kind"), "resolved": sc.get("resolved"),
            "diff_lines": diff.count("\n"), **meta, "score": sc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--models", default="local,haiku,sonnet")
    ap.add_argument("--arms", default="baseline,prism_g,prism_gstar,engine-b")
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
                        except Exception as e:  # noqa: BLE001
                            # Fault-isolate a single bad cell (engine-b index failure,
                            # maven timeout, apply reject) so a 30h unattended run does
                            # not die on one task. Record the error and move on.
                            import traceback
                            rec = {"task": task["instance_id"], "arm": arm, "model": model,
                                   "resolved": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                            print(f"  ERROR {f.name}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                            traceback.print_exc()
                            break
                    (OUT / "PAUSED.json").unlink(missing_ok=True)
                    rec["trial"] = trial
                    f.write_text(json.dumps(rec, indent=2))
                    print(f"  {model:7} {arm:12} {task['instance_id'][-24:]:24} "
                          f"t{trial} resolved={rec['resolved']} turns={rec.get('turns')} "
                          f"wall={rec.get('wall_s')}s", flush=True)
    print("# done", flush=True)


if __name__ == "__main__":
    main()
