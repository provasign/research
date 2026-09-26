# Coding-suite pilot — 2026-09-07

## Decision

Do not start the 32-cell run yet. The execution and scoring pipeline worked,
but the GPT-5.5 Prism treatment was not delivered: both GPT Prism transcripts
say the deferred Prism tools were not exposed. Claude's initialization records
show Prism connected with all six tools, but neither Claude Prism cell chose to
call one. The observed native-versus-Prism differences therefore do not
estimate the effect of using Prism.

Fix and independently smoke-test Codex tool exposure, then repeat the entire
predetermined eight-cell pilot. Do not rerun only favorable or failed cells.

## Outcomes

| Treatment | Correct | Attempts | Regressions | Total agent time | Time / correct | Total cost | Cost / correct |
|---|---:|---:|---:|---:|---:|---:|---:|
| Native | 2 | 4 | 0 | 744.526 s | 372.263 s | $2.664083 | $1.332042 |
| Prism available | 2 | 4 | 1 | 810.230 s | 405.115 s | $3.565891 | $1.782945 |

All four Click attempts passed the 1 fail-to-pass and 27 pass-to-pass tests.
All four urllib3 attempts failed at least one of the 6 fail-to-pass tests; the
Claude Prism attempt also failed at least one of the 63 pass-to-pass tests.

These efficiency differences are descriptive only. There were zero Prism
calls in four eligible cells, the sample contains only two tasks, and the GPT
Prism cells did not have model-visible Prism tools.

## Integrity audit

- 8/8 cells completed; no timeouts, agent errors, harness errors, or native-arm
  Prism contamination.
- Prompt hashes match across all four arms within each task.
- Docker validation and scoring completed without collection errors.
- Every cell produced a source patch and was scored.
- Total recorded spend was $6.229974. GPT figures are API-list-price
  equivalents; Claude figures come from Claude Code's usage records.
- Claude Prism startup records list Prism as connected and expose search,
  query, read, lookup, change-impact, and verify.
- GPT Prism transcripts explicitly report that deferred Prism tools were not
  exposed. Prism's generated database files show the server process started,
  but startup is not the same as model-visible tool availability.
- One Claude native urllib3 attempt edited a test despite the source-only
  instruction. The scorer excluded that test edit and scored only its source
  patch. The runner was tightened after the pilot to record and exclude every
  non-source change, not only named hidden-test modules.

## Archived evidence

`manifest.json` freezes versions, task pins, source hashes, pricing, and study
settings. `summary.json` contains all eight measurements and held-out scores.
Each directory under `evidence/` contains the exact prompt, command,
transcript, final answer, source-only patch, and measurement record.
