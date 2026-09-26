# Guidance-only Comparison

Frozen before execution on 2026-09-06, following user approval to proceed.
Implements ../NEXT_TEST.md; this protocol is not edited after launch.

Eight fresh Codex cells: Gin and Django, two repeats, old/new routing paragraph.
Both arms use binary SHA256
969239d7bb991c3feb64e48d952cc1ff17d1a449a5d58df588e0a005b28440a2.
Model gpt-5.5, medium effort, Codex CLI 0.153.4, native tools available.
No source edits, history, skills, memory, delegation, other MCP servers, or network.
Corpora, prompts, model CLI command, frozen helpers, and all usage are archived.

The original panel helper and scorer are unchanged. Only the appended TOOLS
paragraph differs; exact old/new strings live in run_guidance.py. Prompt prefix
and normalized command equality are asserted for every pair. This tests CLI
routing guidance, not bootstrap behavior or the full generated instruction block.

--prepare performs MCP preflight in both arms, prepares all eight isolated
archives, verifies no git history, and checks prompt/configuration equivalence.
It launches zero models. --run requires the prepared state and unchanged hashes;
a run cannot be resumed or reused. Product and existing benchmark artifacts are
not edited during execution. Source paths and binary are pinned in the manifest.

Order: Gin r1 before/after, Django r1 before/after, Django r2 after/before,
Gin r2 after/before. Two simultaneous executions per pair. No outcome-based
retries or substitutions. All attempt costs count in this invocation, including
errors, non-use, and setup failures. Unknown cost stays unknown.

$3 launch budget, $0.75 headroom required before each pair, 600s timeout per cell.
No hard billing cap. Stop further launches on setup failure, unknown usage,
or insufficient budget. Preserve any partial run and do not label it PASS.

The frozen prior analyzer requires all eight valid cells. Acceptance, unchanged:
no paired recall loss or added false-complete answer; candidate mean recall and
precision >=95%; median paired token savings >=25%; aggregate cost savings >=30%.
Report total/input/output/cache tokens, estimated arm costs and full invocation
spend separately. Cost uses the previous study's fixed $5/$0.50/$30 per million
uncached input/cached input/output tokens; this is an estimate, not a billing invoice.

Tool diagnostics are explanatory, not token or model-request counts. Report first
successful discovery, errors, searches after impact, and batch lookups. Audit
remaining evidence gaps. No claim of statistical significance or superiority to
native Codex/Sonnet follows from this two-task guidance study. Do not pool it with
earlier panels; further held-out four-way controls are required for product claims.
