# Bigger day-to-day study — build status (started 2026-07-26)

Goal: scale the day-to-day e2e beyond the inconclusive n=5 pilot. User picked
**Large**: ~25 tasks x 4 arms (baseline / codegraph / prism_source / prism_gstar)
x {Haiku, Sonnet} x 3 trials ≈ 600 cells, ~$180-230, ~40-60h wall.

## Design (fixed)
- Task set: deliberate MIX of localized (1 src file) AND multi_site (>1) fixes —
  the pilot's fatal flaw was all-localized (where completeness can't help).
- Repos: pytest-native Python only. docker_eval = python:3.12 + pip + pytest.
  **django is OUT** — needs its own runtests.py+settings runner, not bare pytest
  (validated: django__pr21650 collection-errors). Would need a runner to include.
- Scoring: Docker fail->pass (F2P flip, no P2P regression). No model in scoring.
- Trials: 3. Tool-trace captured to see if codegraph/prism degraded to grep.
- Model tiers: Haiku (context bites hardest) + Sonnet (frontier — does effect survive).

## Pipeline built this session
- mine_2026_tasks.py: added --json-out (was print-only, `if False` dump). Mines
  merged 2026 PRs w/ src+test churn, bug/feature, not huge. Per-repo via gh.
- promote_tasks.py: build_task.build -> docker_eval.validate -> keep valid;
  classifies localized vs multi_site; resumable via runs/mining/promoted.jsonl;
  writes tasks-e2e/<iid>.json.
- run_e2e.py: FIXED codegraph index bug (init not index) + fail-loud; PRISM_TIMING.
- agg_e2e_daytoday.py: per-arm resolve/turns aggregator (extend to 4 arms + sonnet).

## Candidate yield (mined)
click 15, django 18 (unusable), werkzeug 8, rich 1. Expanding: jinja, flask,
markupsafe, itsdangerous, requests, urllib3, arrow, tox (mining in bg bhwv9ffe9).

## In flight
- bczcl7ncw: promoting click+werkzeug+rich (~24 cands) -> validated tasks.
- bhwv9ffe9: mining 8 more pytest-native repos.

## Next steps
1. Collect validated tasks; if <25, promote the newly-mined repos too.
2. Balance final set ~25: aim ~40% multi_site, spread across >=4 repos.
3. Add prism_gstar to arms; extend aggregator to 4 arms x 2 models.
4. Launch run_e2e (manifest of 25) --arms baseline,codegraph,prism_source,prism_gstar
   --models haiku,sonnet --trials 3. Resumable; runs in background over ~2 days.
5. Aggregate with per-task-kind (localized vs multi_site) breakdown — the key cut.

## Honest expectation
Change-impact win is settled ([[prism-final-numbers]]). Day-to-day pilot was a
tie ([[day-to-day-e2e-pilot]]). This study exists to either find a real
day-to-day effect on the multi_site tasks + frontier tier, or confirm the tie at
scale. Do NOT pre-commit to a positive result.

## PIVOT to Java (2026-07-26, user: "take Java projects")
Python multi-repo was a dead end (12 tasks, all localized, ~1 repo; multi_site
won't build; other repos need bespoke recipes). Java is the right corpus:
Prism's edge is largest there, and Maven STANDARDIZES build/test (one recipe).

DE-RISKED + BUILT:
- java_eval.py: maven fail->pass in docker w/ persistent ~/.m2-eval cache.
  Validated jackson pr6030 (f2p=1) AND pr6113 (MULTI_SITE, f2p=2) — the regime
  Python couldn't produce.
- promote_java.py: validating jackson pool (20 cands, 4 multi_site).
- run_e2e.py wired: _is_java/_repo_for/_score branch by task["lang"]=="java".
  java_eval.score mirrors docker_eval.score. Imports/syntax OK.
- Image: maven:3.9-eclipse-temurin-17 pulled.
- Candidate pools: jackson 20 (4 multi_site). commons-lang (360 2026 commits)
  and netty (378) available for more; netty is multi-module (needs -pl, TODO).

NEW COST REALITY: Java cells are SLOW (maven compile+test per cell ~5-15min vs
Python ~2-3min). A 30-task x 4-arm x 2-tier x 3-trial run = 720 cells could be
~100h wall. MUST bound: fewer trials (2), ~15-20 tasks, multi_site-weighted.

NEXT: (1) finish jackson validation yield; (2) one FULL agent-loop smoke cell
(worktree->prism index->claude -p->java_eval.score) to prove the loop end-to-end
on Java; (3) assemble manifest, get user go for the paid run given wall-time.
