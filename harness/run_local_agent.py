"""Neutral local-model agent loop for the end-to-end benchmark's LOCAL tier.

There is no off-the-shelf agent that drives a local model across all four arms
with controlled tool exposure (mason bakes the graph in; OpenCode/Continue
score 0-1/9 driving local models -- they would mismeasure the graph as harness
incompetence). So this is a minimal, neutral ReAct loop over ollama's
OpenAI-compatible endpoint. The model is the only variable; per-arm tool
exposure is controlled here exactly as `claude -p --allowedTools` controls the
cloud arms, so local numbers are comparable to Sonnet/Haiku.

Context tools shell out to the prism / codegraph CLIs -- the SAME engine the
cloud arms reach via MCP, so the graph answer is identical; only the transport
differs. Arms mirror ab_endtoend_arms.py.

Cloud tier (Sonnet/Haiku) runs via claude -p (no ANTHROPIC_API_KEY here); this
file is local-only. Ollama has no rate limit, so local cells never pause.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434/v1/chat/completions"
MAX_TURNS = 40


def _prism(*args: str, cwd: str) -> str:
    r = subprocess.run(["prism", *args, "--format", "text"], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr)[:6000]


def _codegraph(*args: str, cwd: str) -> str:
    r = subprocess.run(["codegraph", *args], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr)[:6000]


# --- base tools every arm gets (find, read, edit, build) ---
# All args default so a malformed tool call returns an error to the model
# instead of crashing the run.
def _tool_grep(cwd, pattern="", **_):
    if not pattern:
        return "(no pattern given)"
    r = subprocess.run(["rg", "-n", "--no-heading", pattern], cwd=cwd,
                       capture_output=True, text=True, timeout=60)
    return (r.stdout or "(no matches)")[:4000]


def _tool_read(cwd, path="", **_):
    if not path:
        return "(no path given)"
    p = Path(cwd) / path
    if not p.exists():
        return f"(no such file: {path})"
    return p.read_text(errors="replace")[:8000]


def _tool_edit(cwd, path="", old="", new="", **_):
    if not path or not old:
        return "(edit needs path, old, new)"
    p = Path(cwd) / path
    if not p.exists():
        return f"(no such file: {path})"
    txt = p.read_text()
    if old not in txt:
        return "(old string not found -- read the file and match exactly)"
    if txt.count(old) > 1:
        return "(old string not unique -- add surrounding context)"
    p.write_text(txt.replace(old, new, 1))
    return f"(edited {path})"


def _tool_build(cwd, cmd="", **_):
    if not cmd:
        return "(no command given)"
    if not any(cmd.startswith(x) for x in ("go build", "go vet", "python -m py_compile",
                                            "npm run build", "mvn -q compile", "ls", "cat")):
        return "(command not permitted; build/inspect only)"
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=300)
    return f"exit={r.returncode}\n{(r.stdout + r.stderr)[:3000]}"


BASE_TOOLS = {
    "grep": (_tool_grep, {"pattern": "str"}, "Search code by regex (ripgrep)."),
    "read_file": (_tool_read, {"path": "str"}, "Read a file (repo-relative path)."),
    "apply_edit": (_tool_edit, {"path": "str", "old": "str", "new": "str"},
                   "Replace an exact unique snippet in a file."),
    "run_cmd": (_tool_build, {"cmd": "str"}, "Run a build/inspect command."),
}


def _ctx_tools(arm: str) -> dict:
    """Per-arm context tools -- the ONLY thing that differs between arms."""
    if arm == "baseline":
        return {}
    if arm == "prism_g":  # primitives -- agent orchestrates
        return {
            "prism_search":     (lambda cwd, q="", **_: _prism("search", q, cwd=cwd), {"q": "str"}, "Find a symbol by keyword."),
            "prism_lookup":     (lambda cwd, symbol="", **_: _prism("lookup", symbol, cwd=cwd), {"symbol": "str"}, "One symbol's body."),
            "prism_references": (lambda cwd, name="", **_: _prism("references", name, cwd=cwd), {"name": "str"}, "Where a symbol is used."),
        }
    if arm == "prism_gstar":  # task altitude -- query first, task-shaped ops on shape only
        return {
            "prism_query":         (lambda cwd, task="", terms="", **_: _prism("query", task, "--terms", terms, "--include", "graph,tests,coverage_gaps", cwd=cwd), {"task": "str", "terms": "str"}, "PRIMARY: task-relevant code, callers, tests, gaps in one call."),
            "prism_change_impact": (lambda cwd, method="", **_: _prism("change-impact", method, cwd=cwd), {"method": "str"}, "ONLY for a signature/type change: every affected site."),
            "prism_rename_plan":   (lambda cwd, method="", newName="", **_: _prism("rename-plan", method, newName, cwd=cwd), {"method": "str", "newName": "str"}, "ONLY for a rename."),
        }
    if arm == "codegraph":
        return {
            "codegraph_explore": (lambda cwd, query="", **_: _codegraph("explore", query, cwd=cwd), {"query": "str"}, "PRIMARY: relevant symbols, call paths, blast radius in one call."),
        }
    raise ValueError(arm)


GUIDANCE = {
    "baseline": "Use grep and read_file to find and understand the code, then apply_edit and run_cmd to fix it.",
    "prism_g": "Use the prism_* primitives to navigate (search->lookup->references), assembling context yourself, then edit and build.",
    "prism_gstar": ("START with prism_query(task, terms) -- it returns relevant code, callers, tests, and gaps in one call; "
                    "for most bugs it is the only context call you need. Use prism_change_impact / prism_rename_plan ONLY if the "
                    "task is that specific shape -- never force change_impact on a localized fix. Then edit and build."),
    "codegraph": "Use codegraph_explore as your primary context tool, then edit and build.",
}


def _schema(name, params, desc):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object",
                           "properties": {k: {"type": "string"} for k in params},
                           "required": list(params)}}}


def run(model: str, arm: str, repo: str, task_prompt: str) -> dict:
    # `_nogrep` variants strip content-search (grep) so discovery is FORCED
    # through the graph -- the clean isolation test, applied symmetrically.
    nogrep = arm.endswith("_nogrep")
    base_arm = arm[:-7] if nogrep else arm
    tools = {**BASE_TOOLS, **_ctx_tools(base_arm)}
    if nogrep:
        tools.pop("grep", None)
    tools["finish"] = (None, {"summary": "str"}, "Call when the fix is complete.")
    tool_schemas = [_schema(n, p, d) for n, (_, p, d) in tools.items()]
    guidance = GUIDANCE[base_arm] + (" You have NO text-search tool; discover code THROUGH the graph tools." if nogrep else "")
    sys = (f"You are fixing a codebase. {guidance} When the fix is done and builds, call finish. "
           f"Make the smallest change that resolves the issue.")
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": task_prompt}]
    trace, t0 = [], time.monotonic()
    for turn in range(MAX_TURNS):
        body = json.dumps({"model": model, "messages": msgs, "tools": tool_schemas,
                           "tool_choice": "auto", "stream": False}).encode()
        req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=600))
        except Exception as e:
            return {"arm": arm, "model": model, "error": f"api: {e}", "trace": trace, "turns": turn}
        m = resp["choices"][0]["message"]
        msgs.append(m)
        calls = m.get("tool_calls") or []
        if not calls:
            if m.get("content"):  # nudge once toward acting
                msgs.append({"role": "user", "content": "Continue with a tool call, or call finish if done."})
                continue
            break
        for c in calls:
            fn = c["function"]["name"]
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            trace.append(fn)
            if fn == "finish":
                out = "ok"
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": out})
                diff = subprocess.run(["git", "diff"], cwd=repo, capture_output=True, text=True).stdout
                return {"arm": arm, "model": model, "turns": turn + 1, "trace": trace,
                        "wall_s": round(time.monotonic() - t0, 1), "diff": diff,
                        "finished": True}
            impl = tools.get(fn, (None,))[0]
            out = impl(repo, **args) if impl else f"(unknown tool {fn})"
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": str(out)[:6000]})
    diff = subprocess.run(["git", "diff"], cwd=repo, capture_output=True, text=True).stdout
    return {"arm": arm, "model": model, "turns": MAX_TURNS, "trace": trace,
            "wall_s": round(time.monotonic() - t0, 1), "diff": diff, "finished": False}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3-coder:30b")
    ap.add_argument("--arm", required=True, choices=["baseline", "prism_g", "prism_gstar", "codegraph"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--task", required=True)
    a = ap.parse_args()
    print(json.dumps(run(a.model, a.arm, a.repo, a.task), indent=2))
