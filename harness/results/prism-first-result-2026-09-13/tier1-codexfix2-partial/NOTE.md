# tier1-codexfix2-partial

Tier 1 test of the corrected Prism build (prism dev, sha256 e08efaf5c0f4335664d7cd0cdefa696f473b990b707f3486159706b8ce101912), Prism arm, pilot pair,
3 trials planned, `--concurrency 3`. Stopped by the harness after 4 of 6 cells: two cells hit the 300 s wall-time
budget (`timed_out=True`, exit 143, no `result` event) while three cells ran concurrently under a new cross-wave pool,
and the invalid-cell rule stopped new submissions.

Results: 2 valid cells (click r2: 21 turns, $0.53, resolved; urllib3 r2: 13 turns, $0.21, not resolved).
`include_bodies=true` on the first search call: 0 of 4. Second Prism call: 0 of 4.

Harness state at run time was NOT the committed tree: `bench.py` and `lib/runner_core.py` were modified in the working
tree (cross-wave pool; python-embedded fetch detection) and `lib/cell_metrics.py` was untracked -- runner sha in
manifest.json is of that modified file. Working-tree status at persist time:
M harness/bench.py
 M harness/lib/runner_core.py
?? harness/lib/cell_metrics.py

Comparability: the two n=6 baselines (`../batch-old-v0.74.1`, `../batch-codex-fix` + `-r3`) ran cells sequentially
with 0 timeouts in 13 cells; this run's timeouts are a concurrency/rate-limit artifact (five-hour window at 77%), not a
property of the build. Timed-out cells carry `cost_usd=None`; reconstructing from per-message usage gives roughly
2.5M and 1.9M cache-read tokens (~$1 each), so the run spent about $2.5-3 for its two valid cells.
