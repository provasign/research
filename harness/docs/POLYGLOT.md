# Polyglot suite — Go, Rust, TypeScript (2026-09-13)

Added to test the hypothesis that Prism's benefit shows up on higher-turn,
multi-file sessions rather than small single-file bugfixes, and to stop the
benchmark being Python(+broken-Java)-only. Existing suites are untouched;
this is a new suite, `harness/tasks/polyglot/`.

## Source

[Multi-SWE-bench_mini](https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini)
(ByteDance-Seed): 400 real PRs, 50 per language across 8 languages,
difficulty-tagged easy/medium/hard by its own annotators. Downloaded once
to `/tmp/mswe/mini.jsonl` (not committed -- 315 MB; re-derive with the
snippet below if needed). Same task shape as the existing e2e suite:
`instance_id`, `repo`, `base_commit`, `problem_statement`, `patch`,
`test_patch`, `fail_to_pass`, `pass_to_pass`, plus `language` and
`difficulty` (new fields the scoring dispatch and prompt now key off).

11 tasks promoted, medium/hard tier, filtered to ≤10 files / ≤250 diff
lines (large enough to need real multi-file understanding, small enough to
plausibly finish in the 5-minute budget): 4 Go (`cli/cli`), 5 Rust
(`clap-rs/clap`, `BurntSushi/ripgrep`, `sharkdp/fd`), 2 TypeScript
(`darkreader/darkreader`, easy tier -- see TS gap below). Every task's
`fail_to_pass` was independently re-derived by our own `docker_eval.validate()`
(gold patch resolves, empty patch doesn't), not taken on the dataset's word;
one candidate (`clap-rs__clap-3225`) failed validation on a genuine
Cargo.lock/patch mismatch and was dropped, not forced.

## What changed to support this

- `scoring/docker_eval_lang.py` (new): Go (`go test -json`), Rust (`cargo
  test`, `--locked` when a `Cargo.lock` is committed), TypeScript/JavaScript
  (`npm ci` + jest, config resolved per changed test file rather than a
  hardcoded path -- see its module docstring for why: darkreader's own
  `base_commit` predates the current `tests/unit/jest.config.mjs` layout).
  Parsing is factored into pure functions (`_parse_go_json`,
  `_parse_cargo_output`, `_parse_jest_report`) covered by
  `tests/test_docker_eval_lang.py`, no Docker required for those tests.
- `scoring/docker_eval.py`: `validate`/`score` dispatch by `task["language"]`
  (default `python`, unchanged path).
- `bench.py`: `prompt_for_coding` names the right test command per language
  instead of always saying `python -m pytest`.
- `lib/runner_core.py`:
  - `prepare_environment` skips the Python venv for non-Python tasks and
    calls `prefetch_dependencies` instead (`go mod download` / `cargo
    fetch` -- both populate a *host-global* cache, so every later cell hits
    it warm with no network; `npm ci` runs directly in the template so
    `node_modules` is materialized before `prepare_cell`'s
    `shutil.copytree` carries it into each cell).
  - `agent_path()` gained `/usr/local/bin`, `/usr/local/go/bin`, and
    `~/.cargo/bin` -- cells run as host subprocesses, not containers, so a
    missing toolchain directory means the agent cannot invoke `go`/`cargo`
    at all, silently, regardless of prefetching. Caught because this
    machine has Go at a non-default path and no Rust toolchain at all
    until this session installed one (`rustup`, `--profile minimal`).
  - `run_cell` sets `GOWORK=off` unconditionally. This machine has an
    unrelated `/private/tmp/go.work` from a prior session; Go
    auto-discovers a `go.work` upward from any `/tmp` cwd, so every Go cell
    was silently pulled into the wrong module set until this was set --
    caught because a live cell burned several turns discovering and
    disabling it itself.

## Known gaps, deliberately not forced

- **TypeScript is thin.** Multi-SWE-bench_mini's other 50 TS instances are
  almost all `mui/material-ui` (a 744 MB monorepo whose tests are
  co-located `*.test.js` files, likely mocha/karma-based at the commits
  sampled, not plain jest) or `vuejs/core` (vitest, and its `f2p_tests`
  span many unrelated spec files per single-file fix -- messy to score
  cleanly). Neither was pursued this session; darkreader's 2 easy-tier
  instances are what's real right now. A genuine "high-turn TypeScript"
  task needs either a mocha runner or a vitest runner plus a smaller
  multi-file TS/JS repo than mui -- not attempted, don't claim it works.
- **Rust cells are timeout-prone at the shared 300s budget.** A native
  smoke cell on `clap-rs__clap-4006` timed out after five separate `cargo
  build`/`cargo test` cycles -- each one a real compile, not a stall. This
  is the same confound already documented for Python (`click__pr3244`):
  comparisons across a wall-clock budget are not comparable when one arm's
  language compiles and another's doesn't. Do not compare native vs Prism
  turn/cost on Rust tasks without accounting for this, and expect a higher
  timeout rate on Rust than Go/Python at the same budget.
- **The dataset is real PRs on famous repos** (GitHub CLI, clap, tokio,
  ripgrep, fd, darkreader) -- the same memorization risk flagged for `rich`
  in the Python suite applies here, more so for `cli/cli`. Not measured;
  flagging it rather than ignoring it.

## Smoke-tested, not yet benchmarked

One native cell per language ran end-to-end through `bench.py run` on
2026-09-13 (evidence not kept -- `/tmp/polyglot-smoke*`, ephemeral):
Go and TypeScript cells completed cleanly (8-10 turns, $0.08-0.16,
30-40s); the Rust cell timed out as described above. No Prism arm, no
multi-trial run, and no cost has been spent studying Prism on this suite
yet -- see the harness README/handover for the proposed next run.
