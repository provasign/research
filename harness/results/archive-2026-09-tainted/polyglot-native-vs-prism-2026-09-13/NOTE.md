# Polyglot native vs Prism — Go/Rust/TypeScript, 2026-09-13

11 tasks (polyglot suite: 4 Go on cli/cli, 5 Rust on clap-rs/clap+ripgrep+fd,
2 TypeScript on darkreader), 3 trials, {native, Prism (window-candidate2
build)}, `--concurrency 1`, 300s/cell. 66 planned cells, $14.35 billed.

## The diff-capture bug (found and fixed mid-analysis)

`is_source_path()` defaulted to Python-only suffixes (`.py`/`.pyi`); no
call site threaded the task's actual language through. Every `.go`/`.rs`/
`.ts` edit in every cell run tonight (81 cells across 4 run dirs) was
silently classified as non-source and dropped before diffing, so every
scored cell showed `{"resolved": false, "empty_diff": true}` regardless of
whether the agent's fix was correct. First noticed when a task's own
work directory showed real, uncommitted `git status` changes despite a
scored empty diff. Fixed in research commit `bd34d3e1`
(`lib/runner_core.py`: `SOURCE_SUFFIXES_BY_LANGUAGE`, threaded via
`cell.extra["language"]`). All four affected run directories' work trees
were still on disk; every cell was rescored from the real diff with no
agent re-run.

## Results (rescored)

| | native | Prism |
|---|---:|---:|
| valid / timeouts | 28/33 / 5 | 29/33 / 4 |
| resolved (of planned) | 5/33 | 8/33 |
| billed / cost per resolved | $6.60 / $1.32 | $7.75 / $0.97 |
| mean per valid cell: turns / cost | 19.7 / $0.24 | 19.1 / $0.27 |
| native reads / whole-file / KiB | 2.9 / 0.93 / 14.5 | 3.1 / 0.90 / 12.3 |

Paired (26 task×trial pairs where both arms were valid): both resolved 5,
**native-only 0, Prism-only 0**. Every point of Prism's 8-vs-5 edge is a
cell where native timed out and Prism did not, on the same two Rust tasks
(clap-rs/clap pr4006, pr5080) — not Prism producing a different or better
patch when both arms got to finish. Reported plainly: head-to-head, on
every task where both arms completed, the tie is exact. Cost-per-resolved
inherits the same artifact and should not be read as an efficiency claim.

Per task: `darkreader pr7241` 3/3 both arms (trivial/likely memorized);
`ripgrep pr2209` 2/3 both arms; `clap pr4006`/`pr5080` favor Prism via
native timeouts as above; the remaining 7 of 11 tasks are 0/3 on both
arms — the task set discriminates correctness on 4 of 11 tasks, same
calibration gap flagged for the Python e2e suite (B3).

## Supplementary runs, same rescore

- `polyglot-raised-budget` (1200s pilot, 8 cells): `clap pr5080` now
  resolves on BOTH arms -- at 300s neither did. Budget can decide
  correctness on a Rust compile-bound task even though the earlier
  turn-count pilot showed budget does not grow turns; those are different
  claims and this run only speaks to the first.
- `polyglot-codex-check2` (Codex/gpt-5.5, 4 cells): `cli pr2108` resolved
  on Prism only (n=1); `ripgrep pr2209` resolved on both.
- `polyglot-smoke2` (3 cells): `darkreader pr7241` resolved.

None of the supplementary runs have enough trials to read as more than a
single data point each; included for completeness, not as a separate claim.
