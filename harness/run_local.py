"""Run the Mode-A change-impact tasks through a LOCAL model (Ollama) and score them.

The local tier is a genuinely weak, open-weights point (Qwen2.5-Coder etc.), the
low-capability end where the paper's capability-equalizer predicts the graph
should help most -- *if* the model can drive the graph at all.

Why a bespoke loop instead of Codex --oss: (1) a HARD arm gate -- the T arm is
never given the graph tool, so it structurally cannot touch it (the study's other
tiers use soft gates); (2) local models emit tool calls as freeform text (often
malformed) rather than the structured tool_calls field, so we use a simple, robust
JSON text protocol we parse ourselves. Records match run.py's format, so results
drop into rescore_java.py / agg_jackson.py unchanged (model dir is sanitized:
'qwen2.5-coder:14b' -> 'qwen2.5-coder-14b').

Protocol (one action per turn): the model outputs ONE json object, either
  {"shell": "<command>"}      # command's leading binary must be in the arm allowlist
or the final answer
  {"sites": [...], "complete": bool, "unresolved": [...]}
We execute allowed commands read-only in the workdir and feed back the output
(capped), looping to --max-turns. The T allowlist has no `prism`; a T attempt to
run it is refused and flagged (hard gate). graph_used = any executed prism command.

Usage:
  python run_local.py --task tasks/jackson-serialize.json --arms T G --trials 5 \
      --model qwen2.5-coder:14b --workdir ~/gvg-corpus/jackson-databind
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from arms import PRISM_BIN
from schema import Answer, Task
from score import score

HARNESS_DIR = Path(__file__).resolve().parent
RUNS_DIR = HARNESS_DIR / "runs"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_TURNS = 40
TOOL_OUT_CAP = 4000     # chars of tool output fed back per turn
NUM_CTX = 16384         # ollama context window (fits capped tool outputs)
CMD_TIMEOUT = 60

# Per-arm allowlist of leading binaries. The hard gate: T has no prism.
ALLOW = {
    "T": {"rg", "grep", "find", "sed", "cat", "ls", "head", "tail", "wc", "awk"},
    "G": {"prism", Path(PRISM_BIN).name, "rg", "cat", "sed", "head", "tail"},
    "V": {"rg", "grep", "find", "sed", "cat", "ls", "head", "tail", "wc", "prism",
          Path(PRISM_BIN).name},
}

TASK_FRAME = """\
You are answering a code-context question about a {lang} repository. This is a \
LOCALIZATION / IMPACT analysis task, NOT a coding task: do NOT edit any file. \
Determine the COMPLETE set of functions/methods that must CHANGE for the issue.

ISSUE:
{prompt}
"""

PROTOCOL = """\
You work in a strict one-action-per-turn loop. Each turn output EXACTLY ONE JSON \
object and NOTHING else.

To investigate, run a shell command (read-only):
  {{"shell": "<command>"}}
Allowed commands (leading program must be one of): {allow}.
I will reply with the command's output. Use {tool_hint}.

Be persistent: investigate over MANY turns. If a search returns nothing, try \
DIFFERENT terms (a call site rarely contains the exact text you searched). Do not \
give up after one command, and never finalize an EMPTY list.

Only when you have actually found the sites, output the FINAL answer:
  {{"sites": ["<relpath>:<Symbol>", ...], "complete": true|false, "unresolved": [ ... ]}}
