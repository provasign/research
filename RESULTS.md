# Current results

This page is the canonical summary of current Prism-versus-native evidence. Dated reports under `harness/` remain available for reproduction and historical comparison.

## Nine-task paired sample

The latest Sonnet release-gate sample used fresh isolated sessions and repository snapshots. Native cells used the agent's ordinary search/read tools; Prism cells used the current Prism workflow. Recall and precision are scored against task ground truth.

| Task | Native R/P | Native cost | Prism R/P | Prism cost | Cost ratio |
|---|---:|---:|---:|---:|---:|
| `jackson-jsonnode-get` | 0.625 / 1.000 | $0.77 | **1.000 / 1.000** | **$0.27** | 0.35× |
| `jackson-settable-set` | 0.591 / 0.867 | $0.16 | **1.000 / 1.000** | **$0.06** | 0.38× |
| `typeorm-driver-escape` | 0.405 / 0.517 | $0.11 | **1.000 / 0.974** | **$0.07** | 0.65× |
| `django-quotename` | 1.000 / 0.230 | $0.44 | **1.000 / 0.865** | **$0.08** | 0.19× |
| `jackson-writetypeprefix` | 0.868 / 0.868 | $0.12 | **1.000 / 1.000** | **$0.08** | 0.64× |
| `guava-forwarding-delegate` | 0.171 / 0.982 | $0.51 | **0.984 / 0.950** | **$0.23** | 0.46× |
| `jackson-serialize` | 0.574 / 0.639 | $0.64 | **1.000 / 0.864** | **$0.20** | 0.31× |
| `grafana-checkhealth-impact` | 1.000 / 0.922 | $0.23 | **1.000 / 0.983** | **$0.16** | 0.70× |
| `grafana-querydata-impact` | 0.914 / 0.901 | $0.25 | **1.000 / 0.959** | **$0.13** | 0.51× |
| **Aggregate** | **0.683 / 0.770 mean** | **$3.23 total** | **0.998 / 0.955 mean** | **$1.28 total** | **0.40×** |

Prism improved recall in eight tasks, tied at full recall in one, and cost less in all nine. The 0.40× aggregate means the Prism cells cost 60% less in this sample.

Each cell is one run. Agent output varies substantially, including when the task, repository, model, and tool build are held fixed. The table is a current release-gate snapshot and must not be presented as a confidence interval or as nine repeated experiments.

## Repeated trials

### Jackson `JsonNode.get`

Three fresh paired trials were run with distinct sessions and snapshots.

| Workflow | Mean recall | Mean precision | Mean request tokens | Mean turns | Mean cost |
|---|---:|---:|---:|---:|---:|
| Native search/read | 0.625 | 1.000 | 656k | 30.0 | $0.404 |
| Prism | **1.000** | **1.000** | **215k** | **8.3** | **$0.205** |

This repeated result supports both the accuracy and efficiency direction seen in the corresponding release-gate cell.

### Grafana external interfaces

The Grafana oracles were independently audited after early precision and recall anomalies. `QueryData` ground truth expanded from 51 to 70 sites; the earlier oracle omitted middleware implementations, another external-interface implementation, a production fake, and direct handler callers. `CheckHealth` contains 59 sites.

Deterministic current-Prism calls reached 1.0 recall on both tasks. Three fresh agent trials per task also reached 1.0 recall:

| Task | Trials | Recall | Precision range | Mean turns | Mean cost |
|---|---:|---:|---:|---:|---:|
| `grafana-querydata-impact` | 3 | 1.000 in all trials | 0.933–0.959 | 4.0 | $0.172 |
| `grafana-checkhealth-impact` | 3 | 1.000 in all trials | 0.983 | 5.0 | $0.229 |

The deterministic `QueryData` result contains the full local method family even though `backend.QueryDataHandler` is declared in an external Go dependency. That case motivated external-interface method-set resolution and compact exhaustive search inventories.

## How the numbers are produced

The scorer compares exact repository-relative sites with committed task ground truth. `harness/scoring/impact_oracle.py` validates task pins and repository identity, normalizes engine output, and fails when recall, precision, completeness, or payload crosses the task's configured floor. Agent run records include their model, invocation identifier, session identifier, transcript location, token accounting, cost, and scored answer.

No product code contains task names or expected answers. Ground truth and thresholds live in this research repository, separate from Prism and Grove. Product behavior is implemented through general call, type, interface, and search operations.

## Limits

- The nine-task table has broad task coverage and only one run per cell. Use repeated trials for claims about expected agent cost or reliability.
- Cost depends on model pricing, prompt caching, transcript length, and provider accounting. Recall and precision remain the primary correctness measures.
- Prompt caching can reuse common input prefixes. It does not expose previous answers or conversation state to a new session. The freshness audit found distinct session IDs, invocation IDs, snapshots, and transcript directories across the repeated runs.
- Ground truth is a versioned measurement instrument. The Grafana correction demonstrates why low or strangely stable precision must trigger an oracle audit before it is labeled an engine defect.
- Static analysis has boundaries: reflection, runtime registration, generated code, and unavailable language toolchains can reduce completeness. Engine results report these caveats.

## Reproduction pointers

- Harness guide: [harness/README.md](harness/README.md)
- Task definitions: [`harness/tasks/`](harness/tasks/)
- Impact-oracle reliability audit: [`harness/results/impact-oracle-reliability-2026-09-07/`](harness/results/impact-oracle-reliability-2026-09-07/)
- Current accuracy and efficiency campaign: [`harness/results/prism-accuracy-efficiency-2026-09-06/`](harness/results/prism-accuracy-efficiency-2026-09-06/)
- Historical multi-tier study: [harness/BENCH-MATRIX.md](harness/BENCH-MATRIX.md)
- Invalid and negative experiments: [harness/docs/SWEBENCH-AB-RESULTS.md](harness/docs/SWEBENCH-AB-RESULTS.md), [harness/docs/PR-REPLAY-FINDINGS.md](harness/docs/PR-REPLAY-FINDINGS.md)
