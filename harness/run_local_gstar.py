"""Run the G* arm with a local model via Ollama, backed by the REAL Grove engine.

This replaces run_local_hitool.py (which used the Spoon-powered change_impact.py
and was therefore tautological). Here the change_impact tool calls
`prism change-impact` — the Grove graph engine — independently of the Spoon
oracle that produces ground truth.  Scoring against the oracle is therefore a
genuine measurement.

Model's job: identify the method from the issue → call change_impact once →
submit the returned sites.  Same impact-routing scaffold as the hitool runner
(force turn-0 tool_choice="required") since local models emit tool_calls
unreliably.

Outputs to runs/<task>/<model>-gstar/  (e.g. qwen3-coder-30b-gstar/).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from schema import Answer, Site, Task
from score import score

RUNS_DIR = Path(__file__).resolve().parent / "runs"
PRISM_BIN = Path.home() / "bin" / "prism"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_TURNS = 8
NUM_CTX = 16384


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

CHANGE_IMPACT_TOOL = {
    "type": "function",
    "function": {
        "name": "change_impact",
        "description": (
            "Return the COMPLETE set of sites that must change if the given "
            "method's signature changes: its declaration, every "
            "override/implementation, and every resolved call site. "
            "Input the method as 'Class.method' or 'Class.method(ParamType,...)', "
            "e.g. 'JsonNode.get(int)' or 'JsonSerializer.serialize'. "
            "Returns a list of 'relpath/File.java:methodName' strings ready "
            "to pass directly to submit_answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    },
}

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": "Submit the FINAL list of change-sites and stop.",
        "parameters": {
            "type": "object",
            "properties": {
                "sites": {"type": "array", "items": {"type": "string"}},
                "complete": {"type": "boolean"},
                "unresolved": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sites", "complete", "unresolved"],
        },
    },
}

SYSTEM = """\
You are answering a code-context question about a {lang} repository.
Determine the COMPLETE set of methods that must CHANGE for the issue below.

ISSUE:
{prompt}

