"""Local-model runner that presents tools as STRUCTURED functions (MCP-style),
not raw CLI strings -- to test whether the tool *interface* is what gates a weak
model's ability to use the code graph.

Motivation: with the raw-CLI loop (run_local.py) qwen3-coder:30b greps well
(text 0.62) but cannot drive prism (graph 0.0) -- it can't recall the exact CLI
syntax (`prism references get`, not `prism references JsonNode.get`). Yet the same
model emits clean structured tool_calls. Prism ships an MCP server; MCP's value is
exactly this: self-documenting, schema-typed tools the model fills in rather than
free-form commands it must remember. Here we emulate that affordance -- structured
function tools dispatched to prism/rg under the hood -- so the ONLY thing that
changes vs run_local.py is the interface. Same scoring, same record format
(model dir suffixed '-mcp' so it sits beside the CLI run for comparison).

Arms (HARD gate -- a tool the arm doesn't get is simply not offered):
  T: search, read_file, submit_answer
  G: graph_references, graph_lookup, graph_query, read_file, submit_answer

Usage:
  python run_local_mcp.py --task tasks/jackson-jsonnode-get.json --arms T G \
      --trials 1 --model qwen3-coder:30b --workdir ~/gvg-corpus/jackson-databind
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from arms import PRISM_BIN
from schema import Answer, Site, Task
from score import score

HARNESS_DIR = Path(__file__).resolve().parent
RUNS_DIR = HARNESS_DIR / "runs"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_TURNS = 30
OUT_CAP = 4000
NUM_CTX = 16384
CMD_TIMEOUT = 60

# --- structured tool schemas (the MCP-style affordance) ---
READ_FILE = {"type": "function", "function": {
    "name": "read_file",
    "description": "Read a slice of a repo file to inspect code.",
    "parameters": {"type": "object", "properties": {
        "path": {"type": "string", "description": "repo-relative path"},
        "start": {"type": "integer"}, "end": {"type": "integer"}},
        "required": ["path"]}}}
SEARCH = {"type": "function", "function": {
    "name": "search",
    "description": "ripgrep the repository for a regex; returns matching file:line.",
    "parameters": {"type": "object", "properties": {
        "pattern": {"type": "string"}}, "required": ["pattern"]}}}
SUBMIT = {"type": "function", "function": {
    "name": "submit_answer",
    "description": "Submit the FINAL complete set of change-sites and stop.",
    "parameters": {"type": "object", "properties": {
        "sites": {"type": "array", "items": {"type": "string"},
                  "description": "each '<repo-relative-path>:<MethodName>'"},
        "complete": {"type": "boolean"},
        "unresolved": {"type": "array", "items": {"type": "string"}}},
        "required": ["sites", "complete", "unresolved"]}}}
G_REFERENCES = {"type": "function", "function": {
    "name": "graph_references",
    "description": ("Resolved call graph: every reference/caller of a method, by "
                    "its BARE name (e.g. 'get' or 'deserialize', NOT 'JsonNode.get' "
                    "and NOT a signature). Returns authoritative file:line sites."),
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "bare method name"}},
        "required": ["name"]}}}
G_LOOKUP = {"type": "function", "function": {
    "name": "graph_lookup",
    "description": "Look up a symbol's definition/signature by bare name or FQN.",
    "parameters": {"type": "object", "properties": {
        "symbol": {"type": "string"}}, "required": ["symbol"]}}}
G_QUERY = {"type": "function", "function": {
    "name": "graph_query",
    "description": ("Semantic graph query: describe what you want (callers, "
                    "implementors, dispatch targets) and get a ranked neighborhood."),
    "parameters": {"type": "object", "properties": {
        "intent": {"type": "string"}}, "required": ["intent"]}}}

ARM_TOOLS = {
    "T": [SEARCH, READ_FILE, SUBMIT],
    "G": [G_REFERENCES, G_LOOKUP, G_QUERY, READ_FILE, SUBMIT],
}
GRAPH_TOOLS = {"graph_references", "graph_lookup", "graph_query"}

SYSTEM = """\
You are answering a code-context question about a {lang} repository. This is a \
LOCALIZATION / IMPACT task, NOT a coding task: do NOT edit files. Determine the \
COMPLETE set of functions/methods that must CHANGE for the issue below.

ISSUE:
{prompt}

Use the provided tools to investigate over multiple turns. A change to a method's \
signature forces its declaration, every override/implementation, AND every call \
site to change -- find all of them. When you are confident the set is complete, \
call submit_answer. Each site is "<repo-relative-path>:<MethodName>". A missed \
site is a broken fix.{hint}"""

HINT = {
    "T": " Prefer `search` to find symbols, then `read_file` to confirm.",
    "G": (" Prefer the graph tools (graph_references / graph_lookup / graph_query) "
          "to traverse authoritative call edges; they resolve dispatch that text "
          "search cannot. read_file only to confirm."),
}


def _sh(cmd: list[str], workdir: Path) -> str:
    try:
        p = subprocess.run(cmd, cwd=str(workdir), stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=CMD_TIMEOUT)
        out = (p.stdout or "") + (("\n[stderr] " + p.stderr) if p.stderr else "")
        return (out or "[no output / no matches]")[:OUT_CAP]
    except subprocess.TimeoutExpired:
        return "[timeout]"


