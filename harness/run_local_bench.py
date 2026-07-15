"""Unified local (Ollama) change-impact runner for the model x arm benchmark.

Two arms, same model, same task, same oracle — only the tools differ:

  baseline : search (rg) + read_file + submit_answer          (no graph)
  prism    : change_impact (prism engine) + submit_answer      (task altitude)

Records the same fields as the cloud runner (ab_agentic_mcp): recall (oracle),
turns, tokens_in, tokens_out, wall_s. Ollama returns prompt_eval_count /
eval_count per response; we sum them so local token usage is measured, not
assumed. cost_usd is null (local is free).

Local models emit tool_calls unreliably, so turn 0 forces the arm's primary
tool (invocation wall) — the same accommodation disclosed in run_local_gstar;
it is applied identically to BOTH arms, so it does not favor the graph.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

# qwen3-coder / Hermes-template models often emit the tool call as text in the
# content rather than as structured tool_calls, in one of two shapes:
#   {"name": "change_impact", "arguments": {...}}                      (JSON)
#   <function=change_impact><parameter=symbol>Foo.bar</parameter></function>  (XML tag)
# Ollama's template usually parses these, but leaks them to content on some
# prompts. Recovering them here is what keeps the local PRISM arm from failing
# on tasks the engine resolves fine (measured: writetypeprefix 0.1 -> 1.0).
_FUNC_RE = re.compile(r"<function=(\w+)>(.*?)</function>", re.S)
_PARAM_RE = re.compile(r"<parameter=(\w+)>\s*(.*?)\s*</parameter>", re.S)
_KNOWN = {"search", "read_file", "change_impact", "submit_answer"}


def _toolcall_from_content(content: str):
    content = (content or "").strip()
    if content.startswith("{"):
        try:
            obj = json.loads(content)
            if isinstance(obj, dict) and obj.get("name") in _KNOWN:
                return {"function": {"name": obj["name"],
                                     "arguments": obj.get("arguments", {})}}
        except json.JSONDecodeError:
            pass
    m = _FUNC_RE.search(content)
    if m and m.group(1) in _KNOWN:
        args = {p: v.strip() for p, v in _PARAM_RE.findall(m.group(2))}
        return {"function": {"name": m.group(1), "arguments": args}}
    return None

from schema import Answer, Site, Task
from score import score

PRISM_BIN = Path.home() / "bin" / "prism"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_TURNS = 12
NUM_CTX = 16384
OUT_CAP = 4000

# ── tool schemas ────────────────────────────────────────────────────────────

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": "Submit the FINAL list of change-sites and stop.",
        "parameters": {"type": "object", "properties": {
            "sites": {"type": "array", "items": {"type": "string"}},
            "complete": {"type": "boolean"},
            "unresolved": {"type": "array", "items": {"type": "string"}},
        }, "required": ["sites", "complete", "unresolved"]},
    },
}
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Regex/text search across the repo (ripgrep). Returns matching "
                       "file:line:text. Use to locate the symbol and its callers.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}}, "required": ["pattern"]},
    },
}
READ_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a repo-relative file (optionally a line range) to inspect code.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "start": {"type": "integer"}, "end": {"type": "integer"}},
            "required": ["path"]},
    },
}
CHANGE_IMPACT_TOOL = {
    "type": "function",
    "function": {
        "name": "change_impact",
        "description": ("Return the COMPLETE set of sites that must change if the given "
                        "method's signature changes: declaration, every override/"
                        "implementation, and every resolved caller. Input as "
                        "'Class.method' or 'Class.method(ParamType,...)'. Returns "
                        "'relpath/File:methodName' strings ready for submit_answer."),
        "parameters": {"type": "object", "properties": {
            "symbol": {"type": "string"}}, "required": ["symbol"]},
    },
}

SYSTEM_PRISM = """\
You are answering a code-context question about a {lang} repository.
Determine the COMPLETE set of methods that must CHANGE for the issue below.

ISSUE:
{prompt}

You have a change_impact tool that, given the method named in the issue, returns
the ENTIRE change-set in one call. Call change_impact with the method symbol,
then call submit_answer with exactly the sites it returns — copy them verbatim."""

SYSTEM_BASE = """\
You are answering a code-context question about a {lang} repository.
Determine the COMPLETE set of methods that must CHANGE for the issue below.
A missed site is a broken build; be exhaustive about callers.

ISSUE:
{prompt}