You have a change_impact tool that, given the method named in the issue, \
returns the ENTIRE change-set in one call as a ready-to-submit list.
Call change_impact with the method symbol, then call submit_answer with \
exactly the sites it returns — copy them verbatim, do not add or remove any."""


# ---------------------------------------------------------------------------
# Prism backend
# ---------------------------------------------------------------------------

def prism_change_impact(symbol: str, workdir: Path) -> list[str]:
    """Call `prism change-impact '<symbol>' .` and return sites as file:name strings."""
    result = subprocess.run(
        [str(PRISM_BIN), "change-impact", symbol, "."],
        capture_output=True, text=True, cwd=workdir, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prism change-impact failed: {result.stderr[:400]}")
    data = json.loads(result.stdout)
    sites: list[str] = []
    for group in ("declarations", "family", "callers"):
        for sym in data.get(group, []):
            fp = sym.get("filePath") or sym.get("file", "")
            name = sym.get("name", "")
            if fp and name:
                sites.append(f"{fp}:{name}")
    return sites


# ---------------------------------------------------------------------------
# Ollama chat
# ---------------------------------------------------------------------------

def ollama_chat(model: str, messages: list, tools: list, tool_choice=None) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": NUM_CTX},
    }
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read()).get("message", {}) or {}


# ---------------------------------------------------------------------------
# Single-trial runner
# ---------------------------------------------------------------------------

def run_one(task: Task, model: str, workdir: Path) -> dict:
    all_tools = [CHANGE_IMPACT_TOOL, SUBMIT_TOOL]
    messages = [
        {"role": "system", "content": SYSTEM.format(
            lang=task.lang.capitalize(), prompt=task.prompt)},
        {"role": "user", "content": "Begin."},
    ]
    trace: list[dict] = []
    answer: Answer | None = None
    tool_used = False
    t0 = time.time()

    for turn in range(MAX_TURNS):
        # Turn 0: force change_impact (invocation wall — local models are unreliable).
        # Subsequent turns: free choice so the model can submit.
        if turn == 0:
            msg = ollama_chat(model, messages, [CHANGE_IMPACT_TOOL], tool_choice="required")
        else:
            msg = ollama_chat(model, messages, all_tools)

        calls = msg.get("tool_calls") or []
        if not calls:
            # Model emitted text instead of a tool call — nudge it.
            messages.append({"role": "assistant", "content": (msg.get("content") or "")[:400]})
            messages.append({"role": "user", "content":
                             "Call change_impact with the method symbol, then submit_answer."})
            continue

        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": calls,
        })

        done = False
        for c in calls:
            fn = c.get("function", {})
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}

            if fn_name == "submit_answer":
                answer = Answer(
                    sites=[Site.parse(s) for s in (raw_args.get("sites") or []) if str(s).strip()],
                    complete=bool(raw_args.get("complete", False)),
                    unresolved=[str(u) for u in (raw_args.get("unresolved") or [])],
                )
                done = True
                break

            if fn_name == "change_impact":
                symbol = str(raw_args.get("symbol", "")).strip()
                tool_used = True
                try:
                    sites = prism_change_impact(symbol, workdir)
                    # Return pre-formatted site strings so the model can relay verbatim.
                    tool_result = json.dumps({
                        "sites": sites,
                        "count": len(sites),
                        "note": "Copy these sites verbatim to submit_answer.",
                    })
                except Exception as e:
                    tool_result = json.dumps({"error": str(e)})
                    sites = []
                trace.append({
                    "tool": "change_impact",
                    "bin": "prism",
                    "detail": symbol,
                    "sites_returned": len(sites) if tool_used else 0,
                })
                messages.append({
                    "role": "tool",
                    "tool_name": "change_impact",
                    "content": tool_result,
                })
            else:
                messages.append({
                    "role": "tool",
                    "tool_name": fn_name,
                    "content": "[unknown tool — call change_impact then submit_answer]",
                })

        if done:
            break

    if answer is None:
        answer = Answer(sites=[], complete=False, unresolved=[])

    return {
        "answer": answer,
        "trace": trace,
        "tool_used": tool_used,
        "wall_s": round(time.time() - t0, 2),
        "num_turns": len(trace),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--model", default="qwen3-coder:30b")
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()

    if not PRISM_BIN.exists():
        raise SystemExit(f"prism binary not found at {PRISM_BIN}")

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir

    workdir = Path(task.workdir or task.repo).expanduser()
    model_slug = args.model.replace(":", "-").replace("/", "-") + "-gstar"
    out_dir = RUNS_DIR / task.id / model_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[local-gstar] task={task.id}  model={args.model}  workdir={workdir}")
    print(f"              prism={PRISM_BIN}  out={out_dir}")

    for trial in range(1, args.trials + 1):
        print(f"  trial {trial}/{args.trials} ...", flush=True)
        env = run_one(task, args.model, workdir)
        card = score(task, env["answer"], "L", trial)

        rec = {
            "status": "ok",
            "model": model_slug,
            **card.to_dict(),
            "cost": {
                "wall_s": env["wall_s"],
                "num_turns": env["num_turns"],
                "usage": None,
                "total_cost_usd": 0.0,   # local = free
                "duration_ms": None,
            },
            "tools_used": ["prism_change_impact"] if env["tool_used"] else [],
            "graph_used": env["tool_used"],
            "change_impact_used": env["tool_used"],
            "violation": None if env["tool_used"] else "local-gstar never used change_impact",
            "tool_trace": env["trace"],
            "answer": {
                "sites": [str(s) for s in env["answer"].sites],
                "complete": env["answer"].complete,
                "unresolved": env["answer"].unresolved,
            },
        }
        (out_dir / f"L.t{trial}.json").write_text(json.dumps(rec, indent=2) + "\n")
        print(f"      recall={card.recall:.4f}  precision={card.precision:.4f}"
              f"  tool_used={env['tool_used']}  turns={env['num_turns']}"
              f"  wall={env['wall_s']}s")

    print(f"[local-gstar] done → {out_dir}")


if __name__ == "__main__":
    main()
