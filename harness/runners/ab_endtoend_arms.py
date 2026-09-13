"""Arm definitions for the end-to-end agentic benchmark (edit-and-verify).

The question this benchmark answers: on the work a REGULAR coding agent does
(real bug fixes / small features, most of them localized), does a code graph
help the agent — and is it Prism's G/G* or Engine B? The oracle is the repo's
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

Engine B's `explore` is the true peer of prism_query -- both are one-call task
context -- so the engine-b arm sits at the same altitude as the G* default,
plus Prism's G* has the type-resolved tail ops Engine B does not.
"""
from __future__ import annotations

import json
from pathlib import Path

HOME = Path.home()
CFG_DIR = Path("/tmp/ab-endtoend")
CFG_DIR.mkdir(exist_ok=True)

(CFG_DIR / "engine-b.json").write_text(json.dumps({"mcpServers": {
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
    "gaps in ONE call. For bug fixes it returns verbatim LINE-NUMBERED source "
    "windows (edit-ready; do NOT re-read those files). For most bugs this is "
    "the only context call you need; do not hand-navigate what it already gave you.\n"
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
    # Prism SOURCE DELIVERY -- the feature built for LOCALIZED bug fixes (v0.25):
    # prism_query returns edit-ready, line-numbered source windows + each anchor's
    # callers and covering tests, in one call. No change_impact to distract from a
    # localized fix. This is the arm that tests "does Prism help fix bugs" with the
    # RIGHT tool (vs prism_gstar, which leads with the wide-blast-radius op).
    "prism_source": {
        "guidance": "CONTEXT TOOL: Prism source delivery. Call prism_query(task="
                    "\"<the bug symptom>\", terms=[a few anchor symbols]) FIRST -- for "
                    "a bug fix it returns the relevant code as verbatim, LINE-NUMBERED "
                    "source windows plus each anchor's callers and covering tests, "
                    "edit-ready. Treat those windows as reads you already did: edit "
                    "the files directly, do not re-read them. Then build and verify.",
        "allowed": _EDIT_AND_BUILD + [
            "mcp__prism__prism_query", "mcp__prism__prism_read",
            "mcp__prism__prism_lookup", "mcp__prism__prism_edges"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
    # prism_source + UPFRONT HEDGE (change A). Licenses grep for contract-wide
    # fixes BEFORE acting -- the agent judges upfront whether the fix is broad.
    # NOT failure-gated: the clause is in effect on every fix, so this is the arm
    # that tests whether A's upfront judgment taxes/regresses the localized fixes
    # that already pass (the risk B avoids by gating behind an observed failure).
    "prism_source_a": {
        "guidance": ("CONTEXT TOOL: Prism source delivery. Call prism_query(task="
                    "\"<the bug symptom>\", terms=[a few anchor symbols]) FIRST -- for "
                    "a bug fix it returns the relevant code as verbatim, LINE-NUMBERED "
                    "source windows plus each anchor's callers and covering tests, "
                    "edit-ready. These are the anchor and its immediate context; do not "
                    "re-read them. BUT if the fix touches behavior beyond what is shown "
                    "(a shared format, protocol, or contract used elsewhere), grep to "
                    "map the full extent BEFORE editing. Then edit and verify."),
        "allowed": _EDIT_AND_BUILD + [
            "mcp__prism__prism_query", "mcp__prism__prism_read",
            "mcp__prism__prism_lookup", "mcp__prism__prism_edges"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
    # prism_source + FAILURE-GATED ESCALATION (change B). Same focused source
    # delivery, but if the fix fails its tests, widen: grep the surrounding code
    # and read the failing test to check whether the correct fix is broader than
    # the anchor. Gated behind an observed test failure, so it is a strict no-op
    # on any fix that passes first try -- can't regress the good tasks by design.
    "prism_source_esc": {
        "guidance": ("CONTEXT TOOL: Prism source delivery. Call prism_query(task="
                    "\"<the bug symptom>\", terms=[a few anchor symbols]) FIRST -- for "
                    "a bug fix it returns the relevant code as verbatim, LINE-NUMBERED "
                    "source windows plus each anchor's callers and covering tests, "
                    "edit-ready. Treat those windows as reads you already did: edit "
                    "the files directly, do not re-read them. Then run the tests. IF "
                    "THEY STILL FAIL, do not just keep tweaking the same lines -- grep "
                    "the surrounding code and read the failing test to check whether the "
                    "correct fix is WIDER than what you changed (a shared format, "
                    "protocol, or contract used elsewhere). Widen, then fix."),
        "allowed": _EDIT_AND_BUILD + [
            "mcp__prism__prism_query", "mcp__prism__prism_read",
            "mcp__prism__prism_lookup", "mcp__prism__prism_edges"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
    # Engine B -- explore is the one-call peer of prism_query (same altitude).
    "engine-b": {
        "guidance": "CONTEXT TOOL: Engine B. engine_b_explore(task/symbol) "
                    "returns relevant symbols, call paths, and blast radius in one "
                    "call -- use it as your primary context tool; impact/callers "
                    "for follow-ups. Then edit and build.",
        "allowed": _EDIT_AND_BUILD + ["mcp__codegraph"],
        "mcp": str(CFG_DIR / "engine-b.json"),
    },
}

# Forced-graph (_nogrep) variants: strip every text-search/browse tool so
# discovery MUST go through the graph -- the clean isolation, symmetric across
# graph arms. Baseline keeps grep (grep IS its tool / the control).
_SEARCH = {"Grep", "Glob", "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)",
           "Bash(ls:*)", "Bash(cat:*)"}
for _base in ("prism_g", "prism_gstar", "engine-b"):
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
    "engine-b": ("mcp__engine-b",),
    "baseline": (),
}


# prism_only (2026-08-03): the single-verb design, cloud tier. Grep/rg/find/glob
# STRIPPED; the ONLY way to find code is prism_query. change_impact for
# signature changes. Steering forbids text search explicitly.
ARMS["prism_only"] = {
    "guidance": (
        "CONTEXT TOOL: Prism, and ONLY Prism. You have NO grep, ripgrep, find, "
        "glob, ls, or cat. To find ANY code, run:\n"
        "  python3 /Users/tapabratapal/Projects/provasign/research/harness/pq.py \"<what you need>\" \"comma,separated,anchor,terms\"\n"
        "It returns the type-resolved graph answer, and automatically falls back "
        "to a text search only when the graph has nothing for those terms -- so it "
        "is never empty-handed. Pass the terms you would have grepped. For a "
        "signature/type change, also use prism_change_impact. Then Read the files "
        "it points to, edit, and build."),
    "allowed": [t for t in _EDIT_AND_BUILD if t not in _SEARCH] + [
        "Bash(python3 /Users/tapabratapal/Projects/provasign/research/harness/pq.py:*)",
        "mcp__prism__prism_change_impact"],
    "mcp": str(CFG_DIR / "prism.json"),
}

# prism_native (2026-08-05): the clean single-tool arm the merged text search
# makes fair. Unlike prism_only (which bolted a text fallback on via pq.py),
# this arm exposes the SHIPPED 15-tool MCP surface and nothing else: since
# v0.31 prism_search/prism_query run a real rg/grep full-text pass internally,
# stripping grep no longer removes a capability -- only a routing choice.
ARMS["prism_native"] = {
    "guidance": (
        "CONTEXT TOOL: the Prism MCP server, and ONLY Prism -- you have no grep, "
        "ripgrep, find, glob, ls, or cat. This costs you nothing: prism_search "
        "searches symbol names AND the raw source text (a real ripgrep pass -- "
        "error messages, config keys, comments all land), so use it exactly as "
        "you would grep. Workflow: prism_query(task=\"<the symptom>\", terms=[your "
        "search terms]) FIRST -- it returns edit-ready line-numbered source "
        "windows, callers, and raw text matches in one call; do not re-read what "
        "it shows. prism_search to locate anything else. For a signature/type "
        "change, prism_change_impact. Then Read/Edit the files and build."),
    "allowed": [t for t in _EDIT_AND_BUILD if t not in _SEARCH] + ["mcp__prism"],
    "mcp": str(CFG_DIR / "prism.json"),
}


# prism_priced (2026-08-06): prism_native + agent-priced delivery. Same
# single-tool exposure, but the guidance teaches the scope knob added after
# the first meaningful-bed run measured prism_native at ~1.5x baseline cost
# with identical resolves: the arm's steering routed every locate through
# the rich delivery. Here the agent says what it wants — a pure grep when
# it would have grepped, enrichment when it asks for it.
ARMS["prism_priced"] = {
    "guidance": (
        "CONTEXT TOOL: the Prism MCP server, and ONLY Prism -- you have no grep, "
        "ripgrep, find, glob, ls, or cat. This costs you nothing, because YOU "
        "price each request:\n"
        "- Just locating something (a string, an error message, a config key, a "
        "symbol name)? prism_search(query, scope=\"text\") is a PURE grep -- "
        "exactly the rg hits, cheapest; regex=true for patterns. Use it exactly "
        "as you would grep/rg.\n"
        "- Need real context (the code, its callers, edit-ready windows)? "
        "prism_query(task=\"<the symptom>\", terms=[your search terms]) -- one "
        "call, do not re-read what it shows.\n"
        "- Signature/type change? prism_change_impact.\n"
        "Default to the CHEAP request; escalate to prism_query only when you "
        "actually need the context, not just the location. Then Read/Edit the "
        "files and build."),
    "allowed": [t for t in _EDIT_AND_BUILD if t not in _SEARCH] + ["mcp__prism"],
    "mcp": str(CFG_DIR / "prism.json"),
}


# prism_priced_v2 (2026-08-07): the priced arm with the edit-site guard. The
# 78-cell grid left one open question: priced went 0/6 on the three coin-flip
# tasks (native 3/6) — 22% likely by chance, but with a plausible mechanism
# (cheap-first steering thinning context BEFORE the first edit; urllib3#3786
# trace: 4-7 text searches + still failed where native read full windows).
# v2 keeps cheap-by-default for LOCATING and forbids skimping at the edit
# site. This is the candidate default; the tiebreaker runs against THIS, not
# the superseded v1 — we validate what ships, not what we already replaced.
ARMS["prism_priced_v2"] = {
    "guidance": (
        "CONTEXT TOOL: the Prism MCP server, and ONLY Prism -- you have no grep, "
        "ripgrep, find, glob, ls, or cat. YOU price each request:\n"
        "- LOCATING something (a string, an error message, a config key, a "
        "symbol name)? prism_search(query, scope=\"text\") is a PURE grep -- "
        "exactly the rg hits, cheapest; regex=true for patterns.\n"
        "- But NEVER edit code you have only seen as grep hits. Before editing "
        "any function, get its real context ONCE: prism_query(task=\"<the "
        "symptom>\", terms=[the anchors you found]) -- edit-ready line-numbered "
        "windows plus callers; do not re-read what it shows.\n"
        "- Signature/type change? prism_change_impact.\n"
        "Cheap requests to FIND, full context to EDIT. Then Read/Edit and build."),
    "allowed": [t for t in _EDIT_AND_BUILD if t not in _SEARCH] + ["mcp__prism"],
    "mcp": str(CFG_DIR / "prism.json"),
}


ARMS["codegraph"] = {
    "guidance": (
        "CONTEXT TOOL: CodeGraph. codegraph_explore(query) returns the relevant "
        "symbols' source plus call paths and blast radius in ONE call -- use it "
        "as your primary context tool. codegraph_node for one symbol's source "
        "and caller/callee trail; codegraph_impact for what a change affects; "
        "codegraph_callers/callees to walk the graph. You also have grep/rg for "
        "text search. Then edit and build."),
    "allowed": _EDIT_AND_BUILD + ["mcp__codegraph"],
    "mcp": str(CFG_DIR / "engine-b.json"),
}


# baseline_fanout_steer (2026-08-07): the CONTROL the fan-out probe lacked.
# The codegraph arm scored as well as prism on the fan-out bed while calling
# its graph tool ZERO times in 6 cells — so the prism-vs-baseline coverage
# gap may be a PROMPT effect (both graph arms' steering names blast radius /
# one-call context; baseline's does not), not a tool effect. This arm has
# baseline's tools and the graph arms' framing. If it matches them, the tool
# contributed nothing on this bed and the earlier separation claim is void.
ARMS["baseline_fanout_steer"] = {
    "guidance": (
        "CONTEXT TOOL: ripgrep/grep/find and file reads only. Before editing, "
        "work out the FULL extent of the change: this issue may require the "
        "same edit in several places across the codebase. Find every site the "
        "change affects -- callers, related implementations, everywhere the "
        "pattern appears -- then edit them all and build."),
    "allowed": _EDIT_AND_BUILD,
    "mcp": None,
}
