# Results

This page summarizes Prism-versus-native evidence. The current section is the reference; everything below it is historical.

## Current (2026-10-21)

Source: the [Prism v0.87.39 benchmark fact sheet](https://github.com/provasign/prism/blob/main/docs/benchmarks/prism-v0.87.39-2026-10-21.md). Prism v0.87.39 (Grove v0.63.25, Astkit v0.16.10); Claude Code 2.1.302 with Claude Sonnet 5.5, headless. Arms: **native** (Claude Code's own tools, no Prism) vs **Prism CLI** (`prism init --interface cli`, no MCP server). Same task, checkout and tests in both arms.

Cost was repriced at Sonnet 5.5's 5-minute-cache prices (input $2, cache write $2.50, cache read $0.10, output $10 per million tokens). **Startup** is the first request of a session; **task cost** is everything after it. Tool calls are the agent's actions (grep, read, edit, test run, `prism` command). Requests are model API calls.

Raw records, transcripts and tallies:

- [`harness/results/change32-cli-vs-native-2026-10-21/`](harness/results/change32-cli-vs-native-2026-10-21/)
- [`harness/results/change32-v08739cand-2026-10-21/`](harness/results/change32-v08739cand-2026-10-21/)
- [`harness/results/v0837-vs-native41-2026-10-20/`](harness/results/v0837-vs-native41-2026-10-20/)

### Change work: 32 tasks (renames, signature changes)

Seeded change tasks in Python (12), Java (7), TypeScript (8) and Go (5): renaming an interface or base-class method that shares its name with unrelated methods (24), renaming a property or option (4), and changing a function's signature (4). Solved means every affected site is changed and the project's tests pass.

| | Native | Prism v0.87.39 | Prism / native |
|---|---:|---:|---:|
| Solved | 31 / 32 | **32 / 32** | |
| Task cost per task | $0.0646 | $0.0492 | **0.76×** |
| Tool calls per task | 6.8 | 4.4 | **0.65×** |
| Model requests per task (after startup) | 5.7 | 4.2 | **0.74×** |
| Startup per session | $0.0607 | $0.0626 | 1.03× |

By kind and language (Prism / native):

| Slice | Tasks | Solved native / Prism | Task cost | Tool calls |
|---|---:|---|---:|---:|
| Method rename (shared name) | 24 | 23 / 24 | 0.72× | 0.62× |
| Signature change | 4 | 4 / 4 | 0.85× | 0.60× |
| Property/option rename | 4 | 4 / 4 | 0.92× | 0.83× |
| Java | 7 | 7 / 7 | 0.74× | 0.58× |
| TypeScript | 8 | 7 / 8 | 0.74× | 0.66× |
| Go | 5 | 5 / 5 | 0.78× | 0.64× |
| Python | 12 | 12 / 12 | 0.81× | 0.69× |

Slices with 4-5 tasks show direction, not a precise figure. The Prism arm comes from the v0.87.38-vs-v0.87.39 A/B run; the native arm from the same day's native-vs-v0.87.38 run on the same tasks and setup. v0.87.38 alone measured 31 / 32 solved, 0.84× task cost, 0.76× tool calls against native.

### Bug fixes: 40 GitHub issues

Real issues filed after the model's training cutoff, from gin, chi, echo, urfave/cli, gson, jackson-databind, jackson-dataformat-xml, dubbo, hono, zod, urllib3 and pydantic. Solved means the hidden tests pass. Measured on Prism v0.87.37 (2026-10-20); v0.87.38-v0.87.39 changed change-impact delivery, not the bug-fix path, and were not re-run on this set.

| | Native | Prism v0.87.37 | Prism / native |
|---|---:|---:|---:|
| Solved | 23 / 40 | 25 / 40 | |
| Task cost per task | $0.0520 | $0.0477 | **0.92×** |
| Tool calls per task | 6.85 | 5.85 | **0.85×** |
| Model requests per task (after startup) | 5.38 | 4.92 | 0.92× |
| Startup per session | $0.0609 | $0.0626 | 1.03× |

The solve difference (25 vs 23) is within run-to-run noise; read it as the same result. 22 of the 40 are small one-file fixes (Prism 0.87× task cost, 0.88× tool calls); the other slices are too small to quote.

### Over a working session

Startup is paid once per session, task cost once per task. Projected saving of Prism vs native for a session of N tasks of one kind:

| Tasks in session | Change work | Bug fixes |
|---:|---:|---:|
| 1 | 11% | 2% |
| 10 | 21% | 7% |
| 20 | 22% | 8% |
| 40 | 23% | 8% |

The projection does not model context growth within a long session, and does not count Prism's one-time indexing (time, not tokens).

### Limits

- One model (Sonnet 5.5), one agent (Claude Code), one run per cell. Opus was not measured against native.
- The change set has 4 signature-change and 4 property-rename tasks; their rows are directional.
- Two losses were adjudicated, not dropped: Prism's werkzeug `HTTPException.get_headers` miss in the v0.87.38 run was a macOS `sed` `\b` substitution that changed nothing (Prism's change-impact listed the right sites); native missed hono `Router.match`.
- Claude Code's auto mode with Opus 5.5 adds a reminder to work through Bash with grep/cat. Under it Prism still handled 80% (CLI) / 59% (MCP) of code searches; savings under that reminder were not measured against native.

