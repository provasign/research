# Scoped Lookup Binary Comparison

Frozen before the first model invocation, 2026-09-06. This is a diagnostic
eight-cell comparison, not the native-baseline product acceptance study.

## Treatment and controls

- Gin `gin-4645` and Django `django-connparams`, two repeats, before/after.
- Before binary SHA256: `969239d7bb991c3feb64e48d952cc1ff17d1a449a5d58df588e0a005b28440a2`.
- After binary SHA256: `ac41360cd212fce40bd627884d3a606720d59e235806cd97978abb5cd2d0867d`.
- Codex CLI 0.153.4, `gpt-5.5`, medium effort, unchanged frozen exact-site scorer.
- Both arms receive the prior study's NEW_GUIDANCE verbatim. No candidate-only
  prompt teaching scoped objects. Binary schemas/descriptions are part of treatment.
- Every cell receives a fresh, pinned archive, separately indexed, with no HEAD.
  Task text, native tools, MCP approvals, answer schema and CLI settings are equal.
- Ignore user config, disable memories, web search, apps, hooks and delegation.
  Prompts forbid other repositories, benchmark access and network; this is a
  prompt restriction, not a claim of perfect OS-level read/network confinement.
- Paired concurrent execution; submission order: Gin r1 before/after, Django r1
  before/after, Django r2 after/before, Gin r2 after/before. Provider cache and
  backend nondeterminism are observed, not controlled. Same-length arm paths.

## Accounting and stopping

- Zero quality-based retries or selective exclusions. One invocation only;
  the runner rejects resume/reuse. Ordinary model/tool errors remain evidence.
- 600 seconds per cell. Setup failures or unknown usage stop later pairs;
  already-started peers finish and are retained. An incomplete study is inconclusive.
- $3 fixed-rate estimated launch budget, $.75 reserve before each pair. This is
  not a hard billing cap; launched calls can exceed the reserve.
- All attempts in this invocation count toward spend. Historical runs do not.
  Missing usage or a lost attempt makes total spend unknown, never zero.
- Count input (including cached input) plus output from CLI `turn.completed`.
  Reasoning is an output subset, not an extra addition.
- Keep the prior comparison's fixed rates: $5/M uncached input, $.50/M cached
  input, $30/M output. These are API-equivalent estimates, not subscription or
  invoice reconciliation. OpenAI documents a premium above 272K input context;
  the fixed-rate estimate excludes that premium, and aggregate session counters
  do not establish individual-request eligibility. Source checked 2026-09-06:
  https://developers.openai.com/api/docs/models/gpt-5.5

## Frozen decision and diagnostics

Reuse the existing eight-cell analyzer without changes: no paired recall loss,
no added false completeness, candidate mean recall/precision >=95%, median
paired token saving >=25%, aggregate estimated cost saving >=30%. All eight
arm-valid measurements are required. Both efficiency checks must pass.

Report per-pair and aggregate results, including regressions. Count post-impact
searches, lookups and native commands; separately inspect scoped-object adoption,
errors, misses and omissions in raw tool calls. These diagnostics cannot change
eligibility or thresholds. Do not pool with or compound savings from prior studies.

Passing is only permission to test fresh native Sonnet/Codex controls on broader
held-out tasks, not proof of universal savings. Failure is actionable evidence.

## Reuse and audit

Research-only wrapper imports the frozen runner, execution loop, scorer and
analyzer. It overrides only directory bindings, binary/prompt preparation and
identity verification. Original harness imports are hash-checked against the
snapshot, with scorer modules loaded from that snapshot. The unused bootstrap
Jackson task in the legacy import is replaced before every pair. No old helper
is edited. Hash inputs before launch and each pair; independently replay raw
usage and exact site sets before archiving. Product repository receives reports
only; raw transcripts, checksums and runnable evidence remain in research.
