# `bench.py` — the standard benchmark runner

**This is the standard way to run a Prism benchmark. Do not write a new
one-off runner script — add a flag to `bench.py` or a suite under
`harness/tasks/` instead.**

`harness/bench.py` is the CLI entrypoint over `harness/lib/`, the one
implementation of "invoke `claude`/`codex` with optional Prism and parse the
result" (generalized from
`harness/results/daytoday-four-head-2026-09-07/run_readonly.py`, merged with
the safety properties `harness/runners/coding_suite.py` added: per-task git
templates, a real dependency-installed venv, a Prism-vs-native template
content-hash check, PATH isolation, and the protocol-violation audit).

## Layout

- `harness/lib/runner_core.py` — agent invocation, event parsing, audit,
  template/environment prep, cell execution.
- `harness/lib/scoring.py` — dispatch to `docker_eval` (coding/patch tasks)
  or the site-list oracle (impact/localization tasks).
- `harness/lib/pricing.py` — per-model API cost tables.
- `harness/lib/suites.py` — task-suite discovery from
  `harness/tasks/<suite>/*.json` and an optional `SUITE.json` per suite.
- `harness/bench.py` — the CLI (`run`, `list-suites`, `list-tasks`, `index`).

## Suites

A suite is a directory under `harness/tasks/`. It may carry a `SUITE.json`
mapping task id -> `{category, pilot}` plus a top-level `kind` (`"coding"`
for patch + `docker_eval`, `"impact"` for a structured site-list answer +
oracle). `harness/tasks/e2e/SUITE.json` and `harness/tasks/manual/SUITE.json`
are the two suites currently declared this way; adding a task to either
means editing its `SUITE.json`, not runner code.

```
python3 bench.py list-suites
python3 bench.py list-tasks --suite e2e
```

## Running a suite

`bench.py run` supports **coding-kind suites only today** (patch + docker
FAIL_TO_PASS/PASS_TO_PASS scoring) — this is the primary, best-proven task
shape. Impact/localization suites (structured site-list answers, e.g.
`harness/tasks/manual`) are scored via `harness/lib/scoring.py` but are not
yet wired into `bench.py run`; use `harness/runners/product_impact_suite.py`
for those until that support lands (see the "Deferred" note below).

```
# Preflight only: builds task/template manifest, no agents run.
python3 bench.py run --suite e2e --phase pilot --preflight-only \
    --prism-binary "$(which prism)"

# Full 2x2 matrix (claude+codex x native+prism) on the pilot task set.
python3 bench.py run --suite e2e --phase pilot --out harness/results/my-run \
    --prism-binary "$(which prism)"

# Narrow to one arm for a smoke test.
python3 bench.py run --suite e2e --tasks pallets__click__pr3244 \
    --agents claude --prism on --out /tmp/smoke

# Override models.
python3 bench.py run --suite e2e --phase pilot \
    --models claude=claude-opus-5,codex=gpt-5.5-mini --out /tmp/opus-run
```

Flags:

- `--suite <name>` — required; a directory under `harness/tasks/`.
- `--tasks id1,id2,...` — explicit task ids; overrides `--phase`.
- `--agents claude,codex` — default both; each maps to an arm prefix
  (`claude` -> `sonnet_*`, `codex` -> `gpt55_*`).
- `--models claude=<model>,codex=<model>` — override either or both
  defaults (`claude-sonnet-5`, `gpt-5.5`).
- `--prism both|on|off` — default `both` (the full native+prism matrix); use
  `on`/`off` with `--agents` to narrow to one or two arms.
- `--prism-binary PATH` — which `prism` binary to use: a system install, a
  pinned release, or one built on the fly all work. Resolution order when
  omitted: `$PRISM_BINARY` env var (legacy alias `$PRISM_V072_BINARY`), then
  `PATH` (`which prism`), then the `~/bin/prism` convention. Errors clearly,
  naming everything it tried, rather than silently picking a missing binary.
  See `lib.runner_core.resolve_prism_binary`.
- `--trials N`, `--concurrency N`, `--phase pilot|remaining|full`.
- `--out DIR` — run directory; default `harness/results/bench-<suite>-<timestamp>`.
- `--preflight-only` — validate tasks, build templates/venvs, write
  `manifest.json`, and stop before invoking any agent.

Output is the same `manifest.json` / `summary.json` / per-cell
`evidence/<cell_id>/measurement.json` schema already used across
`harness/results/*` (`cell_id`, `task`, `arm`, `tokens`, `turns`, `wall_s`,
`cost_usd`, `resolved`, ...).

## Indexing results

```
python3 bench.py index
python3 bench.py index --results-dir harness/results --out harness/results/index.jsonl
```

Scans every `summary.json` under `--results-dir` and appends one JSONL row
per cell to `--out`: `{suite, task, agent, model, prism, trial, tokens,
turns, wall_s, cost_usd, resolved, run_dir, cell_id, timestamp}`. Idempotent
and safe to re-run against a growing results directory — it dedupes by
`(run_dir, cell_id)`, so re-running after new runs land only appends the new
rows.

## Deferred

Impact/localization-task support (`bench.py run` for a `"kind": "impact"`
suite) is not implemented — `harness/runners/product_impact_suite.py`
remains the standalone entrypoint for that task shape, itself migrated to
import `harness/lib/runner_core.py` and `harness/lib/scoring.py` rather than
duplicating logic. Wiring it into `bench.py run` mainly needs a
finalize-callback (structured answer + oracle score, no source diff) and a
per-suite repo-lookup convention distinct from the coding suite's SWE-bench
corpus layout — deferred rather than done partially alongside the coding
path.