def dispatch(name: str, args: dict, workdir: Path) -> str:
    if name == "search":
        return _sh(["rg", "--type", "java", str(args.get("pattern", "")), "."], workdir)
    if name == "read_file":
        path = str(args.get("path", ""))
        start, end = int(args.get("start", 1) or 1), int(args.get("end", 200) or 200)
        return _sh(["sed", "-n", f"{start},{end}p", path], workdir)
    if name == "graph_references":
        return _sh([PRISM_BIN, "references", str(args.get("name", "")), "--format", "text"], workdir)
    if name == "graph_lookup":
        return _sh([PRISM_BIN, "lookup", str(args.get("symbol", "")), "--format", "text"], workdir)
    if name == "graph_query":
        return _sh([PRISM_BIN, "query", str(args.get("intent", "")),
                    "--include", "graph", "--format", "text"], workdir)
    return f"[unknown tool {name}]"


def ollama_chat(model: str, messages: list[dict], tools: list[dict]) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": tools,
                       "stream": False,
                       "options": {"temperature": 0.0, "num_ctx": NUM_CTX}}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read()).get("message", {}) or {}


def _fallback_toolcall(content: str) -> dict | None:
    """Some models still emit a call as content JSON; accept {name,arguments}."""
    dec = json.JSONDecoder()
    i = 0
    while True:
        idx = content.find("{", i)
        if idx < 0:
            return None
        try:
            obj, _ = dec.raw_decode(content, idx)
            if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                return {"function": obj}
        except json.JSONDecodeError:
            pass
        i = idx + 1


def run_one(task: Task, arm: str, model: str, workdir: Path) -> dict:
    tools = ARM_TOOLS[arm]
    messages = [{"role": "system",
                 "content": SYSTEM.format(lang=task.lang.capitalize(),
                                          prompt=task.prompt, hint=HINT[arm])},
                {"role": "user", "content": "Begin. Use a tool."}]
    trace: list[dict] = []
    answer = None
    graph_used = False
    t0 = time.time()
    for _ in range(MAX_TURNS):
        msg = ollama_chat(model, messages, tools)
        calls = msg.get("tool_calls") or []
        if not calls:  # fallback: model wrote the call as content
            fb = _fallback_toolcall(msg.get("content", "") or "")
            if fb:
                calls = [fb]
        if not calls:
            messages.append({"role": "assistant", "content": msg.get("content", "")[:500]})
            messages.append({"role": "user", "content": "Call a tool (or submit_answer)."})
            continue
        messages.append({"role": "assistant", "content": msg.get("content", "") or "",
                         "tool_calls": calls})
        done = False
        for c in calls:
            fn = c.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if name == "submit_answer":
                answer = Answer(
                    sites=[Site.parse(s) for s in (args.get("sites") or []) if str(s).strip()],
                    complete=bool(args.get("complete", False)),
                    unresolved=[str(u) for u in (args.get("unresolved") or [])])
                done = True
                break
            if name in GRAPH_TOOLS:
                graph_used = True
            out = dispatch(name, args, workdir)
            trace.append({"tool": name, "bin": name, "detail": json.dumps(args)[:200]})
            messages.append({"role": "tool", "tool_name": name, "content": out})
        if done:
            break
    wall = round(time.time() - t0, 2)
    if answer is None:
        answer = Answer(sites=[], complete=False, unresolved=[])
    return {"answer": answer, "trace": trace, "graph_used": graph_used, "wall_s": wall,
            "tools_used": sorted({t["bin"] for t in trace})}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arms", nargs="+", default=["T", "G"])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--model", required=True)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--pace", type=float, default=0)
    args = ap.parse_args()

    task = Task.load(args.task)
    if args.workdir:
        task.workdir = args.workdir
    workdir = Path(task.workdir or task.repo)
    model_dir = args.model.replace(":", "-").replace("/", "-") + "-mcp"
    out = RUNS_DIR / task.id / model_dir
    out.mkdir(parents=True, exist_ok=True)

    cards, errored = [], []
    for arm in args.arms:
        for trial in range(1, args.trials + 1):
            tag = f"{arm}.t{trial}"
            if args.pace and not (arm == args.arms[0] and trial == 1):
                time.sleep(args.pace)
            print(f"[mcp] {task.id} {model_dir} {tag}")
            try:
                env = run_one(task, arm, args.model, workdir)
            except Exception as e:
                rec = {"task_id": task.id, "arm": arm, "trial": trial,
                       "status": "error", "error": f"{type(e).__name__}: {e}"}
                (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
                errored.append(rec)
                print(f"      ERROR ({rec['error']}) -- excluded")
                continue
            card = score(task, env["answer"], arm, trial)
            gu = env["graph_used"]
            violation = ("T arm used the graph" if arm == "T" and gu else
                         "G arm never used the graph" if arm == "G" and not gu else None)
            rec = {"status": "ok", "model": model_dir, **card.to_dict(),
                   "cost": {"wall_s": env["wall_s"], "duration_ms": None,
                            "num_turns": len(env["trace"]), "usage": None,
                            "total_cost_usd": None},
                   "tools_used": env["tools_used"], "graph_used": gu,
                   "violation": violation, "tool_trace": env["trace"],
                   "answer": {"sites": [str(s) for s in env["answer"].sites],
                              "complete": env["answer"].complete,
                              "unresolved": env["answer"].unresolved}}
            (out / f"{tag}.json").write_text(json.dumps(rec, indent=2) + "\n")
            cards.append(rec)
            warn = f"  !! {violation}" if violation else ""
            print(f"      recall={card.recall} graph_used={gu} turns={len(env['trace'])} "
                  f"tools={env['tools_used']}{warn}")

    (out / "summary.json").write_text(
        json.dumps({"ok": cards, "errored": errored}, indent=2) + "\n")
    print(f"\n[done] {len(cards)} scored, {len(errored)} errored -> {out}")
    print("Next: python rescore_java.py --task", args.task, "; python agg_jackson.py")


if __name__ == "__main__":
    main()
