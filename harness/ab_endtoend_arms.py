"""Arm definitions for the end-to-end agentic benchmark (edit-and-verify).

The question this benchmark answers: on the work a REGULAR coding agent does
(real bug fixes / small features, most of them localized), does a code graph
help the agent — and is it Prism's G/G* or CodeGraph? The oracle is the repo's
own test suite (fail->pass, no pass->fail regressions), run post-hoc in Docker;
the agent never sees it. Tasks are POST-CUTOFF (merged after the model training
cutoff) so memorization cannot substitute for tooling.

Every arm is identical except the CONTEXT tool. All arms can read, edit, and
run the build — only how the agent gathers context differs. Correctness (did
the tests pass) is the headline; turns and the tool_trace are secondary.

The G/G* distinction is enforced STRUCTURALLY via per-tool MCP allowlisting,
not just by prompt:

  G  (primitives)   : the agent orchestrates context hop by hop.
  G* (task altitude): the agent reads whole answers. Its EVERYDAY operation is
                      prism_query (task + anchors -> ranked code/callers/tests/
                      gaps in one call). The task-shaped ops (change_impact,
                      rename_plan, missing_implementations, untested_surface,
                      dead_code) are also G*, but they fire ONLY when the task
                      is that shape. change_impact is NEVER forced onto a
                      localized fix -- doing so would be using the wrong tool
                      and would mismeasure the graph. This is the correction to
                      ab_agentic_mcp.py, whose Prism arm hard-wired change_impact.

CodeGraph's `explore` is the true peer of prism_query -- both are one-call task
context -- so the codegraph arm sits at the same altitude as the G* default,
plus Prism's G* has the type-resolved tail ops CodeGraph does not.
"""
from __future__ import annotations

import json
from pathlib import Path

HOME = Path.home()
CFG_DIR = Path("/tmp/ab-endtoend")
CFG_DIR.mkdir(exist_ok=True)

(CFG_DIR / "codegraph.json").write_text(json.dumps({"mcpServers": {
    "codegraph": {"type": "stdio", "command": str(HOME / ".local/bin/codegraph"),
                  "args": ["serve", "--mcp"]}}}))
(CFG_DIR / "prism.json").write_text(json.dumps({"mcpServers": {
    "prism": {"type": "stdio", "command": str(HOME / "bin/prism"), "args": ["mcp"]}}}))

# Shared: what every arm may do to actually make the fix. Only the context tool
# (added per-arm below) differs. No arm may run the oracle test file -- the
# Docker eval does that after the agent exits.
_EDIT_AND_BUILD = ["Read", "Edit", "Write", "Grep", "Glob",
                   "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)", "Bash(ls:*)",
                   "Bash(cat:*)", "Bash(go build:*)", "Bash(go vet:*)",
                   "Bash(python -m py_compile:*)", "Bash(npm run build:*)",
                   "Bash(mvn -q compile:*)"]

# G* everyday-vs-task-shaped steering -- the crux. Query first; task-shaped ops
# ONLY when the task is that shape; never force change_impact on a localized fix.
_GSTAR_GUIDANCE = (
    "CONTEXT TOOL: Prism at task altitude.\n"
    "1. START with prism_query(task, terms=[a few anchor symbols]) -- it returns "
    "the task-relevant code, its callers, the tests that pin it, and coverage "
    "gaps in ONE call. For most bugs this is the only context call you need; do "
    "not hand-navigate what it already gave you.\n"
    "2. ONLY IF the task is that specific shape, use the matching whole-answer "
    "operation instead of re-deriving it:\n"
    "   - a signature/type is changing -> prism_change_impact (every affected site)\n"
    "   - a rename -> prism_rename_plan\n"
    "   - a new required interface member -> prism_missing_implementations\n"
    "   - 'what should I test' -> prism_untested_surface\n"
    "   - a cleanup / 'is this reachable' -> prism_dead_code\n"
    "Do NOT force prism_change_impact onto a localized fix -- for an ordinary "
    "bug, prism_query is the right and only context call. Then edit and build."
)

