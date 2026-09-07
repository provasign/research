# Coding suite v1

## Claim and decision rule

This suite tests whether normal Prism availability changes correct coding work
completed per unit of time and cost. Search metrics are explanatory only.

The primary outcomes are correct fixes at a matched five-minute budget, total
wall time and cost per correct fix (including unsuccessful attempts), and
regressions. Tokens, tool calls, Prism adoption, payload bytes, and one-time
indexing cost are secondary mechanism measures.

Equal correctness at lower total cost supports an efficiency claim. More
correct fixes at the same budget supports a correctness claim. Concentrated
gains support only the corresponding task-class claim.

## Frozen initial workload

| Category | Task | Repository | Validation |
|---|---|---|---|
| Local bug | `pallets__click__pr3244` | Click | 1 fail-to-pass, 27 pass-to-pass |
| Local bug | `Textualize__rich__pr3882` | Rich | 1 fail-to-pass, 7 pass-to-pass |
| Cross-file fix | `Textualize__rich__pr3938` | Rich | 3 fail-to-pass, 158 pass-to-pass |
| Cross-file fix | `urllib3__urllib3__pr3786` | urllib3 | 6 fail-to-pass; regression set re-derived per run |
| Small feature | `pallets__click__pr3228` | Click | 2 fail-to-pass, 546 pass-to-pass |
| Small feature | `pallets__werkzeug__pr3006` | Werkzeug | 8 fail-to-pass, 128 pass-to-pass |
| Maintenance / compatibility | `pallets__click__pr3466` | Click | 1 fail-to-pass, 53 pass-to-pass |
| Maintenance / refactor | `pallets__click__pr3695` | Click | collection-aware hidden deprecation and internal-API tests |

The set is deliberately small and spans four repositories. It can establish an
initial workload result, not a broad “average coding” claim.

## Execution

`coding_suite.py` runs Sonnet and GPT-5.5, each native and with Prism v0.72.0
available through its normal generated project steering. Task prompts, model
settings, source pins, time limits, and preinstalled dependency environments
are matched within each four-cell task wave. Models may choose any available
tool; Prism adoption is an outcome.

The pilot is the predetermined Click local bug and urllib3 cross-file fix (eight
cells). Run the full 32-cell set only after the pilot passes validation,
measurement, transcript, and scoring audits.

```sh
python3 -B harness/coding_suite.py --run-dir /absolute/output --phase pilot --preflight-only
python3 -B harness/coding_suite.py --run-dir /absolute/output --phase pilot
python3 -B harness/coding_suite.py --run-dir /absolute/output --phase full
```

Every patch present when the process exits or times out is scored. Completion
status remains a separate measurement. There are no retries or quality-based
exclusions. Task and arm order are deterministic and counterbalanced.

Dependencies and Prism indexing are prepared before agent timing and recorded
separately. The run archive freezes validated target/regression node IDs,
dependency versions, source hashes, prompts, commands, transcripts, patches,
and tool measurements.

Sonnet cost is taken from Claude Code's usage record. GPT-5.5 cost is an
API-list-price equivalent computed from uncached input, cached input, and
output tokens; it is not a claim about the incremental charge of a Codex
subscription. The pricing rates, observation date, source URL, and long-context
multipliers are frozen in each manifest.

## Oracle audit findings

The earlier Werkzeug `pallets__werkzeug__pr3081` screen task is not suitable as
currently prompted. Its pinned base already contains the first attempted fix,
while its prompt reproduces the original report. Upstream PR 3081 describes a
repair to that earlier fix. Base plus hidden tests still fails five targets and
gold passes them, so the code/test oracle is real, but the natural-language
task must be rewritten and re-audited before reuse.

The following candidates were excluded:

- Werkzeug 3169 and 3162: supplied tests pass on both base and gold, so they do
  not provide an outcome discriminator for this functional scorer.
- urllib3 5020: the frozen prompt concerns whitespace in header names, while
  its patch and tests concern obsolete folded header values.

Pure behavior-preserving refactors should be added later under a separately
declared structural oracle. They must not be scored by similarity to the gold
patch.

## Validation safeguards

The Docker scorer now fails loudly if Docker is unavailable or pytest produces
no outcomes for reasons other than a real collection error. Test outcomes and
collection status are separate, and pytest continues across collection errors
so one module cannot erase the baseline results from all other modules.
