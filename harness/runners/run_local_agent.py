"""Neutral local-model agent loop for the end-to-end benchmark's LOCAL tier.

There is no off-the-shelf agent that drives a local model across all four arms
with controlled tool exposure (mason bakes the graph in; OpenCode/Continue
score 0-1/9 driving local models -- they would mismeasure the graph as harness
incompetence). So this is a minimal, neutral ReAct loop over ollama's
OpenAI-compatible endpoint. The model is the only variable; per-arm tool
exposure is controlled here exactly as `claude -p --allowedTools` controls the
cloud arms, so local numbers are comparable to Sonnet/Haiku.

Context tools shell out to the prism / engine-b CLIs -- the SAME engine the
cloud arms reach via MCP, so the graph answer is identical; only the transport
differs. Arms mirror ab_endtoend_arms.py.

Cloud tier (Sonnet/Haiku) runs via claude -p (no ANTHROPIC_API_KEY here); this
file is local-only. Ollama has no rate limit, so local cells never pause.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434/v1/chat/completions"
MAX_TURNS = int(__import__("os").environ.get("LOCAL_MAX_TURNS", "150"))


def _prism(*args: str, cwd: str) -> str:
    r = subprocess.run(["prism", *args, "--format", "text"], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr)[:6000]


def _engine_b(*args: str, cwd: str) -> str:
    r = subprocess.run(["engine-b", *args], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr)[:6000]


# --- base tools every arm gets (find, read, edit, build) ---
# All args default so a malformed tool call returns an error to the model
# instead of crashing the run.
def _tool_grep(cwd, pattern="", **_):
    if not pattern:
        return "(no pattern given)"
    # explicit "." target + closed stdin: without them rg reads a piped stdin
    # forever instead of searching the directory.
    r = subprocess.run(["rg", "-n", "--no-heading", pattern, "."], cwd=cwd,
                       capture_output=True, text=True, timeout=60,
                       stdin=subprocess.DEVNULL)
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



# --- grep passthrough: the graph delivered through the grep habit ---
# Same tool name, same schema, same description the model already reaches for.
# Real ripgrep output ALWAYS comes back verbatim; when the pattern is
# symbol-shaped, a compact type-resolved block is appended. Any prism failure
# or slow path degrades silently to plain grep -- fidelity first.
import re as _re

_IDENT = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
_TYPEMETH = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


def _graph_block(cwd, pattern):
    try:
        if _TYPEMETH.match(pattern):
            args = ["prism", "change-impact", pattern, str(cwd), "--format", "text"]
        elif _IDENT.match(pattern):
            # v2: deliver the CODE, not a site list. v1 appended bare
            # references (file:line names) and the model failed pr3534 with the
            # block in hand, while prism_query's source+callers delivery won it
            # 2/2. `node` is the passthrough-sized version of that payload:
            # the symbol's definition source plus its neighbour menu.
            args = ["prism", "node", pattern, str(cwd), "--format", "text"]
        else:
            return ""
        r = subprocess.run(args, capture_output=True, text=True, timeout=15)
        out = (r.stdout or "").strip()
        if r.returncode != 0 or not out or "0 references" in out:
            return ""
        return ("\n---- graph (type-resolved; grep cannot see indirect/typed usages) ----\n"
                + out[:2600])
    except Exception:
        return ""


def _tool_grep_passthru(cwd, pattern="", **_):
    base = _tool_grep(cwd, pattern=pattern)
    block = _graph_block(cwd, pattern)
    log = os.environ.get("PASSTHRU_LOG")
    if log:
        with open(log, "a") as f:
            f.write(json.dumps({"pattern": pattern, "enriched": bool(block),
                                "block_chars": len(block)}) + "\n")
    return (base + block)[:5600]


BASE_TOOLS = {
    "grep": (_tool_grep, {"pattern": "str"}, "Search code by regex (ripgrep)."),
    "read_file": (_tool_read, {"path": "str"}, "Read a file (repo-relative path)."),
    "apply_edit": (_tool_edit, {"path": "str", "old": "str", "new": "str"},
                   "Replace an exact unique snippet in a file."),
    "run_cmd": (_tool_build, {"cmd": "str"}, "Run a build/inspect command."),
}



# --- prism_only: the single search verb (user design, 2026-08-03) ---
# Graph-first, grep-fallback INSIDE the tool. The agent has no grep; it calls
# prism_query with the terms it would have grepped. Contract: NEVER refuse,
# NEVER return empty. No terms -> derive them from the task text. Thin or
# absent graph answer -> run ripgrep on the terms and return that, labeled.
def _derive_terms(task):
    import collections
    words = _re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", task)
    common = {"this", "that", "with", "from", "have", "when", "should",
              "returns", "return", "value", "error", "does", "call"}
    ranked = [w for w, _ in collections.Counter(words).most_common()
              if w.lower() not in common]
    return ",".join(ranked[:3]) if ranked else "main"


def _grep_terms(cwd, terms):
    outs = []
    for t in [x.strip() for x in terms.split(",") if x.strip()][:4]:
        r = subprocess.run(["rg", "-n", "--no-heading", t, "."], cwd=cwd,
                           capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        if r.stdout:
            outs.append(f"-- text matches for '{t}' --\n" + r.stdout[:1200])
    return "\n".join(outs) or "(no text matches either -- try different terms)"


def _tool_prism_query_fb(cwd, task="", terms="", **_):
    if not task and not terms:
        return "(give a task description, terms, or both)"
    if not terms:
        terms = _derive_terms(task or "")
    out = _prism("query", task or terms, "--terms", terms,
                 "--include", "graph", cwd=cwd)
    thin = (not out) or len(out.strip()) < 200 or out.strip().startswith("query:")
    if thin:
        return ("(graph had nothing for these terms; text search results)\n"
                + _grep_terms(cwd, terms))
    return out[:5600]


def _ctx_tools(arm: str) -> dict:
    """Per-arm context tools -- the ONLY thing that differs between arms."""
    if arm == "baseline":
        return {}
    if arm == "prism_only":
        return {
            "prism_query": (_tool_prism_query_fb, {"task": "str", "terms": "str"},
                            "Find code: searches the code graph, falls back to text "
                            "search automatically. Pass the task and the terms you "
                            "would have grepped."),
            "prism_change_impact": (lambda cwd, method="", **_: _prism("change-impact", method, cwd=cwd),
                                    {"method": "str"},
                                    "ONLY for a signature/type change: every affected site."),
        }
    if arm == "prism_passthru":
        # IDENTICAL surface to baseline -- no prism tools, no extra steering.
        # Only grep's internals change. This is the zero-adoption-ask arm.
        return {"grep": (_tool_grep_passthru, {"pattern": "str"},
                         "Search code by regex (ripgrep).")}
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
    if arm == "engine-b":
        return {
            "engine_b_explore": (lambda cwd, query="", **_: _engine_b("explore", query, cwd=cwd), {"query": "str"}, "PRIMARY: relevant symbols, call paths, blast radius in one call."),
        }
    raise ValueError(arm)


GUIDANCE = {
    "prism_only": "Use prism_query(task, terms) to find code -- it searches the code graph and falls back to text search automatically; pass the terms you would have searched for. Use prism_change_impact ONLY for a signature/type change. Then read, edit, and build.",
    "prism_passthru": "Use grep and read_file to find and understand the code, then apply_edit and run_cmd to fix it.",
    "baseline": "Use grep and read_file to find and understand the code, then apply_edit and run_cmd to fix it.",
    "prism_g": "Use the prism_* primitives to navigate (search->lookup->references), assembling context yourself, then edit and build.",
    "prism_gstar": ("START with prism_query(task, terms) -- it returns relevant code, callers, tests, and gaps in one call; "
                    "for most bugs it is the only context call you need. Use prism_change_impact / prism_rename_plan ONLY if the "
                    "task is that specific shape -- never force change_impact on a localized fix. Then edit and build."),
    "engine-b": "Use engine_b_explore as your primary context tool, then edit and build.",
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
    if nogrep or arm == "prism_only":
        tools.pop("grep", None)
    tools["finish"] = (None, {"summary": "str"}, "Call when the fix is complete.")
    tool_schemas = [_schema(n, p, d) for n, (_, p, d) in tools.items()]
    guidance = GUIDANCE[base_arm] + (" You have NO text-search tool; discover code THROUGH the graph tools." if nogrep else "")
    sys = (f"You are fixing a codebase. {guidance} When the fix is done and builds, call finish. "
           f"Make the smallest change that resolves the issue.")
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": task_prompt}]
    trace, t0 = [], time.monotonic()

    # Context management -- without this the message list grows unbounded and
    # ollama silently truncates the prompt head (system + task first), after
    # which the model flails and burns the remaining turns in ~1s each. The
    # 2026-08-02 local grid measured exactly that, not graph-vs-grep.
    # Policy: always keep system+task and the last KEEP_TAIL messages verbatim;
    # when over budget, elide OLDER tool outputs (stub keeps the trajectory
    # visible so the model still knows what it already looked at).
    NUM_CTX = int(os.environ.get("LOCAL_NUM_CTX", "16384"))
    CHAR_BUDGET = int(NUM_CTX * 3.5 * 0.80)   # ~3.5 chars/token, 20% headroom
    KEEP_TAIL = 10

    def _fit(ms):
        total = sum(len(str(m.get("content") or "")) for m in ms)
        if total <= CHAR_BUDGET:
            return ms
        head, tail = ms[:2], ms[2:]
        body_ = tail[:-KEEP_TAIL] if len(tail) > KEEP_TAIL else []
        keep = tail[len(body_):]
        for m in body_:
            if m.get("role") == "tool" and len(str(m.get("content") or "")) > 200:
                m = dict(m); m["content"] = "(elided earlier output -- re-run the tool if needed)"
            total_m = m
            yield_m = total_m
            head.append(yield_m)
        out = head + keep
        # second pass: if STILL over budget, drop elided-tool messages entirely
        # (oldest first), never touching system/task or the tail.
        while sum(len(str(m.get("content") or "")) for m in out) > CHAR_BUDGET and len(out) > 2 + KEEP_TAIL:
            for i in range(2, len(out) - KEEP_TAIL):
                if out[i].get("role") in ("tool", "assistant"):
                    del out[i]
                    break
            else:
                break
        return out

    for turn in range(MAX_TURNS):
        msgs = list(_fit(msgs))
        body = json.dumps({"model": model, "messages": msgs, "tools": tool_schemas,
                           "tool_choice": "auto", "stream": False,
                           "options": {"num_ctx": NUM_CTX}}).encode()
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
            try:
                out = impl(repo, **args) if impl else f"(unknown tool {fn})"
            except Exception as e:
                # A bad call (read of a directory, missing file, etc.) is the
                # MODEL's mistake — report it back so it can correct course; it
                # must never kill the cell (it did, 2026-08-02, IsADirectoryError).
                out = f"(tool error: {type(e).__name__}: {e})"
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": str(out)[:6000]})
    diff = subprocess.run(["git", "diff"], cwd=repo, capture_output=True, text=True).stdout
    return {"arm": arm, "model": model, "turns": MAX_TURNS, "trace": trace,
            "wall_s": round(time.monotonic() - t0, 1), "diff": diff, "finished": False}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3-coder:30b")
    ap.add_argument("--arm", required=True, choices=["baseline", "prism_passthru", "prism_g", "prism_gstar", "engine-b"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--task", required=True)
    a = ap.parse_args()
    print(json.dumps(run(a.model, a.arm, a.repo, a.task), indent=2))