ARMS = {
    # What Claude Code / Cursor / Amp do today: grep + read.
    "baseline": {
        "guidance": "CONTEXT TOOL: ripgrep/grep/find and file reads only. Search "
                    "for the symbols, read the code, reason, then edit and build.",
        "allowed": _EDIT_AND_BUILD,
        "mcp": None,
    },
    # G -- primitives; the agent orchestrates context hop by hop. No query, no
    # task-shaped ops: this arm has to assemble the picture itself.
    "prism_g": {
        "guidance": "CONTEXT TOOL: Prism graph PRIMITIVES -- assemble context "
                    "yourself. prism_search (locate a symbol), prism_lookup (one "
                    "symbol's body), prism_references (where it is used), "
                    "prism_edges (callers/callees/tests, one hop), prism_resolve "
                    "(disambiguate a name). Grep for anchors. Then edit and build.",
        "allowed": _EDIT_AND_BUILD + [
            "mcp__prism__prism_search", "mcp__prism__prism_lookup",
            "mcp__prism__prism_references", "mcp__prism__prism_edges",
            "mcp__prism__prism_resolve", "mcp__prism__prism_read"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
    # G* -- task altitude; query-first, task-shaped ops on task shape only.
    "prism_gstar": {
        "guidance": _GSTAR_GUIDANCE,
        "allowed": _EDIT_AND_BUILD + [
            "mcp__prism__prism_query",
            "mcp__prism__prism_change_impact", "mcp__prism__prism_rename_plan",
            "mcp__prism__prism_missing_implementations",
            "mcp__prism__prism_untested_surface", "mcp__prism__prism_dead_code",
            "mcp__prism__prism_read", "mcp__prism__prism_lookup"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
    # CodeGraph -- explore is the one-call peer of prism_query (same altitude).
    "codegraph": {
        "guidance": "CONTEXT TOOL: CodeGraph. codegraph_explore(task/symbol) "
                    "returns relevant symbols, call paths, and blast radius in one "
                    "call -- use it as your primary context tool; impact/callers "
                    "for follow-ups. Then edit and build.",
        "allowed": _EDIT_AND_BUILD + ["mcp__codegraph"],
        "mcp": str(CFG_DIR / "codegraph.json"),
    },
}

# Forced-graph (_nogrep) variants: strip every text-search/browse tool so
# discovery MUST go through the graph -- the clean isolation, symmetric across
# graph arms. Baseline keeps grep (grep IS its tool / the control).
_SEARCH = {"Grep", "Glob", "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)",
           "Bash(ls:*)", "Bash(cat:*)"}
for _base in ("prism_g", "prism_gstar", "codegraph"):
    ARMS[_base + "_nogrep"] = {
        "guidance": ARMS[_base]["guidance"] +
                    "\nYou have NO grep/text-search tool. Discover all code THROUGH "
                    "the graph tools above, then read/edit the files they point to.",
        "allowed": [t for t in ARMS[_base]["allowed"] if t not in _SEARCH],
        "mcp": ARMS[_base]["mcp"],
    }

# Which MCP tool families count as "used the graph" when reading a tool_trace --
# lets the runner report the finding the user cares about: on localized tasks,
# did the agent reach for a graph op at all, and WHICH altitude?
GRAPH_TOOL_PREFIXES = {
    "prism_g": ("mcp__prism__prism_search", "mcp__prism__prism_lookup",
                "mcp__prism__prism_references", "mcp__prism__prism_edges",
                "mcp__prism__prism_resolve"),
    "prism_gstar": ("mcp__prism__prism_query", "mcp__prism__prism_change_impact",
                    "mcp__prism__prism_rename_plan",
                    "mcp__prism__prism_missing_implementations",
                    "mcp__prism__prism_untested_surface",
                    "mcp__prism__prism_dead_code"),
    "codegraph": ("mcp__codegraph",),
    "baseline": (),
}
