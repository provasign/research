# batch-window-candidate2 — Tier 1 on the per-term window build (2026-09-13)

Prism binary: uncommitted prism tree = Codex's default-on bounded windows
(12:33 build) + the batched-slot fix (this session): slots count delivered
regions not visited hits; one region per term first, then a second, max 4,
same 4,000-token budget; the first-term small-symbol rule no longer
suppresses the enclosing pass. sha256 b751bbd981447d55… (see manifest.json).
Harness: research commit 75629a66 (continue past timeouts). `--concurrency 1`,
so timeouts are comparable to the two sequential n=6 baselines.

Pilot pair, Prism arm, 3 trials, Claude Sonnet, thinking captured, network
blocked. 6/6 valid, 0 timeouts (click r1 finished at 298 s of 300).

| | OLD v0.74.1 (n=6) | NEW 09:33 (n=6) | WINDOW (n=6) |
|---|---:|---:|---:|
| resolved | 2/6 | 3/6 | 3/6 (click 3/3, urllib3 0/3) |
| Prism calls / follow-up-op cells | 1.7 / 1 | 2.0 / 2 | 2.2 / 2 |
| native reads (discovery / edit-prereq) | 5.5 (4.5/1.0) | 6.5 (5.3/1.2) | 5.3 (3.7/1.7) |
| whole-file reads | 0.3 | 0.5 | 0.8 |
| KiB read | 19.6 | 28.5 | 19.7 |
| turns / cost / cost per resolved | 22.8 / $0.39 / $1.18 | 22.5 / $0.40 / $0.79 | 24.0 / $0.44 / $0.88 |

Read: neutral under the rule. Discovery reads and KiB are back to the v0.74.1
level (down from the 09:33 build), whole-file reads and cost are not better.
One cell shows the intended displacement (click r1: search + lookup, ONE
native read of 3 KiB, resolved) but it took 34 turns / $0.66 on edit-test
cycles; click r2/r3 read 26–27 KiB each despite a delivered window. urllib3
still 0/9 across builds. n=6 cannot separate a real ~20% read reduction
from run-to-run swing (single cells vary ~2x).
