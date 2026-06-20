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
import os
import re
import signal
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
RUN_TIMEOUT_S = 1200  # big enumeration tasks (51 sites/43 pkgs) need ~12min on
# sonnet (measured 740s, 70 turns, valid answer); 600s killed them ~80% done, and
# near-cap API throttling slows runs further. Paired with no-retry-on-timeout.
MAX_ATTEMPTS = 3  # retry transient API/infra failures before recording an error
# Plan *usage* cap (the daily ~5h rolling window and the weekly cap) is NOT a
# transient failure: retrying it back-to-back just burns attempts. We pause the
# whole batch until it resets, then resume the same cell.
USAGE_POLL_S = 900       # reset time unknown -> recheck every 15 min (a capped run fails fast/free)
USAGE_BUFFER_S = 120     # wait this long past a reported reset before resuming
USAGE_MAX_WAIT_S = 8 * 24 * 3600  # safety cap: covers a weekly reset + slack


def ensure_worktree(task: Task) -> Path:
    """Check out task.repo at task.pin in an isolated worktree (idempotent).

    If the task names an existing `workdir`, run there directly (used when the
    repo's git dir is unavailable, e.g. an oracle task built on a worktree)."""
    if task.workdir:
        wt = Path(task.workdir)
        if not wt.exists():
            raise SystemExit(f"task.workdir does not exist: {wt}")
        return wt
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


def _bash_bin(command: str) -> str:
    """Leading binary of a bash command (basename), for trace classification."""
    tok = command.strip().split() or [""]
    return Path(tok[0]).name


def _parse_stream(stdout: str) -> dict:
    """Parse `--output-format stream-json` into the result envelope + tool trace.

    Captures every tool_use the agent issued (name + a short detail) so we can
    *prove* which tools an arm actually touched -- the validity check the paper
    needs (design §10): T must never reach the graph, G must traverse it.
    """
    env: dict = {"result": ""}
    trace: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = obj.get("type")
        if kind == "assistant":
            for block in obj.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                inp = block.get("input", {})
                if name == "Bash":
                    cmd = inp.get("command", "")
                    trace.append(
                        {"tool": name, "bin": _bash_bin(cmd), "detail": cmd[:200]}
                    )
                else:
                    detail = inp.get("pattern") or inp.get("file_path") or ""
                    trace.append({"tool": name, "bin": "", "detail": str(detail)[:200]})
        elif kind == "result":
            env.update(obj)  # result text, usage, total_cost_usd, num_turns, duration_ms
        elif kind == "rate_limit_event":
            info = obj.get("rate_limit_info")
            if info:  # emitted every run; status flips off 'allowed' when capped
                env["rate_limit_info"] = info
    env["tool_trace"] = trace
    env["tools_used"] = sorted({t["bin"] or t["tool"] for t in trace})
    env["graph_used"] = any(
        t["tool"] == "Bash" and "prism" in t["detail"] for t in trace
    )
    return env


def _is_errored(env: dict) -> str | None:
    """Return an error reason if this run never reached the model, else None.

    Distinguishes infra failure (API outage, timeout) from a genuine empty
    answer: an outage shows is_error / zero input tokens / an "API Error"
    banner, and must NOT be scored as recall 0 -- it is excluded and retried.
    """
    if env.get("_timed_out"):
        return "timeout"
    if env.get("is_error"):
        return f"is_error:{env.get('subtype', '?')}"
    result = env.get("result", "") or ""
    if "API Error" in result or "Unable to connect" in result:
        return "api_error"
    usage = env.get("usage") or {}
    if usage.get("input_tokens", 0) == 0 and not env.get("tool_trace"):
        return "no_tokens"
    return None


def _usage_limit_reset(env: dict) -> float | None:
    """If an *errored* run was blocked by the plan usage cap (the rolling
    five_hour window OR the weekly cap), return its reset time as a unix epoch
    -- or -1.0 if capped but no reset time was reported (caller should poll).
    Return None if this is not a usage-cap event.

    Primary signal: the CLI's structured `rate_limit_event`. rate_limit_info is
    emitted on every run with status 'allowed' (or 'allowed_warning' near the
    cap); it flips to a non-allowed state (rejected/blocked/...) when the cap is
    hit, and `resetsAt` is the exact epoch to resume at. `rateLimitType` is
    five_hour|weekly -- we handle both uniformly via resetsAt. Only called on a
    run _is_errored already flagged, so an 'allowed' status on a healthy run
    never reaches here. A text fallback covers older CLIs that lack the event."""
    info = env.get("rate_limit_info") or {}
    status = str(info.get("status", "")).lower()
    if status and not status.startswith("allowed"):  # rejected/blocked/exceeded/...
        reset = info.get("resetsAt")
        try:
            return float(reset) if reset else -1.0
        except (TypeError, ValueError):
            return -1.0
    # Fallback: older CLI surfaces the cap only as text.
    blob = ((env.get("_stderr") or "") + "\n" + (env.get("result") or "")).lower()
    if "usage limit" in blob or ("rate limit" in blob and "reached" in blob):
        for pat in (r"reset[^0-9]{0,12}(\d{10,13})", r"\|(\d{10,13})"):
            m = re.search(pat, blob)
            if m:
                ts = int(m.group(1))
                return ts / 1000 if ts > 1e12 else ts  # ms -> s if needed
        return -1.0
    return None


