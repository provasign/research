# e2e native vs Prism (window build) — 2026-09-13

First full-set, side-by-side comparison. 7 e2e tasks (urllib3 excluded: 0/9
across builds, discriminates nothing) × {sonnet_native, sonnet_prism} × 3
trials = 42 cells, `--concurrency 1`, 300 s cap, Claude Sonnet, thinking
captured, network blocked (0 executed, 0 blocked attempts in 42 cells).
Prism: uncommitted window build (Codex default-on windows + batched-slot
fix), sha256 b751bbd981447d55…. Harness: research 75629a66.

| | native | Prism |
|---|---:|---:|
| valid / timeouts | 18/21 / 3 | 20/21 / 1 |
| resolved (of planned) | 5/21 | 7/21 |
| billed / cost per resolved | $3.42 / $0.68 | $3.80 / $0.54 |
| mean per valid cell: turns / cost | 17.9 / $0.19 | 15.1 / $0.19 |
| native reads / whole-file / KiB | 2.9 / 0.22 / 8.3 | 2.0 / 0.05 / 5.0 |
| Prism calls / follow-up-op cells | — | 1.6 / 2 of 20 |

Paired (17 task×trial pairs with both arms valid): mean Δcost native−Prism
= +$0.014 (Prism cheaper in 9/17), Δturns +2.9; both resolved 4, neither
arm resolved anything the other did not.

Per task (resolved/valid): rich pr3882 3/3 vs 3/3 (trivial, ~5 turns —
memorized); rich pr3938, click pr3228, click pr3695, werkzeug pr3006 all
0/3 vs 0/3 (neither arm passes the held-out tests — these four measure cost
only); click pr3244 native 0 valid (3 timeouts; two of the timed-out diffs
pass the held-out tests) vs Prism 3/3; click pr3466 2/3 vs 1/2 (Prism r3
timed out).

Read: on cost the arms are equal ($0.19/valid cell; paired Δ ≈ $0.01).
Prism reads ~30–40% less (fewer whole-file reads) and uses ~3 fewer turns,
but turns×thinking dominate cost so that does not show up in dollars. The
resolved edge (7 vs 5, $0.54 vs $0.68 per resolved) comes from one task,
click pr3244, where native ran out of wall clock three times with the fix
already in place — a budget artifact as much as a Prism effect. The task
set discriminates correctness on 2 of 7 tasks; B3 (task calibration, tasks
the model cannot have memorized) is the limiting factor, not the tool.
