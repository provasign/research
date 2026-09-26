# SWE-bench-Live A/B results — reset 2026-08-16

Everything produced before this date was **deleted**, not archived-in-place,
because it was measured on a bench with two defects that changed the sign of
the headline number. Keeping it invites citing it.

## Why

**1. The permission allowlist was measuring itself.** `--allowedTools`
enumerated binaries (`git`, `grep`, `python3`, …) and the enumeration did not
match how Python projects are built. Across 380 denials in one 38-task run:
`uv` 93, `PYTHONPATH=… python3` 46, `ls`-in-a-pipeline 32, `env` 15, plus
`pip`, `pytest`, absolute venv paths. None dangerous — all absent. An env-var
prefix cannot be expressed as a binary pattern at all, so enumeration could
never have covered it.

The effect was not noise, it was sign:

    corr(delta-denials, delta-turns) = +0.89
    corr(delta-denials, delta-cost)  = +0.76

    |delta-denials| >= 5   n= 4   median delta-cost -1.070   delta-turns -29.5
    |delta-denials| <  5   n=26   median delta-cost +0.035   delta-turns  -1.0

Every large swing was a cell where one arm hit the allowlist harder than the
other. A reported "prism is cheaper on average" was four cells of allowlist
luck.

**2. The prism arm carried a grep denial from a reverted release.**
`prism init --deny-builtin-search` kept being called for three prism versions
after v0.52.0 removed the denial from the product. An arm that cannot grep
makes "the agent chose prism" unfalsifiable, and it reads as *adoption* in
every downstream metric — a broken run that looks like a good result.
Confirmed present in `sonnet38` (43 denials) and `haiku38` (68).

Both are fixed in `swebench_ab.py`. Neither is detectable in the aggregates,
which is exactly why the old numbers had to go rather than be annotated.

## What survived, and why it is not a result

- **`phase1/`** — the BED. 80 mined candidates, `valid-instances.json` (the
  38 gold-validated tasks), and `gold-verdicts.json` from three independent
  gold-validation passes. This is task provenance, produced by running the
  SWE-bench Docker oracle on GOLD patches. It is unaffected by the agent-side
  defects above.
- **`slice-*.json`** — task definitions derived from the bed.
- **`bedcheck/`** — the first post-correction run, kept as the evidence the
  fix works: 1 task, 2 arms, **0 permission denials in both** (comparable
  cells previously had 8 and 25), no gold-fix attempts, and
  `python3 -m venv /tmp/… && /tmp/…/bin/pip install -e .` ran.

## Before spending on a new run

    python3 audit_bed.py runs/swebench-live/slice-ab38.json --wt   # exit 1 = do not run
    python3 -m pytest test_swebench_ab.py -q                       # 8 checks, free

`audit_bed.py` asserts: HEAD == base_commit; no refs and no remote (the gold
fix unreachable by discovery); the gold patch still APPLIES to the checkout
(line-comparison is not enough — patches legitimately re-add lines that
already exist); no diff and no verbatim gold lines in `problem_statement`;
baseline worktrees free of prism config; prism worktrees free of deny rules;
the repo cache outside `/tmp` with intact git metadata.

The test file asserts the permission boundary holds in every arm. That
matters more than it sounds: with Bash now allowed broadly, the denylist is
the ONLY thing between an agent and the answer. One real cell
(`beetbox__beets-5890`) ran `gh pr view 5890 --json title,body,files` twice
and WebFetch'd the PR's files page. The instance_id leaks the PR number, so
this is a live threat.

## Reporting rules for whatever replaces this

- **Resolve-rate FIRST.** Every number deleted here was efficiency-only,
  because correctness scoring needs Docker and was never run. Cost at unknown
  resolve-rate is uninterpretable: one arm may simply have done less.
- **Median and paired deltas, not means.** Single cells swing 30–60 turns.
  `python__mypy-19705` ran 39, 24 and 64 turns across three near-identical
  configurations.
- **Report denial deltas alongside cost.** If the +0.89 correlation comes
  back, the bench is measuring itself again.
- **Record provenance.** Every run writes `prism_provenance.json` (binary
  sha256, version, advertised MCP tool list). "Which build produced these
  numbers" must not depend on shell history.

Old results remain in git history (`git log -- harness/runs/swebench-live`)
if a specific cell ever needs recovering. They should not be cited.