def _wait_for_usage_reset(reset: float, out: Path, task: Task,
                          model: str | None, tag: str) -> float:
    """Pause until the plan usage cap resets, then return seconds waited.

    Handles both the rolling (daily ~5h) and weekly caps uniformly: whichever
    reset the CLI reports drives the wake time; if unknown we re-probe every
    USAGE_POLL_S (a capped run fails fast and ~free, so polling by retrying is
    cheap). Sleeps in chunks so a multi-day weekly wait survives clock changes,
    and writes a heartbeat file so the pause is visible, not mistaken for a hang."""
    now = time.time()
    if reset and reset > now:
        target = min(reset + USAGE_BUFFER_S, now + USAGE_MAX_WAIT_S)
        kind = "reported reset"
    else:
        target = now + USAGE_POLL_S
        kind = "unknown reset; polling"
    eta = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(target))
    hb = out / ".usage_wait.json"
    hb.write_text(json.dumps({
        "task": task.id, "model": model or "opus", "cell": tag,
        "paused_at": now, "resume_target": target, "resume_target_iso": eta,
        "kind": kind,
    }, indent=2) + "\n")
    print(f"      USAGE LIMIT hit ({kind}); pausing until {eta} "
          f"(~{(target - now) / 3600:.2f}h)", flush=True)
    while True:
        remaining = target - time.time()
        if remaining <= 0:
            break
        time.sleep(min(300, remaining))
    try:
        hb.unlink()
    except FileNotFoundError:
        pass
    return time.time() - now