## Historical (before 2026-10-21)

Everything below predates the v0.87.39 benchmark and is kept for reference. It describes older Prism builds and an older measurement setup (MCP interface, recall/precision scoring of impact answers). The runs from that period were moved to [`harness/results/archive-2026-10-22/`](harness/results/archive-2026-10-22/) (and, for September runs, `harness/results/archive-2026-09-tainted/`). Do not quote these numbers as current.

### Nine-task paired sample

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

### Repeated trials

#### Jackson `JsonNode.get`

Three fresh paired trials were run with distinct sessions and snapshots.

| Workflow | Mean recall | Mean precision | Mean request tokens | Mean turns | Mean cost |
|---|---:|---:|---:|---:|---:|
| Native search/read | 0.625 | 1.000 | 656k | 30.0 | $0.404 |
| Prism | **1.000** | **1.000** | **215k** | **8.3** | **$0.205** |

This repeated result supports both the accuracy and efficiency direction seen in the corresponding release-gate cell.

#### Grafana external interfaces

The Grafana oracles were independently audited after early precision and recall anomalies. `QueryData` ground truth expanded from 51 to 70 sites; the earlier oracle omitted middleware implementations, another external-interface implementation, a production fake, and direct handler callers. `CheckHealth` contains 59 sites.

Deterministic current-Prism calls reached 1.0 recall on both tasks. Three fresh agent trials per task also reached 1.0 recall:

| Task | Trials | Recall | Precision range | Mean turns | Mean cost |
|---|---:|---:|---:|---:|---:|
| `grafana-querydata-impact` | 3 | 1.000 in all trials | 0.933–0.959 | 4.0 | $0.172 |
| `grafana-checkhealth-impact` | 3 | 1.000 in all trials | 0.983 | 5.0 | $0.229 |

The deterministic `QueryData` result contains the full local method family even though `backend.QueryDataHandler` is declared in an external Go dependency. That case motivated external-interface method-set resolution and compact exhaustive search inventories.

### How the numbers are produced

The scorer compares exact repository-relative sites with committed task ground truth. `harness/scoring/impact_oracle.py` validates task pins and repository identity, normalizes engine output, and fails when recall, precision, completeness, or payload crosses the task's configured floor. Agent run records include their model, invocation identifier, session identifier, transcript location, token accounting, cost, and scored answer.

No product code contains task names or expected answers. Ground truth and thresholds live in this research repository, separate from Prism and Grove. Product behavior is implemented through general call, type, interface, and search operations.

### Limits

- The nine-task table has broad task coverage and only one run per cell. Use repeated trials for claims about expected agent cost or reliability.
- Cost depends on model pricing, prompt caching, transcript length, and provider accounting. Recall and precision remain the primary correctness measures.
- Prompt caching can reuse common input prefixes. It does not expose previous answers or conversation state to a new session. The freshness audit found distinct session IDs, invocation IDs, snapshots, and transcript directories across the repeated runs.
- Ground truth is a versioned measurement instrument. The Grafana correction demonstrates why low or strangely stable precision must trigger an oracle audit before it is labeled an engine defect.
- Static analysis has boundaries: reflection, runtime registration, generated code, and unavailable language toolchains can reduce completeness. Engine results report these caveats.

### Reproduction pointers

- Harness guide: [harness/README.md](harness/README.md)
- Task definitions: [`harness/tasks/`](harness/tasks/)
- Impact-oracle reliability audit: [`harness/results/archive-2026-09-tainted/impact-oracle-reliability-2026-09-07/`](harness/results/archive-2026-09-tainted/impact-oracle-reliability-2026-09-07/)
- 2026-09-06 accuracy and efficiency campaign: [`harness/results/archive-2026-09-tainted/prism-accuracy-efficiency-2026-09-06/`](harness/results/archive-2026-09-tainted/prism-accuracy-efficiency-2026-09-06/)
- Historical multi-tier study: [harness/BENCH-MATRIX.md](harness/BENCH-MATRIX.md)
- Invalid and negative experiments: [harness/docs/SWEBENCH-AB-RESULTS.md](harness/docs/SWEBENCH-AB-RESULTS.md), [harness/docs/PR-REPLAY-FINDINGS.md](harness/docs/PR-REPLAY-FINDINGS.md)