Use search to locate the method and everything that calls it (including
overrides and indirect callers), read_file to confirm, then submit_answer with
every site as 'relpath:MethodName'."""

ARMS = {
    "baseline": {"tools": [SEARCH_TOOL, READ_TOOL, SUBMIT_TOOL], "primary": "search",
                 "system": SYSTEM_BASE},
    "prism":    {"tools": [CHANGE_IMPACT_TOOL, SUBMIT_TOOL], "primary": "change_impact",
                 "system": SYSTEM_PRISM},
}


# ── tool backends ───────────────────────────────────────────────────────────

def _rg(pattern: str, workdir: Path) -> str:
    r = subprocess.run(["rg", "-n", "--no-heading", "-m", "80", pattern, "."],
                       capture_output=True, text=True, cwd=workdir, timeout=60)
    out = r.stdout or r.stderr or "(no matches)"
    return out[:OUT_CAP]


def _read(path: str, workdir: Path, start=None, end=None) -> str:
    fp = (workdir / path)
    if not fp.exists():
        return f"(no such file: {path})"
    lines = fp.read_text(errors="replace").splitlines()
    if start:
        lines = lines[max(0, int(start) - 1):int(end) if end else None]
    return "\n".join(lines)[:OUT_CAP]


def prism_change_impact(symbol: str, workdir: Path) -> list[str]:
    r = subprocess.run([str(PRISM_BIN), "change-impact", symbol, "."],
                       capture_output=True, text=True, cwd=workdir, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"prism change-impact failed: {r.stderr[:300]}")
    data = json.loads(r.stdout)
    sites: list[str] = []
    for group in ("declarations", "family", "callers"):
        for sym in data.get(group, []):
            fp = sym.get("filePath") or sym.get("file", "")
            name = sym.get("name", "")
            if fp and name:
                sites.append(f"{fp}:{name}")
    return sites


def ollama_chat(model: str, messages, tools, tool_choice=None) -> dict:
    payload = {"model": model, "messages": messages, "tools": tools,
               "stream": False, "options": {"temperature": 0, "num_ctx": NUM_CTX}}
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())  # full response incl. token counts


def run(arm: str, task: Task, model: str) -> dict:
    """One trial of one (arm, task) on the local model. Returns a cloud-shaped rec."""
    spec = ARMS[arm]
    workdir = Path(task.workdir or task.repo)
    messages = [
        {"role": "system", "content": spec["system"].format(
            lang=task.lang.capitalize(), prompt=task.prompt)},
        {"role": "user", "content": "Begin."},
    ]
    answer: Answer | None = None
    turns = 0
    tok_in = tok_out = 0
    t0 = time.monotonic()

    for turn in range(MAX_TURNS):
        if turn == 0:
            primary = next(t for t in spec["tools"]
                           if t["function"]["name"] == spec["primary"])
            resp = ollama_chat(model, messages, [primary], tool_choice="required")
        else:
            resp = ollama_chat(model, messages, spec["tools"])
        tok_in += int(resp.get("prompt_eval_count", 0) or 0)
        tok_out += int(resp.get("eval_count", 0) or 0)
        msg = resp.get("message", {}) or {}
        calls = msg.get("tool_calls") or []

        if not calls:  # recover a tool call the template leaked into content
            tc = _toolcall_from_content(msg.get("content") or "")
            if tc:
                calls = [tc]
        if not calls:
            messages.append({"role": "assistant", "content": (msg.get("content") or "")[:400]})
            messages.append({"role": "user", "content":
                             f"Call {spec['primary']}, then submit_answer with every site."})
            continue

        messages.append({"role": "assistant", "content": msg.get("content") or "",
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
            turns += 1
            if name == "submit_answer":
                answer = Answer(
                    sites=[Site.parse(s) for s in (args.get("sites") or []) if str(s).strip()],
                    complete=bool(args.get("complete", False)),
                    unresolved=[str(u) for u in (args.get("unresolved") or [])])
                done = True
                break
            if name == "search":
                res = _rg(str(args.get("pattern", "")), workdir)
            elif name == "read_file":
                res = _read(str(args.get("path", "")), workdir,
                            args.get("start"), args.get("end"))
            elif name == "change_impact":
                try:
                    sites = prism_change_impact(str(args.get("symbol", "")).strip(), workdir)
                    res = json.dumps({"sites": sites, "count": len(sites),
                                      "note": "Copy these verbatim to submit_answer."})
                except Exception as e:
                    res = json.dumps({"error": str(e)})
            else:
                res = json.dumps({"error": f"unknown tool {name}"})
            messages.append({"role": "tool", "content": res[:OUT_CAP]})
        if done:
            break

    # Out of turns without submitting: force a final submit so the run yields a
    # measured answer (what the model found) rather than a null. Applied to both
    # arms identically.
    if answer is None:
        messages.append({"role": "user", "content":
                         "You are out of steps. Call submit_answer now with every "
                         "site you have found so far."})
        try:
            resp = ollama_chat(model, messages, [SUBMIT_TOOL], tool_choice="required")
            tok_in += int(resp.get("prompt_eval_count", 0) or 0)
            tok_out += int(resp.get("eval_count", 0) or 0)
            for c in (resp.get("message", {}) or {}).get("tool_calls") or []:
                a = c.get("function", {}).get("arguments", {})
                if isinstance(a, str):
                    a = json.loads(a)
                answer = Answer(
                    sites=[Site.parse(s) for s in (a.get("sites") or []) if str(s).strip()],
                    complete=bool(a.get("complete", False)),
                    unresolved=[str(u) for u in (a.get("unresolved") or [])])
                turns += 1
                break
        except Exception:
            pass

    wall = round(time.monotonic() - t0, 1)
    rec = {"arm": arm, "model": model, "task": task.id, "wall_s": wall,
           "turns": turns, "tokens_in": tok_in, "tokens_out": tok_out,
           "cost_usd": 0.0}
    if answer is not None:
        rec["recall"] = round(score(task, answer, arm, 1).recall, 3)
        rec["n_sites"] = len(answer.sites)
        rec["complete_claim"] = answer.complete
    else:
        rec["error"] = "no answer submitted within MAX_TURNS"
    return rec