Each site is "<repo-relative-path>:<FunctionOrMethodName>" (receiver optional). A \
missed site is a broken fix; set "complete" honestly. Output ONLY the JSON object.\
"""

TOOL_HINT = {
    "T": "ripgrep/grep to find symbols and read files to confirm which functions must change",
    "G": (f"the `{PRISM_BIN}` call-graph CLI to TRAVERSE: "
          f"`{PRISM_BIN} references <Name>`, `{PRISM_BIN} lookup <Sym>`, "
          f"`{PRISM_BIN} query \"<task>\" --include graph --format text`; rg only to find an anchor"),
    "V": "ripgrep to find candidates, then prism to verify completeness before finalizing",
}


def build_system(task: Task, arm: str) -> str:
    allow = ", ".join(sorted(ALLOW[arm]))
    return (TASK_FRAME.format(lang=task.lang.capitalize(), prompt=task.prompt)
            + "\n" + PROTOCOL.format(allow=allow, tool_hint=TOOL_HINT[arm]))


def ollama_chat(model: str, messages: list[dict]) -> str:
    body = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": 0.0, "num_ctx": NUM_CTX},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read()).get("message", {}).get("content", "") or ""


def last_json(text: str) -> dict | None:
    dec = json.JSONDecoder()
    best = None
    i = 0
    while True:
        idx = text.find("{", i)
        if idx < 0:
            break
        try:
            obj, _ = dec.raw_decode(text, idx)
            if isinstance(obj, dict) and ("shell" in obj or "sites" in obj):
                best = obj
        except json.JSONDecodeError:
            pass
        i = idx + 1
    return best


def _lead(command: str) -> str:
    toks = command.strip().split()
    return Path(toks[0]).name if toks else ""


def run_shell(command: str, arm: str, workdir: Path) -> tuple[str, str]:
    """Return (leading_bin, output). Refuses binaries not in the arm allowlist."""
    toks = command.strip().split()
    lead = Path(toks[0]).name if toks else ""
    if lead not in ALLOW[arm]:
        return lead, f"[refused] '{lead}' is not permitted for this arm."
    try:
        p = subprocess.run(command, shell=True, cwd=str(workdir),
                           capture_output=True, text=True, timeout=CMD_TIMEOUT)
        out = (p.stdout or "") + (("\n[stderr] " + p.stderr) if p.stderr else "")
    except subprocess.TimeoutExpired:
        out = "[timeout]"
    return lead, out[:TOOL_OUT_CAP]


def run_one(task: Task, arm: str, model: str, workdir: Path) -> dict:
    messages = [{"role": "system", "content": build_system(task, arm)},
                {"role": "user", "content": "Begin. Output your first JSON action."}]
    trace: list[dict] = []
    answer_text = ""
    empty_pushbacks = 0
    seen: dict[str, str] = {}   # command -> output (dedup weak-agent loops)
    repeats = 0
    t0 = time.time()
    for _ in range(MAX_TURNS):
        content = ollama_chat(model, messages)
        obj = last_json(content)
        if obj is None:
            messages.append({"role": "assistant", "content": content[:1000]})
            messages.append({"role": "user",
                             "content": 'Output ONLY one JSON object: a {"shell": "..."} '
                                        'action or the final {"sites": [...], ...} answer.'})
            continue
        if "sites" in obj:
            # Arm-neutral guard: don't accept a premature EMPTY answer without
            # having actually investigated -- push back up to twice.
            if not obj.get("sites") and empty_pushbacks < 2:
                empty_pushbacks += 1
                messages.append({"role": "assistant", "content": json.dumps(obj)})
                messages.append({"role": "user",
                                 "content": "Your site list is empty. Keep investigating "
                                            "with the tools (try different search terms) "
                                            "and do not finalize until you have found the "
                                            "sites."})
                continue
            answer_text = json.dumps(obj)
            break
        cmd = str(obj.get("shell", ""))
        if cmd in seen:  # weak agents loop on a failing command; nudge, don't rerun
            repeats += 1
            if repeats >= 6:
                break  # not converging -- stop wasting turns, finalize what we have
            note = ("[note] You already ran this exact command; its output is "
                    "unchanged (shown below). Try a DIFFERENT command (e.g. "
                    f"`{PRISM_BIN} references <BareName>`) or finalize.\n" + seen[cmd])
            trace.append({"tool": "Bash", "bin": _lead(cmd), "detail": cmd[:200]})
            messages.append({"role": "assistant", "content": json.dumps({"shell": cmd})})
            messages.append({"role": "user", "content": f"OUTPUT:\n{note}"})
            continue
        lead, out = run_shell(cmd, arm, workdir)
        seen[cmd] = out
        trace.append({"tool": "Bash", "bin": lead, "detail": cmd[:200]})
        messages.append({"role": "assistant", "content": json.dumps({"shell": cmd})})
        messages.append({"role": "user", "content": f"OUTPUT:\n{out}"})
    wall = round(time.time() - t0, 2)
    tools_used = sorted({t["bin"] for t in trace if t["bin"]})
    graph_used = any("prism" in t["detail"] for t in trace)
    return {"answer_text": answer_text, "tool_trace": trace, "tools_used": tools_used,
            "graph_used": graph_used, "wall_s": wall}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arms", nargs="+", default=["T", "G"])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--model", required=True, help="ollama model, e.g. qwen2.5-coder:14b")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--pace", type=float, default=0)
    args = ap.parse_args()

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir
    workdir = Path(task.workdir or task.repo)
    model_dir = args.model.replace(":", "-").replace("/", "-")
    out = RUNS_DIR / task.id / model_dir
    out.mkdir(parents=True, exist_ok=True)

    cards, errored = [], []
    for arm in args.arms:
        for trial in range(1, args.trials + 1):
            tag = f"{arm}.t{trial}"
            if args.pace and not (arm == args.arms[0] and trial == 1):
                time.sleep(args.pace)
            print(f"[local] {task.id} {model_dir} {tag}")
            try:
                env = run_one(task, arm, args.model, workdir)
            except Exception as e:  # network/model failure -> exclude, don't score 0
                rec = {"task_id": task.id, "arm": arm, "trial": trial,
                       "status": "error", "error": f"{type(e).__name__}: {e}"}
                (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
                errored.append(rec)
                print(f"      ERROR ({rec['error']}) -- excluded")
                continue

            answer = Answer.parse(env["answer_text"])
            card = score(task, answer, arm, trial)
            graph_used = env["graph_used"]
            violation = None
            if arm == "T" and graph_used:
                violation = "T arm used the graph"
            elif arm == "G" and not graph_used:
                violation = "G arm never used the graph"
            rec = {
                "status": "ok", "model": model_dir, **card.to_dict(),
                "cost": {"wall_s": env["wall_s"], "duration_ms": None,
                         "num_turns": len(env["tool_trace"]), "usage": None,
                         "total_cost_usd": None},
                "tools_used": env["tools_used"], "graph_used": graph_used,
                "violation": violation, "tool_trace": env["tool_trace"],
                "answer": {"sites": [str(s) for s in answer.sites],
                           "complete": answer.complete, "unresolved": answer.unresolved},
            }
            (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
            cards.append(rec)
            warn = f"  !! {violation}" if violation else ""
            print(f"      recall={card.recall} graph_used={graph_used} "
                  f"turns={len(env['tool_trace'])} tools={env['tools_used']}{warn}")

    (out / "summary.json").write_text(
        json.dumps({"ok": cards, "errored": errored}, indent=2) + "\n")
    print(f"\n[done] {len(cards)} scored, {len(errored)} errored -> {out}")
    print("Next: python rescore_java.py --task", args.task, "; python agg_jackson.py")


if __name__ == "__main__":
    main()
