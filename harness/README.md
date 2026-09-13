# Evaluation harness

This harness answers one concrete question: **does Prism (an MCP code-context
tool) make a coding agent better** — more correct, cheaper in tokens, fewer
turns, faster — **and is that still true over time and across models?** It
runs the same task through Claude and Codex, each with Prism registered as an
MCP server or not, and records the comparison.

It also carries an earlier, still-live research track (Mode-A tool-arm study
— see [`docs/MODE-A-STUDY.md`](docs/MODE-A-STUDY.md)), which measures a
single model's tool *arm* (text search vs. the Prism graph vs. both) rather
than agent *products*. Don't mix the two tracks' numbers; they measure
different things.

## Quick start (for an agent or a human)

```sh
cd harness

# What benchmarks exist?
python3 bench.py list-suites
python3 bench.py list-tasks --suite e2e

# Dry run: build task templates/venvs and a manifest, invoke no agent.
python3 bench.py run --suite e2e --phase pilot --preflight-only

# Real run: Claude + Codex, each with Prism on and off (2x2 matrix),
# on the pilot task subset.
python3 bench.py run --suite e2e --phase pilot --out results/my-run \
  --prism-binary "$(which prism)"   # or a pinned/built-on-the-fly binary

# Rebuild the cross-run comparison table (tokens/turns/cost/correctness
# by suite x task x agent x model x prism x time).
python3 bench.py index
```

**This is the standard way to run a benchmark. Do not write a new one-off
runner script — add a flag to `bench.py` or a suite under `harness/tasks/`
instead.** Full reference: [`docs/BENCH.md`](docs/BENCH.md).

## Benchmarks at a glance

A benchmark is a **suite**: a directory under `harness/tasks/`. A suite with
a `SUITE.json` (task id -> `{category, pilot}`, plus a `kind`) is wired into
`bench.py`; the others are task pools not yet promoted into a standard suite.

