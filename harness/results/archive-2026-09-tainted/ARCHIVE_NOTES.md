# Archive notes: tainted results from before 2026-09-24 22:02

Archived on 2026-09-25. This folder holds every benchmark result produced before the
two harness fixes below. Do not cite resolve rates or deltas from anything in it.

- Gold-fix leak (fixed in aa3a98cb, 2026-09-24 21:13). run_e2e worktrees shared refs
  with the corpus clone, so agents could see the merged fix through `git log --all`.
- PR-body prompts (fixed in 99b11ea5, 2026-09-24 22:02). Java/Go/JS/C tasks used the
  PR description as the prompt, and it often named the file to fix.

Contents:
- Top-level directories and files: moved as-is from harness/results/.
- e2e/: the cells in harness/results/e2e/ last modified before the cutoff. Newer cells
  (from the 2026-09-25 rerun and fresh-bed runs) stay in harness/results/e2e/.
- archive-pre-09-20/: the earlier archive-2026-09 folder, which also predates the fixes.
- from-research-runs/, from-harness-runs/: the old research/runs/ and harness/runs/.

These stay live in harness/results/: mining/, fresh-bed*, rerun-2026-09-25*, and the
three manifests that runners/rerun_2026_09_25.sh reads (guard-fix-run, residency-ab,
h3-movable). The manifests are task-ID lists (inputs), not results.

Scripts that read these results now point here: the token-survey analyses, the
swebench-live scorers and builders, contamination_check, and run_overnight's default
manifest. Scripts that write new results still write to live harness/results/.

fanout-*/meaningful-* candidate and promotion files went back to live results/,
because they're task-mining files used by build/mine_* and build/promote_*.

Frozen run_code.py snapshots in here point at harness/runs/daytoday-..., which didn't
exist even before this archive, so they were already broken and are left as they were.
