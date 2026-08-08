"""The two arms of the ledger A/B. Identical except how the agent finds code."""
from __future__ import annotations

import json
from pathlib import Path

HOME = Path.home()
CFG = HOME / "ledger-ab" / "cfg"
CFG.mkdir(parents=True, exist_ok=True)

(CFG / "prism.json").write_text(json.dumps({"mcpServers": {
    "prism": {"type": "stdio", "command": str(HOME / "bin" / "prism"),
              "args": ["mcp"]}}}))
(CFG / "none.json").write_text(json.dumps({"mcpServers": {}}))

EDIT_AND_BUILD = [
    "Read", "Edit", "Write", "Grep", "Glob", "TodoWrite",
    "Bash(node:*)", "Bash(npm run:*)", "Bash(npm test:*)", "Bash(npx tsc:*)",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(wc:*)",
    "Bash(mkdir:*)", "Bash(touch:*)", "Bash(mv:*)", "Bash(cp:*)", "Bash(rm:*)",
    "Bash(find:*)", "Bash(grep:*)", "Bash(rg:*)", "Bash(sed:*)", "Bash(awk:*)",
    "Bash(sort:*)", "Bash(uniq:*)", "Bash(diff:*)", "Bash(echo:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git ls-files:*)",
    "Bash(cd:*)", "Bash(true:*)",
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
]

_PROJECT_RULES = """# ledger

A multi-tenant billing and payments service.

## Ground rules

- **TypeScript, ESM, Node 26.** No build step — Node runs the `.ts` sources
  directly via native type stripping.
- **Relative imports MUST carry the `.ts` extension** (`import { Money } from
  "./money.ts"`). Node fails at runtime without it.
- TypeScript **parameter properties** (`constructor(private readonly x: T)`) are
  NOT supported by Node's type stripping. Declare fields and assign them in the
  constructor body instead.
- **Dependencies are ALREADY INSTALLED.** `node_modules/` is present with
  `typescript` and `@types/node`. Do NOT run `npm install` — it is neither
  needed nor permitted. Just run `npm run typecheck` and `npm test`.
- **No third-party runtime dependencies.** Do not add any.
- Source in `src/`, tests in `test/` named `*.test.ts`, using `node:test` and
  `node:assert/strict`.
- `SPEC.md` is the frozen public contract — other teams code against those exact
  module paths, class names and signatures.
- Before finishing a work item: `npm run typecheck` passes and `npm test` passes.
- Do not create git commits.
"""

_BASE_CONTEXT = """
## Finding code

Use text search and file reads to build context.

- `rg`/`grep` to locate a symbol, a string, or a call site; `find`/`ls` to see
  what exists.
- Read the files the search points at before editing them.
- When you change a signature, rename something, or add a requirement that every
  implementation of an interface must satisfy, search the whole repository for
  every affected place — source and tests — and update them all. Note that the
  compiler will not catch a requirement that is merely *unimplemented* but still
  type-correct.
- When you need to know what is untested or unused, search for the symbol and
  check where it appears.
"""

_PRISM_CONTEXT = """
## Finding code — Prism

Prism (MCP) answers whole-task questions in ONE deterministic call and delivers
code context cheaply.

**1. Changing or auditing code? One call answers the whole task:**

| Situation | Tool |
|---|---|
| Changing a method signature | prism_change_impact(query="Type.method") — declaration + every implementation + callers |
| Adding/changing a member on an interface or base class | prism_change_impact — the whole override family |
| A requirement every implementation must now satisfy | prism_change_impact to enumerate the family, then check each |
| Adding a REQUIRED interface member ("who is now broken?") | prism_missing_implementations(query="Type.member") |
| A rename, and you want the edits not just the sites | prism_rename_plan(query="Type.method", newName="newName") |
| "What should I test?" | prism_untested_surface |
| A cleanup / "is this reachable?" | prism_dead_code |
| "How is this repo structured?" | prism_map |
| "Is my change complete?" before finishing | prism_verify |

**2. Reading code:** prism_read (whole file, SHA-pointer on repeat reads),
prism_lookup (one symbol's body, ~5x cheaper), prism_node (one symbol or file
plus its neighbours).

**3. A bug or an unfamiliar area:** prism_query(task="<the symptom>",
terms=["<one anchor guess>"]) — ONE call returning edit-ready line-numbered
source windows plus each anchor's callers and covering tests. terms is REQUIRED.

**Pre-task rule:** before writing code on a task that changes an existing symbol
or adds an obligation to an interface's implementations, call
prism_change_impact FIRST — even if the change looks small. In TypeScript a
method name like `apply`, `validate` or `handle` is shared by several unrelated
interfaces, so text search returns other types' members; change_impact returns
the type-resolved family. Check `completeness`: "closed" means authoritative.

**Relay rule:** the result is deterministic and type-resolved. Do NOT re-verify
or re-filter it through grep — re-processing a solved traversal drops real sites
and adds spurious ones. Use the sites as-is.

**Do NOT:** re-read files prism_query just delivered; grep for what it already
returned; orchestrate multi-call traversals to enumerate a change's impact.
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
