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
    """Best-effort: pull shell commands out of the --json event stream.

    Codex emits JSONL events; command-execution events vary by version. We scan
    each line for a command string under common keys and, failing that, treat any
    line mentioning a `prism` invocation as graph use. The raw stream is saved so
    the parser can be tuned to your version.
    """
    cmds: list[str] = []
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
    bins = sorted({_lead_bin(c) for c in cmds if c})
    graph_used = any("prism" in c for c in cmds)
    return {"tool_cmds": cmds, "tools_used": bins, "graph_used": graph_used}


def _find_command(obj) -> str | None:
    """Recursively find a shell-command string in a Codex event object."""
    if isinstance(obj, dict):
        for k in ("command", "cmd", "args", "shell_command", "input"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                return " ".join(v)
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
    tok = command.strip().split() or [""]
    return Path(tok[0]).name


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
    args = ap.parse_args()

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir
    workdir = Path(task.workdir or task.repo)
    model_dir = args.model or "codex-default"
    out = RUNS_DIR / task.id / model_dir
    out.mkdir(parents=True, exist_ok=True)

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
            env = run_codex_agent(arm.prompt(task.prompt, task.lang), arm_name,
                                  workdir, args.model, lastmsg, events,
                                  args.hide_prism_from_t)

            err = None
            if env["_timed_out"]:
                err = "timeout"
            elif env["_returncode"] not in (0, None) and not env["_answer_text"].strip():
                err = f"codex_exit_{env['_returncode']}"

            answer = Answer.parse(env["_answer_text"])
            card = score(task, answer, arm_name, trial)

            if err:
                rec = {"task_id": task.id, "arm": arm_name, "trial": trial,
                       "status": "error", "error": err,
                       "stderr": env["_stderr"], "wall_s": env["_wall_s"]}
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
                "cost": {"wall_s": env["_wall_s"], "duration_ms": None,
                         "num_turns": None, "usage": None, "total_cost_usd": None},
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


if __name__ == "__main__":
    main()
