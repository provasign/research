# Sonnet coding pilot rerun with Prism v0.72.1 — 2026-09-08

## Outcome

The two Sonnet+Prism cells from the balanced coding-suite pilot were rerun
against the released Prism v0.72.1 artifact. Task pins, prompts, Claude Code
version, model and effort, dependency setup, five-minute agent timeout, and
held-out scorer were unchanged. Only the Prism treatment cells were rerun;
the archived Sonnet-native cells remain the matched baseline.

The routing regression is fixed in this run: Sonnet's first tool call was a
Prism search on both tasks, compared with zero Prism calls in both v0.72.0
pilot cells. Both cells completed without a timeout, measurement gap, harness
error, or protocol violation.

| Task | Prism actions | Wall | Cost | Held-out result |
|---|---:|---:|---:|---|
| Click PR 3244 | 2 (`search`, `verify`) | 180.9s | $0.4972 | resolved; 28/28 target and regression tests passed |
| urllib3 PR 3786 | 4 (`search` x4) | 201.1s | $0.4995 | unresolved; target and regression sets failed |

Correctness is therefore 1/2, unchanged from the earlier Sonnet+Prism pilot.
The rerun establishes treatment adoption, not a broad coding-quality gain.
In particular, the urllib3 patch changed both `connection.py` and
`poolmanager.py`, but failed the frozen 69-test held-out evaluation.

## Click cost diagnosis

The matched archived Sonnet-native Click cell cost $0.1940 and took 202.2s;
this Sonnet+Prism cell cost $0.4972 and took 180.9s. The increase did not come
from Prism response volume: `prism_search` and `prism_verify` returned only
about 616 characters combined. It came from the model taking a longer,
iterative path after discovery.

| Measure | Sonnet native | Sonnet + Prism v0.72.1 |
|---|---:|---:|
| Turns | 10 | 27 |
| Tool calls | 9 | 26 |
| Shell calls | 7 | 17 |
| Reads | 1 | 4 |
| Edits | 1 | 3 |
| Cache-read tokens | 176,531 | 927,866 |
| Cache-creation tokens | 21,427 | 41,179 |
| Output tokens | 6,895 | 14,279 |
| Reasoning tokens | 4,248 | 8,268 |

The Prism cell explored `SpooledTemporaryFile`, hit an experimental error,
revised the patch multiple times, inspected an additional lifecycle test, and
repeated targeted and full-suite tests. Those extra turns repeatedly replayed
the growing cached context. This one pair therefore shows trajectory variance,
not evidence that Prism payload size caused the higher cost.

## Audit

- Study status: `complete`
- Audited-valid cells: 2/2
- Prism adoption: 2/2
- Timeouts: 0
- Measurement, agent, protocol, and harness errors: 0
- Claude Code: 2.1.263
- Model: claude-sonnet-5, medium effort
- Prism: v0.72.1 release artifact
- Prism artifact SHA-256:
  `e6850735a0f4b2541b801e5e8b00a755726105d2d5aedf1fd4cc88e2f0286252`

## Evidence

- `manifest.json`: task/source pins, versions, hashes, and protocol.
- `summary.json`: normalized measurements and held-out outcomes.
- `evidence/`: exact prompts, commands, transcripts, patches, final answers,
  and per-cell measurements.
- `run_code.py`: exact executed runner, narrowed to the Sonnet+Prism arm and
  labeled for Prism v0.72.1.
