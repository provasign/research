"""Demonstrate: a weak/local model reaches a COMPLETE change-set in ONE call when
the graph is exposed as a high-altitude change_impact() tool -- the fix the
run_local*.py experiments motivated (primitives, CLI or MCP, scored 0.0 for the
local 30B because it can't orchestrate a multi-turn traversal).

The model gets ONE investigative tool -- change_impact(symbol) -- plus
submit_answer. Expected interaction: call change_impact with the method named in
the issue, then submit its sites. Model dir suffix '-hitool'.

READ change_impact.py's VALIDITY NOTE: the tool is Spoon-powered (== the GT
engine), so the recall here is tautological and demonstrates the *interaction*
(one-call success by a weak model), NOT a graph-vs-text score. The meaningful
result is the CONTRAST with the same model on primitives (0.0).

Usage:
  python run_local_hitool.py --task tasks/jackson-jsonnode-get.json \
      --model qwen3-coder:30b --workdir ~/gvg-corpus/jackson-databind
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from change_impact import change_impact
from schema import Answer, Site, Task
from score import score

RUNS_DIR = Path(__file__).resolve().parent / "runs"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_TURNS = 8
NUM_CTX = 16384

CHANGE_IMPACT_TOOL = {"type": "function", "function": {
    "name": "change_impact",
    "description": ("Return the COMPLETE set of sites that must change if the given "
                    "method's signature changes: its declaration, every "
                    "override/implementation, and every resolved call site. Input "
                    "the method as 'Class.method(paramTypes)', e.g. "
                    "'JsonNode.get(int)' or 'JsonSerializer.serialize'."),
    "parameters": {"type": "object", "properties": {
        "symbol": {"type": "string"}}, "required": ["symbol"]}}}
SUBMIT = {"type": "function", "function": {
    "name": "submit_answer",
    "description": "Submit the FINAL list of change-sites and stop.",
    "parameters": {"type": "object", "properties": {
        "sites": {"type": "array", "items": {"type": "string"}},
        "complete": {"type": "boolean"},
        "unresolved": {"type": "array", "items": {"type": "string"}}},
        "required": ["sites", "complete", "unresolved"]}}}

SYSTEM = """\
You are answering a code-context question about a {lang} repository. Determine the \
COMPLETE set of methods that must CHANGE for the issue below.

ISSUE:
{prompt}

You have a change_impact tool that, given the method named in the issue, returns \
the entire change-set in one call. Call it with that method, then call \
submit_answer with exactly the sites it returns. Do not omit any."""


def ollama_chat(model, messages, tools, tool_choice=None):
    payload = {"model": model, "messages": messages, "tools": tools,
               "stream": False, "options": {"temperature": 0, "num_ctx": NUM_CTX}}
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read()).get("message", {}) or {}


def run_one(task: Task, model: str, workdir: Path) -> dict:
    tools = [CHANGE_IMPACT_TOOL, SUBMIT]
    messages = [{"role": "system", "content": SYSTEM.format(
        lang=task.lang.capitalize(), prompt=task.prompt)},
        {"role": "user", "content": "Begin."}]
    trace, answer, tool_used = [], None, False
    t0 = time.time()
    for turn in range(MAX_TURNS):
        # Turn 1: an impact-routing scaffold forces the tool (local models emit
        # tool_calls unreliably on their own -- the invocation wall). After the
        # tool result, let the model submit freely.
        if turn == 0:
            msg = ollama_chat(model, messages, [CHANGE_IMPACT_TOOL], tool_choice="required")
        else:
            msg = ollama_chat(model, messages, tools)
        calls = msg.get("tool_calls") or []
        if not calls:
            messages.append({"role": "assistant", "content": msg.get("content", "")[:400]})
            messages.append({"role": "user", "content": "Call change_impact, then submit_answer."})
            continue
        messages.append({"role": "assistant", "content": msg.get("content", "") or "",
                         "tool_calls": calls})
        done = False
        for c in calls:
            fn = c.get("function", {})
            name, args = fn.get("name", ""), fn.get("arguments", {})
            if isinstance(args, str):
                try: args = json.loads(args)
                except json.JSONDecodeError: args = {}
            if name == "submit_answer":
                answer = Answer(sites=[Site.parse(s) for s in (args.get("sites") or []) if str(s).strip()],
                                complete=bool(args.get("complete", False)),
                                unresolved=[str(u) for u in (args.get("unresolved") or [])])
                done = True
                break
            if name == "change_impact":
                tool_used = True
                try:
                    r = change_impact(str(args.get("symbol", "")), workdir)
                    out = json.dumps(r)
                except Exception as e:
                    out = f"[error] {e}"
                trace.append({"tool": "change_impact", "bin": "change_impact",
                              "detail": str(args.get("symbol", ""))[:200]})
                messages.append({"role": "tool", "tool_name": "change_impact", "content": out})
            else:
                messages.append({"role": "tool", "tool_name": name, "content": "[unknown tool]"})
        if done:
            break
    if answer is None:
        answer = Answer(sites=[], complete=False, unresolved=[])
    return {"answer": answer, "trace": trace, "tool_used": tool_used,
            "wall_s": round(time.time() - t0, 2)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--model", required=True)
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir
    workdir = Path(task.workdir or task.repo).expanduser()
    model_dir = args.model.replace(":", "-").replace("/", "-") + "-hitool"
    out = RUNS_DIR / task.id / model_dir
    out.mkdir(parents=True, exist_ok=True)

    for trial in range(1, args.trials + 1):
        print(f"[hitool] {task.id} {model_dir} H.t{trial}")
        env = run_one(task, args.model, workdir)
        card = score(task, env["answer"], "H", trial)
        rec = {"status": "ok", "model": model_dir, **card.to_dict(),
               "cost": {"wall_s": env["wall_s"], "num_turns": len(env["trace"]),
                        "usage": None, "total_cost_usd": None, "duration_ms": None},
               "tools_used": ["change_impact"] if env["tool_used"] else [],
               "graph_used": env["tool_used"], "violation": None,
               "tool_trace": env["trace"],
               "answer": {"sites": [str(s) for s in env["answer"].sites],
                          "complete": env["answer"].complete,
                          "unresolved": env["answer"].unresolved}}
        (out / f"H.t{trial}.json").write_text(json.dumps(rec, indent=2) + "\n")
        print(f"      recall={card.recall} precision={card.precision} "
              f"one_call={len(env['trace'])<=1} turns={len(env['trace'])} "
              f"tool_used={env['tool_used']} wall={env['wall_s']}s")


if __name__ == "__main__":
    main()
