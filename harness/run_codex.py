"""Run the Mode-A change-impact tasks through Codex (GPT) and score them.

Cross-model-family arm of the study: Claude Code was the agent for Claude models;
Codex (`codex exec`) is the agent for GPT models. We reuse the SAME task prompts
(`arms.py`), the SAME independent oracle scoring (`score.py` + `rescore_java.py`),
and write the SAME per-run record format as `run.py`, so GPT results drop straight
into `agg_jackson.py` / `rescore_java.py` and the paper's tables.

Per (task x arm x trial) it invokes:
  codex exec -m <model> -s workspace-write -C <workdir> --json \
       -o <last_message_file> --output-schema codex-answer-schema.json \
       --skip-git-repo-check -c approval_policy="never" "<arm prompt>"

Records land in runs/<task>/<model>/  (model = the --model value, e.g. gpt-5-codex).

NOTES / things to verify against your Codex version (CLI evolves):
  * Sandbox: workspace-write lets `prism` open its sqlite/.grove WAL (read-only
    sandbox can fail on the WAL write). The Mode-A prompt forbids edits and we
    never read the working tree (we score the model's *answer*), so writes are
    harmless; pass --reset-corpus to `git checkout` the corpus between runs if you
    want to be strict about drift.
  * Approval: `-c approval_policy="never"` keeps it non-interactive. If your build
    still prompts, switch CODEX_EXTRA to use
    `--dangerously-bypass-approvals-and-sandbox` (note: that removes the sandbox).
  * Tool trace: parsed best-effort from the --json event stream to set
    `graph_used` (did it call prism?). The raw JSONL is saved next to each run so
    you can refine the parser if your event schema differs -- run ONE cell with
    --print-cmd / a single trial first and inspect runs/<task>/<model>/*.events.jsonl.

Arm enforcement: like the Claude soft-gate, T-vs-G is enforced by prompt + a
post-hoc trace check (`violation` is set if the G arm never called prism, or the T
arm did). For a hard gate, pass --hide-prism-from-T (strips prism's dir from PATH
for T-arm runs).

Usage:
  python run_codex.py --task tasks/jackson-serialize.json --arms T G --trials 5 \
      --model gpt-5-codex --workdir ~/gvg-corpus/jackson-databind
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path

from arms import ARMS, PRISM_BIN
from schema import Answer, Task
from score import score

HARNESS_DIR = Path(__file__).resolve().parent
RUNS_DIR = HARNESS_DIR / "runs"
SCHEMA = HARNESS_DIR / "codex-answer-schema.json"
RUN_TIMEOUT_S = 1800  # GPT large-task enumeration can run long
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
USAGE_POLL_S = 900
USAGE_BUFFER_S = 120
USAGE_MAX_WAIT_S = 8 * 24 * 3600


def build_cmd(model: str | None, workdir: Path, lastmsg: Path) -> list[str]:
    cmd = [CODEX_BIN, "exec",
           "-s", "workspace-write",
           "-C", str(workdir),
           "--json",
           "--skip-git-repo-check",
           "-o", str(lastmsg),
           "--output-schema", str(SCHEMA),
           "-c", 'approval_policy="never"']
    if model:
        cmd += ["-m", model]
    extra = os.environ.get("CODEX_EXTRA", "").split()
    cmd += extra
    return cmd


def _env_for_arm(arm: str, hide_prism_from_t: bool) -> dict:
    env = dict(os.environ)
    if arm == "T" and hide_prism_from_t:
        # Hard gate: remove prism's directory from PATH for the text arm.
        prism_dir = str(Path(PRISM_BIN).parent)
        env["PATH"] = os.pathsep.join(
            p for p in env.get("PATH", "").split(os.pathsep) if p != prism_dir
        )
    return env


def _parse_events(stdout: str) -> dict:
    """Best-effort: pull shell commands and usage out of the --json stream.

    Codex emits JSONL events; command-execution events vary by version. We scan
    each line for a command string under common keys and, failing that, treat any
    line mentioning a `prism` invocation as graph use. Usage/cost fields are also
    schema-flexible: newer CLIs may put them on a final result event, while older
    builds nest them under payloads. The raw stream is saved so the parser can be
    tuned to your version.
    """
    cmds: list[str] = []
    usage: dict | None = None
    total_cost_usd = None
    duration_ms = None
    num_turns = None
    error_messages: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # walk the object for a command-ish field
        cmd = _find_command(obj)
        if cmd:
            cmds.append(cmd)
        found_usage = _find_usage(obj)
        if found_usage:
            usage = _merge_usage(usage, found_usage)
        total_cost_usd = _latest_number(obj, total_cost_usd,
                                        ("total_cost_usd", "cost_usd", "usd"))
        duration_ms = _latest_number(obj, duration_ms,
                                     ("duration_ms", "elapsed_ms"))
        num_turns = _latest_number(obj, num_turns,
                                   ("num_turns", "turn_count", "turns"))
        err = _find_error_message(obj)
        if err:
            error_messages.append(err)
    bins = sorted({_lead_bin(c) for c in cmds if c})
    graph_used = any("prism" in c for c in cmds)
    return {
        "tool_cmds": cmds,
        "tools_used": bins,
        "graph_used": graph_used,
        "usage": usage,
        "total_cost_usd": total_cost_usd,
        "duration_ms": duration_ms,
        "num_turns": int(num_turns) if isinstance(num_turns, float)
        and num_turns.is_integer() else num_turns,
        "errors": error_messages,
    }


def _find_command(obj) -> str | None:
    """Recursively find a shell-command string in a Codex event object."""
    if isinstance(obj, dict):
        for k in ("command", "cmd", "shell_command"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v
        for k in ("args", "argv"):
            v = obj.get(k)
            if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                return " ".join(v)
        v = obj.get("input")
        if isinstance(v, dict):
            r = _find_command(v)
            if r:
                return r
        for v in obj.values():
            r = _find_command(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_command(v)
            if r:
                return r
    return None


def _lead_bin(command: str) -> str:
    try:
        tok = shlex.split(command.strip()) if command.strip() else [""]
    except ValueError:
        tok = command.strip().split() or [""]
        return Path(tok[0]).name
    if len(tok) >= 3 and Path(tok[0]).name in ("zsh", "bash", "sh") and tok[1] == "-lc":
        return _lead_bin(tok[2])
    if any(Path(t).name == "prism" for t in tok):
        return "prism"
    return Path(tok[0]).name


_USAGE_KEYS = {
    "input_tokens", "prompt_tokens",
    "output_tokens", "completion_tokens",
    "total_tokens",
    "cached_input_tokens", "cache_read_input_tokens",
    "reasoning_output_tokens",
}


def _find_usage(obj) -> dict | None:
    """Recursively find a token-usage object and normalize common aliases."""
    if isinstance(obj, dict):
        for k in ("usage", "token_usage", "usage_metadata"):
            v = obj.get(k)
            if isinstance(v, dict):
                usage = _normalize_usage(v)
                if usage:
                    return usage
        usage = _normalize_usage(obj)
        if usage:
            return usage
        for v in obj.values():
            usage = _find_usage(v)
            if usage:
                return usage
    elif isinstance(obj, list):
        for v in obj:
            usage = _find_usage(v)
            if usage:
                return usage
    return None


def _normalize_usage(d: dict) -> dict:
    usage = {
        k: v for k, v in d.items()
        if k in _USAGE_KEYS and isinstance(v, (int, float))
    }
    if "prompt_tokens" in usage and "input_tokens" not in usage:
        usage["input_tokens"] = usage["prompt_tokens"]
    if "completion_tokens" in usage and "output_tokens" not in usage:
        usage["output_tokens"] = usage["completion_tokens"]
    if ("total_tokens" not in usage
            and "input_tokens" in usage and "output_tokens" in usage):
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    return usage


def _merge_usage(current: dict | None, new: dict) -> dict:
    """Keep the largest observed counters; Codex streams often repeat snapshots."""
    if current is None:
        return dict(new)
    merged = dict(current)
    for k, v in new.items():
        old = merged.get(k)
        if isinstance(old, (int, float)):
            merged[k] = max(old, v)
        else:
            merged[k] = v
    return merged


def _latest_number(obj, current, keys: tuple[str, ...]):
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, (int, float)):
                current = v
            elif isinstance(v, str):
                try:
                    current = float(v)
                except ValueError:
                    pass
        for v in obj.values():
            current = _latest_number(v, current, keys)
    elif isinstance(obj, list):
        for v in obj:
            current = _latest_number(v, current, keys)
    return current


def _find_error_message(obj) -> str | None:
    if not isinstance(obj, dict):
        return None
    typ = obj.get("type")
    if typ in ("error", "turn.failed"):
        msg = obj.get("message")
        if isinstance(msg, str):
            return msg
        err = obj.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return err["message"]
    return None


def _usage_limit_reset(env: dict) -> float | None:
    """Return reset epoch for a Codex usage-cap error, -1 if unknown, else None."""
    blob = "\n".join(env.get("errors") or [])
    blob += "\n" + (env.get("_stderr") or "")
    blob += "\n" + (env.get("_answer_text") or "")
    lower = blob.lower()
    if not (
        "usage limit" in lower
        or ("rate limit" in lower and ("reached" in lower or "exceeded" in lower))
        or "too many requests" in lower
    ):
        return None
    for pat in (
        r'"resetsAt"\s*:\s*"?(\d{10,13})"?',
        r'"reset_at"\s*:\s*"?(\d{10,13})"?',
        r"reset[^0-9]{0,20}(\d{10,13})",
        r"\|(\d{10,13})",
    ):
        m = re.search(pat, blob, re.IGNORECASE)
        if m:
            ts = int(m.group(1))
            return ts / 1000 if ts > 1e12 else float(ts)
    return -1.0


def _wait_for_usage_reset(reset: float, out: Path, task: Task,
                          model: str | None, tag: str) -> float:
    """Pause until Codex usage resets; write a heartbeat for long sleeps."""
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
        "task": task.id,
        "model": model or "codex-default",
        "cell": tag,
        "paused_at": now,
        "resume_target": target,
        "resume_target_iso": eta,
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


def run_codex_agent(prompt: str, arm: str, workdir: Path, model: str | None,
                    lastmsg: Path, events_path: Path, hide_prism: bool) -> dict:
    cmd = build_cmd(model, workdir, lastmsg)
    cmd.append(prompt)
    env = _env_for_arm(arm, hide_prism)
    t0 = time.time()
    timed_out = False
    proc = subprocess.Popen(cmd, cwd=str(workdir), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env,
                            start_new_session=True)
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
    events_path.write_text(stdout)  # keep raw stream for trace-parser tuning
    ev = _parse_events(stdout)
    # answer text: prefer the structured last-message file, fall back to stdout
    answer_text = ""
    if lastmsg.exists():
        answer_text = lastmsg.read_text()
    if not answer_text.strip():
        answer_text = stdout
    ev.update({"_wall_s": round(wall, 2), "_stderr": (stderr or "")[-2000:],
               "_timed_out": timed_out, "_answer_text": answer_text,
               "_returncode": proc.returncode})
    return ev


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arms", nargs="+", default=["T", "G"])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--model", default=None,
                    help="GPT model id for codex -m (e.g. gpt-5-codex). Default: "
                         "codex's configured default. Record dir = this value.")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--pace", type=float, default=0)
    ap.add_argument("--hide-prism-from-t", action="store_true",
                    help="hard gate: strip prism's dir from PATH for T-arm runs")
    ap.add_argument("--reset-corpus", action="store_true",
                    help="git checkout the corpus between runs (guard vs edits)")
    ap.add_argument("--print-cmd", action="store_true",
                    help="print the codex command for one cell and exit (no run)")
    ap.add_argument("--reparse-events", action="store_true",
                    help="refresh trace/cost fields in existing run JSON from saved events")
    args = ap.parse_args()

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir
    workdir = Path(task.workdir or task.repo)
    model_dir = args.model or "codex-default"
    out = RUNS_DIR / task.id / model_dir
    out.mkdir(parents=True, exist_ok=True)

    if args.reparse_events:
        changed = _reparse_event_records(out)
        print(f"[reparse-events] {changed} record(s) updated -> {out}")
        return

    if args.print_cmd:
        cmd = build_cmd(args.model, workdir, out / "EXAMPLE.lastmsg.txt")
        cmd.append(ARMS[args.arms[0]].prompt(task.prompt, task.lang))
        print(" ".join(repr(c) if " " in c else c for c in cmd))
        return

    cards, errored = [], []
    for arm_name in args.arms:
        arm = ARMS[arm_name]
        for trial in range(1, args.trials + 1):
            tag = f"{arm_name}.t{trial}"
            if args.pace and not (arm_name == args.arms[0] and trial == 1):
                time.sleep(args.pace)
            if args.reset_corpus:
                subprocess.run(["git", "-C", str(workdir), "checkout", "--", "."],
                               check=False, capture_output=True)
            print(f"[codex] {task.id} {model_dir} {tag}")
            lastmsg = out / f"{tag}.lastmsg.txt"
            events = out / f"{tag}.events.jsonl"
            usage_waited = 0.0
            while True:
                for stale in (lastmsg, events):
                    try:
                        stale.unlink()
                    except FileNotFoundError:
                        pass
                env = run_codex_agent(arm.prompt(task.prompt, task.lang), arm_name,
                                      workdir, args.model, lastmsg, events,
                                      args.hide_prism_from_t)

                err = None
                if env["_timed_out"]:
                    err = "timeout"
                elif env.get("errors") and not lastmsg.exists():
                    err = "codex_error"
                elif env["_returncode"] not in (0, None) and not env["_answer_text"].strip():
                    err = f"codex_exit_{env['_returncode']}"

                reset = _usage_limit_reset(env) if err else None
                if reset is None:
                    break
                usage_waited += _wait_for_usage_reset(reset, out, task,
                                                      args.model, tag)
                if usage_waited >= USAGE_MAX_WAIT_S:
                    print(f"      giving up: usage cap not cleared after "
                          f"{usage_waited / 3600:.1f}h")
                    break
                if args.reset_corpus:
                    subprocess.run(["git", "-C", str(workdir), "checkout", "--", "."],
                                   check=False, capture_output=True)

            answer = Answer.parse(env["_answer_text"])
            card = score(task, answer, arm_name, trial)

            if err:
                rec = {"task_id": task.id, "arm": arm_name, "trial": trial,
                       "status": "error", "error": err,
                       "stderr": env["_stderr"], "wall_s": env["_wall_s"],
                       "codex_errors": env.get("errors", [])}
                (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
                errored.append(rec)
                print(f"      ERROR ({err}) -- excluded")
                continue

            graph_used = env["graph_used"]
            violation = None
            if arm_name == "T" and graph_used:
                violation = "T arm used the graph"
            elif arm_name == "G" and not graph_used:
                violation = "G arm never used the graph"

            rec = {
                "status": "ok",
                "model": model_dir,
                **card.to_dict(),
                "cost": {"wall_s": env["_wall_s"],
                         "duration_ms": env.get("duration_ms"),
                         "num_turns": env.get("num_turns"),
                         "usage": env.get("usage"),
                         "total_cost_usd": env.get("total_cost_usd")},
                "tools_used": env["tools_used"],
                "graph_used": graph_used,
                "violation": violation,
                "tool_trace": [{"tool": "Bash", "bin": _lead_bin(c), "detail": c[:200]}
                               for c in env["tool_cmds"]],
                "answer": {"sites": [str(s) for s in answer.sites],
                           "complete": answer.complete,
                           "unresolved": answer.unresolved},
            }
            (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
            cards.append(rec)
            warn = f"  !! {violation}" if violation else ""
            print(f"      recall={card.recall} graph_used={graph_used} "
                  f"tools={env['tools_used']}{warn}")

    (out / "summary.json").write_text(
        json.dumps({"ok": cards, "errored": errored}, indent=2) + "\n")
    print(f"\n[done] {len(cards)} scored, {len(errored)} errored -> {out}")
    print("Next: python rescore_java.py --task", args.task,
          "(line->method fix); then python agg_jackson.py")


def _reparse_event_records(out: Path) -> int:
    changed = 0
    for events in sorted(out.glob("[TGV].t*.events.jsonl")):
        rec_path = events.with_suffix("").with_suffix(".json")
        if not rec_path.exists():
            continue
        rec = json.loads(rec_path.read_text())
        env = _parse_events(events.read_text())
        if env.get("errors"):
            rec.update({
                "status": "error",
                "error": "codex_error",
                "codex_errors": env["errors"],
                "tools_used": env["tools_used"],
                "graph_used": env["graph_used"],
                "tool_trace": [
                    {"tool": "Bash", "bin": _lead_bin(c), "detail": c[:200]}
                    for c in env["tool_cmds"]
                ],
            })
            rec_path.write_text(json.dumps(rec, indent=2) + "\n")
            changed += 1
            continue
        if rec.get("status") != "ok":
            continue
        rec["tools_used"] = env["tools_used"]
        rec["graph_used"] = env["graph_used"]
        rec["tool_trace"] = [
            {"tool": "Bash", "bin": _lead_bin(c), "detail": c[:200]}
            for c in env["tool_cmds"]
        ]
        cost = rec.setdefault("cost", {})
        if env.get("usage") is not None:
            cost["usage"] = env["usage"]
        if env.get("total_cost_usd") is not None:
            cost["total_cost_usd"] = env["total_cost_usd"]
        if env.get("duration_ms") is not None:
            cost["duration_ms"] = env["duration_ms"]
        if env.get("num_turns") is not None:
            cost["num_turns"] = env["num_turns"]
        rec_path.write_text(json.dumps(rec, indent=2) + "\n")
        changed += 1
    return changed


if __name__ == "__main__":
    main()