def run_agent(prompt: str, allowed: list[str], workdir: Path,
              model: str | None = None) -> dict:
    """Invoke `claude -p` headlessly; return result envelope + tool trace.

    Runs in its own process group so a timeout kills the CLI *and* any child
    it spawned (the CLI's own retry/backoff can otherwise outlive a plain
    subprocess timeout)."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",  # per-event stream so we can log the tool sequence
        "--verbose",  # required for stream-json under -p
        "--strict-mcp-config",  # ignore filesystem .mcp.json; arms own the tools
        "--allowedTools",
        ",".join(allowed),
    ]
    if model:  # pin the agent model (weak-model arm: --model haiku/sonnet)
        cmd += ["--model", model]
    t0 = time.time()
    timed_out = False
    proc = subprocess.Popen(
        cmd,
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=RUN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
    wall = time.time() - t0
    env = _parse_stream(stdout)
    if not env.get("result") and stdout and not env.get("tool_trace"):
        env["result"] = stdout  # fallback: stream didn't parse
        env["_parse_error"] = True
    env["_wall_s"] = round(wall, 2)
    env["_stderr"] = (stderr or "")[-2000:]
    env["_timed_out"] = timed_out
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arms", nargs="+", default=["T", "G"])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--model", default=None,
                    help="agent model (e.g. haiku, sonnet). Default = Opus; "
                         "non-default models write to runs/<task>/<model>/")
    ap.add_argument("--workdir", default=None,
                    help="override task.workdir: run in this existing checkout "
                         "(keeps machine-specific paths out of committed tasks)")
    ap.add_argument("--pace", type=float, default=0,
                    help="seconds to sleep between runs (spread load under rate limits)")
    args = ap.parse_args()

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir
    workdir = ensure_worktree(task)
    # Namespace non-default models so the Opus baseline is never overwritten.
    out = RUNS_DIR / task.id / args.model if args.model else RUNS_DIR / task.id
    out.mkdir(parents=True, exist_ok=True)

    needs_graph = any(a in ("G", "V") for a in args.arms)
    if needs_graph:
        print(f"[preindex] {workdir} via {PRISM_BIN}")
        preindex(workdir)

    cards = []
    errored: list[dict] = []
    for arm_name in args.arms:
        arm = ARMS[arm_name]
        for trial in range(1, args.trials + 1):
            tag = f"{arm_name}.t{trial}"
            if args.pace and not (arm_name == args.arms[0] and trial == 1):
                time.sleep(args.pace)  # spread load to stay under rate limits
            print(f"[run] {task.id} {tag} (tools: {','.join(arm.allowed_tools)})")
            # Two failure classes, two policies:
            #  - transient (API outage, timeout, overload): short backoff, up to
            #    MAX_ATTEMPTS, so an outage doesn't masquerade as recall 0.
            #  - plan usage cap (daily/weekly): pause the whole batch until it
            #    resets, then resume the *same* cell -- never counts as an attempt.
            attempt = 0
            usage_waited = 0.0
            while True:
                env = run_agent(arm.prompt(task.prompt), arm.allowed_tools,
                                workdir, model=args.model)
                err = _is_errored(env)
                if not err:
                    break
                reset = _usage_limit_reset(env)
                if reset is not None:
                    usage_waited += _wait_for_usage_reset(
                        reset, out, task, args.model, tag)
                    if usage_waited >= USAGE_MAX_WAIT_S:
                        print(f"      giving up: usage cap not cleared after "
                              f"{usage_waited / 3600:.1f}h")
                        break
                    continue  # resume the same cell; do not consume an attempt
                if err == "timeout":
                    # A timeout is ~deterministic for a given task/model; retrying
                    # just burns another full RUN_TIMEOUT_S (we were wasting 3x).
                    print(f"      timeout after {env.get('_wall_s')}s -- not retried")
                    break
                attempt += 1
                print(f"      attempt {attempt}/{MAX_ATTEMPTS} errored ({err})"
                      + ("; retrying" if attempt < MAX_ATTEMPTS else "; giving up"))
                if attempt >= MAX_ATTEMPTS:
                    break
                time.sleep(20 * attempt)
            result_text = env.get("result", "")
            answer = Answer.parse(result_text)
            card = score(task, answer, arm_name, trial)

            if err:  # record the failure but keep it out of the scored set
                rec = {
                    "task_id": task.id, "arm": arm_name, "trial": trial,
                    "status": "error", "error": err,
                    "stderr": env.get("_stderr", ""), "wall_s": env.get("_wall_s"),
                    # telemetry so a future cap/limit is diagnosable from the record
                    "rate_limit_info": env.get("rate_limit_info"),
                    "result_snippet": (env.get("result") or "")[:300],
                }
                (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
                errored.append(rec)
                print(f"      ERROR ({err}) -- excluded from scoring")
                continue

            # Validity guard (design §10): T must never reach the graph; G must.
            graph_used = env.get("graph_used", False)
            violation = None
            if arm_name == "T" and graph_used:
                violation = "T arm used the graph"
            elif arm_name == "G" and not graph_used:
                violation = "G arm never used the graph"

            (out / f"{tag}.transcript.txt").write_text(result_text)
            rec = {
                "status": "ok",
                "model": args.model or "opus",
                **card.to_dict(),
                "cost": {
                    "wall_s": env.get("_wall_s"),
                    "duration_ms": env.get("duration_ms"),
                    "num_turns": env.get("num_turns"),
                    "usage": env.get("usage"),
                    "total_cost_usd": env.get("total_cost_usd"),
                },
                "tools_used": env.get("tools_used", []),
                "graph_used": graph_used,
                "violation": violation,
                "tool_trace": env.get("tool_trace", []),
                "answer": {
                    "sites": [str(s) for s in answer.sites],
                    "complete": answer.complete,
                    "unresolved": answer.unresolved,
                },
            }
            (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
            cards.append(rec)
            warn = f"  !! {violation}" if violation else ""
            print(
                f"      recall={card.recall} precision={card.precision} "
                f"f1={card.f1} overconfident={card.overconfident} "
                f"gap={card.surfaced_gap} tools={env.get('tools_used')}{warn}"
            )

    summary = out / "summary.json"
    summary.write_text(json.dumps({"ok": cards, "errored": errored}, indent=2) + "\n")
    print(f"\n[done] {len(cards)} scored, {len(errored)} errored -> {summary}")
    if errored:
        print(f"  {len(errored)} run(s) errored (excluded): "
              + ", ".join(f"{e['arm']}.t{e['trial']}({e['error']})" for e in errored))
    _print_table(cards)


def _print_table(cards: list[dict]) -> None:
    print(f"\n{'arm.trial':<10} {'recall':>7} {'prec':>7} {'f1':>7} "
          f"{'overconf':>9} {'gap':>5} {'graph':>6} {'turns':>6} {'wall_s':>7} viol")
    viols = 0
    for c in cards:
        cost = c.get("cost", {})
        v = c.get("violation")
        viols += 1 if v else 0
        print(
            f"{c['arm']+'.t'+str(c['trial']):<10} "
            f"{c['recall']:>7} {c['precision']:>7} {c['f1']:>7} "
            f"{str(c['overconfident']):>9} {str(c['surfaced_gap']):>5} "
            f"{str(c.get('graph_used')):>6} "
            f"{str(cost.get('num_turns')):>6} {str(cost.get('wall_s')):>7} "
            f"{v or ''}"
        )
    if viols:
        print(f"\n  WARNING: {viols} arm-boundary violation(s) -- inspect tool_trace")


if __name__ == "__main__":
    main()
