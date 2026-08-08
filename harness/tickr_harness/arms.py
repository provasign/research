"""The two arms of the tickr greenfield A/B.

Everything is identical between arms except HOW THE AGENT FINDS CODE:

  base  — ripgrep/grep/find + file reads. What a coding agent does today.
  prism — the Prism MCP server at task altitude, plus the Prism section of the
          project CLAUDE.md that a real Prism user has in their repo.

Both arms get:
  - byte-identical turn prompts (tasks.py) and the same SPEC.md,
  - the same edit/build/test tool surface,
  - a CLAUDE.md with the same project rules, and a context-tool section of
    comparable length, so neither arm is advantaged by having been told more
    about how to work,
  - --strict-mcp-config, which matters: the user's ~/.claude.json registers a
    prism MCP server globally, and without the flag it would leak into the
    baseline arm and silently destroy the comparison,
  - --setting-sources project, so no user-level settings (including a
    bypassPermissions default) apply to either arm.
"""
from __future__ import annotations

import json
from pathlib import Path

HOME = Path.home()
CFG = Path.home() / "tickr-ab" / "cfg"
CFG.mkdir(parents=True, exist_ok=True)

(CFG / "prism.json").write_text(json.dumps({"mcpServers": {
    "prism": {"type": "stdio", "command": str(HOME / "bin" / "prism"),
              "args": ["mcp"]}}}))
(CFG / "none.json").write_text(json.dumps({"mcpServers": {}}))

# What both arms may do to actually build, test and run the app. Deliberately
# generous: a permission denial mid-run would be an artefact, not a finding.
# The runner records permission_denials per turn so any denial is visible.
EDIT_AND_BUILD = [
    "Read", "Edit", "Write", "Grep", "Glob", "TodoWrite",
    "Bash(python3:*)", "Bash(python:*)", "Bash(pytest:*)",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(wc:*)", "Bash(mkdir:*)", "Bash(touch:*)", "Bash(mv:*)",
    "Bash(cp:*)", "Bash(rm:*)", "Bash(find:*)", "Bash(grep:*)",
    "Bash(rg:*)", "Bash(sed:*)", "Bash(awk:*)", "Bash(sort:*)",
    "Bash(uniq:*)", "Bash(diff:*)", "Bash(echo:*)", "Bash(git status:*)",
    "Bash(git diff:*)", "Bash(git ls-files:*)", "Bash(cd:*)", "Bash(true:*)",
]

PRISM_TOOLS = [
    "mcp__prism__prism_query", "mcp__prism__prism_read",
    "mcp__prism__prism_lookup", "mcp__prism__prism_node",
    "mcp__prism__prism_search", "mcp__prism__prism_resolve",
    "mcp__prism__prism_references", "mcp__prism__prism_edges",
    "mcp__prism__prism_change_impact", "mcp__prism__prism_rename_plan",
    "mcp__prism__prism_missing_implementations",
    "mcp__prism__prism_untested_surface", "mcp__prism__prism_dead_code",
    "mcp__prism__prism_map", "mcp__prism__prism_index",
    "mcp__prism__prism_drift", "mcp__prism__prism_verify",
    "mcp__prism__prism_arch_check", "mcp__prism__prism_cycles",
]

# ---------------------------------------------------------------- CLAUDE.md
# Shared half: the project rules. Identical text in both arms.
_PROJECT_RULES = """# tickr

A real-time stock tracking and prediction service.

## Ground rules

- Python 3.11+, **standard library only** for anything the package imports at
  runtime. `pytest` is available for tests.
- No network access. The market feed is synthetic and deterministic.
- The package is `tickr/` at the repository root; tests are in `tests/`.
- `SPEC.md` is the frozen public contract. Other teams code against those exact
  module paths, names, and signatures.
- Indicator and prediction code must never raise on short input — return `None`.
- Before finishing a work item: every module imports cleanly, and
  `python3 -m pytest tests -q` passes.
- Do not create git commits.
"""

# Arm half: how to find code. Comparable length and specificity in both arms.
_BASE_CONTEXT = """
## Finding code

Use text search and file reads to build context.

- `rg`/`grep` to locate a symbol, a string, or a call site; `find`/`ls` to see
  what exists.
- Read the files the search points at before editing them.
- When you change a function's signature or rename something, search the whole
  repository for every place that refers to it — production code and tests —
  and update them all. A missed call site is a broken build.
- When you need to know what is untested or unused, search for the symbol and
  check where it appears.
"""

_PRISM_CONTEXT = """
## Finding code — Prism

Prism (MCP) answers whole-task questions in ONE deterministic call and delivers
code context cheaply. Three layers, in priority order.

**1. Changing or auditing code? One call answers the whole task:**

| Situation | Tool |
|---|---|
| Renaming/changing a method signature | prism_change_impact(query="Type.method") — declaration + overrides + callers |
| Adding/changing a method on an interface or base class | prism_change_impact — override family + all callers |
| Renaming a class or type | prism_change_impact for each public method — all usages |
| ANY task that says "find all X" for a specific method | prism_change_impact first, before any grep |
| Renaming and you want the edits, not just the sites | prism_rename_plan(query="Type.method", newName="newName") — every edit line with before/after |
| Adding a REQUIRED member to an interface/base class | prism_missing_implementations(query="Type.method") |
| "What should I test?" | prism_untested_surface |
| Cleanups, "can I delete this?" | prism_dead_code — unreachable production symbols, safe-to-delete list |
| "How is this repo structured?" | prism_map — components + dependency edges |
| "Is my change complete?" before finishing | prism_verify — missed change-impact sites, line-precise |

**2. Reading code? Prism reads are cheaper than shell reads:**

| Situation | Tool |
|---|---|
| Read a whole file | prism_read — SHA-pointer (~10 tokens) on repeat reads |
| Read one function body | prism_lookup(name="pkg.FuncName") — ~5x cheaper than prism_read |
| Orient on ONE symbol or file | prism_node — source plus a neighbour menu |

**3. Fixing a bug or exploring an unfamiliar area? ONE prism_query call:**

prism_query REQUIRES terms — guess ONE keyword from the task first.

| Situation | Tool |
|---|---|
| Bug report, error message, or unfamiliar area | prism_query(task="<the symptom>", terms=["<your best guess>"]) — ONE call; returns verbatim line-numbered source windows (edit-ready) + per-anchor callers |
| Locate a plain string or file | shell tools (grep, find, rg) — not Prism |

**Pre-task rule:** before writing any code on a task that changes or renames an
existing symbol, call prism_change_impact FIRST — even if the change looks
small. Result groups: declarations + family + callers + declaringTypes = every
site that must change. Check `completeness`: "closed" means authoritative.

**Relay rule:** the result is deterministic and type-resolved. Do NOT re-verify,
re-filter or dedup it through grep/sed/scripts — re-processing a solved
traversal drops real sites and adds spurious ones. Use the sites as-is.

**Do NOT:** re-read files prism_query just delivered as source windows (they are
verbatim and current — go straight to the edit); grep for what prism_query
already returned; orchestrate multi-call traversals to enumerate a change's
impact (prism_change_impact computes the complete set in one call).
"""

ARMS = {
    "base": {
        "claude_md": _PROJECT_RULES + _BASE_CONTEXT,
        "allowed": EDIT_AND_BUILD,
        "mcp": str(CFG / "none.json"),
        "index": False,
    },
    "prism": {
        "claude_md": _PROJECT_RULES + _PRISM_CONTEXT,
        "allowed": EDIT_AND_BUILD + PRISM_TOOLS,
        "mcp": str(CFG / "prism.json"),
        "index": True,
    },
}