| Suite (`tasks/<name>/`) | `kind` | Curated / total tasks | Source repos (language) | Runnable via |
|---|---|---|---|---|
| `e2e/` | `coding` — real patch, scored against held-out FAIL_TO_PASS/PASS_TO_PASS tests via `docker_eval.py` | 8 / 75 | pallets/click, pallets/werkzeug, Textualize/rich, urllib3/urllib3 (Python) | `bench.py run --suite e2e` |
| `manual/` | `impact` — structured JSON site-list answer, scored against an oracle | 9 / 52 | FasterXML/jackson-databind, apache/commons-collections, apache/commons-lang, google/guava (Java); grafana, gin (Go); typeorm (TypeScript); django, flask (Python) | `runners/product_impact_suite.py` (not yet in `bench.py run` — see `docs/BENCH.md`'s "Deferred"); also the task pool for the Mode-A study |
| `e2e-fanout/` | — | 4 | mined cross-file "fanout" candidates | not yet a standard suite |
| `e2e-meaningful/` | — | 12 | mined candidates curated for non-trivial diffs | not yet a standard suite |
| `wide/` | — | 8 | a wider net across additional repos (e.g. dubbo, grove) | not yet a standard suite |
| `seeded/` | — | 1 | one seeded task | not yet a standard suite |

To add a task to `e2e` or `manual`: drop the task JSON in the suite directory
and add one entry to its `SUITE.json` — no code change. To promote one of the
other pools into a real suite, add a `SUITE.json` with a `kind` and wire it
into `bench.py run` (coding-kind suites work today; impact-kind needs the
work described in `docs/BENCH.md`'s "Deferred" section).

## Layout

- `lib/` — the standard runner library (`runner_core.py`, `scoring.py`, `pricing.py`, `suites.py`) that `bench.py` and its callers share. One implementation of "invoke claude/codex, with/without Prism, capture the result" lives here — see [`docs/BENCH.md`](docs/BENCH.md).
- `bench.py` — the standard CLI (`run`, `list-suites`, `list-tasks`, `index`).
- `runners/` — scripts that drive an actual agent/model run (`bench.py` presets like `coding_suite.py`/`product_impact_suite.py`, plus the Mode-A study's `run.py`/`run_codex.py`/`arms.py`, and other one-off A/B scripts — `mason_*.py`, `tickr_ab.py`, `ledger_ab.py`, `ab_*.py`, ...)
- `aggregate/` — post-hoc analysis of run output (`agg_*.py`, `bench_aggregate.py`, `aggregate_e2e.py`, `usage_account.py`, ...)
- `build/` — task/dataset construction (`build_*.py`, `mine_*.py`, `promote_*.py`, `extract_task.py`, `candidate_targets.py`, ...)
- `scoring/` — correctness checking (`score*.py`, `*_oracle.py`, `verify_*.py`, `validate_*.py`, `docker_eval.py`, `java_eval.py`, ...)
- `docs/` — findings write-ups and deeper reference (`BENCH.md`, `MODE-A-STUDY.md`; this README stays at the top level as the operational entry point)
- `archive/` — superseded/dead scripts, kept for history (see `archive/ARCHIVE_NOTES.md`)
- `schema.py` — stays at the harness root: `Task`/`Site`/`Scorecard` dataclasses, imported by nearly every script in every category above.

## Files

| File | Role |
|---|---|
| `schema.py` | `Task`, `Site`, `Scorecard` dataclasses; task/run JSON I/O |
| `bench.py` | Standard runner CLI — see [`docs/BENCH.md`](docs/BENCH.md) |
| `lib/runner_core.py` | Agent invocation (Claude/Codex, with/without Prism), event parsing, protocol-violation audit, template/environment prep |
| `lib/suites.py` | Task-suite discovery from `tasks/<suite>/SUITE.json` |
| `runners/arms.py` | Mode-A study: arm definitions (T / G / G\* / V) — see [`docs/MODE-A-STUDY.md`](docs/MODE-A-STUDY.md) |
| `runners/run.py` | Mode-A study runner (`claude` CLI, headless, `--output-format stream-json`) |
| `runners/run_codex.py` | Same protocol through the Codex CLI (GPT models) |
| `runners/run_local_gstar.py` | G\* arm on a local model via Ollama, backed by the real Grove engine |
| `scoring/score.py` | Mode-A scorer: recall/precision/F1, calibration, weak-match audit |
| `scoring/rescore_java.py` | **Mandatory for Java**: normalizes `file:line` answers to enclosing methods before aggregation |
| `scoring/rescore.py` / `scoring/reparse_all.py` | Re-score / re-parse existing runs after scorer changes |
| `scoring/impact_oracle.py` | Pinned, isolated one-call `change-impact` gate using the official scorer and payload/completeness thresholds — no LLM |
| `scoring/engine_ceiling.py` | Backward-compatible alias for `scoring/impact_oracle.py` |
| `scoring/docker_eval.py` | Coding-suite scorer: builds/runs the task's held-out tests against an agent's patch |
| `aggregate/agg_jackson.py` | Aggregates recall + cost per task × model × arm (auto-discovers model dirs) |
| `aggregate/mode_b_analysis.py` | Derived compile-failure metric (paper §5.5) |
| `build/extract_task.py` | Derives a task from a merged PR (Go tasks, Experiment 1) |
| `java-oracle/` | Spoon oracle — builds Java GT (own [README](java-oracle/README.md)) |
| `ts-oracle/` | ts-morph oracle — TypeScript GT ([README](ts-oracle/README.md)) |
| `py-oracle/` | Jedi oracle — Python GT ([README](py-oracle/README.md)) |
| `tasks/<suite>/*.json` | Task definitions **with GT embedded** — self-contained for scoring; see "Benchmarks at a glance" above |
| `results/` | All scored runs + transcripts (released; layout below) |
| `results/index.jsonl` | Cross-run comparison table, rebuilt by `bench.py index` |
| `tests/` | Unit tests for `lib/`, `bench.py`, and the scorer (`python3 -m unittest discover -s tests`); full list in [`tests/CATALOG.md`](tests/CATALOG.md) |
| `scoring/engine_comparison.py` | Engine-level Prism-vs-Engine B completeness sweep, no LLM — see [docs/AB-ENGINE-COMPARISON.md](docs/AB-ENGINE-COMPARISON.md) |
| `scoring/efficiency_sweep.py` | Speed + tokens for the same one-call use case, reported next to recall |
| `runners/ab_agentic_mcp.py` | Three-arm agent A/B (prism / engine-b / grep) via `claude -p` + MCP |
| `runners/ab_local_clis.py` | Local-model agentic coding across CLIs — see [docs/AB-LOCAL-CLIS.md](docs/AB-LOCAL-CLIS.md) |
| `runners/ab_mason_claude.py` | Product A/B: mason (local 30B) vs Claude Code — see [docs/AB-MASON-CLAUDE.md](docs/AB-MASON-CLAUDE.md) |
| `runners/swebench_ab.py` / `scoring/contamination_check.py` | SWE-bench A/B + the contamination measurement that voids it — see [docs/SWEBENCH-AB-RESULTS.md](docs/SWEBENCH-AB-RESULTS.md) |
| `scoring/pr_replay.py` | PR-replay task-mining pilot — see [docs/PR-REPLAY-FINDINGS.md](docs/PR-REPLAY-FINDINGS.md) |

## Mode-A tool-arm study

The arm definitions, scorer, Java line-index pitfall, engine-ceiling gate,
and runner notes for the earlier T/G/G\*/V tool-arm study now live in
[`docs/MODE-A-STUDY.md`](docs/MODE-A-STUDY.md) — read that before running
`runners/run.py`/`run_codex.py` or touching `scoring/score.py`.
