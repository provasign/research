# Model × arm benchmark — does Prism help, per tier, and at what cost?

9 change-impact tasks (Java/Go/TypeScript/Python, 8→310 sites), both arms steered, oracle-scored, medians across trials. Only the tool varies within a model row.

## Recall · turns · tokens · speed

| Model | Arm | Recall | Turns | Tokens in | Tokens out | Wall (s) |
|---|---|---:|---:|---:|---:|---:|
| local | without Prism | 0.156 | 13 | 47K | 1K | 71 |
| local | with Prism | 1.000 | 3 | 2K | 1K | 31 |
| haiku | without Prism | 0.843 | 31 | 1321K | 12K | 146 |
| haiku | with Prism | 1.000 | 5 | 127K | 6K | 59 |
| sonnet | without Prism | 1.000 | 46 | 1225K | 22K | 234 |
| sonnet | with Prism | 1.000 | 4 | 139K | 3K | 33 |
| opus | without Prism | 1.000 | 20 | 475K | 12K | 133 |
| opus | with Prism | 1.000 | 4 | 85K | 3K | 30 |

## Precision & F1 (derived) — did an arm win recall by over-reporting?

| Model | Arm | Recall | Precision | F1 |
|---|---|---:|---:|---:|
| local | without Prism | 0.156 | 1.000 | 0.270 |
| local | with Prism | 1.000 | 0.917 | 0.957 |
| haiku | without Prism | 0.843 | 0.661 | 0.741 |
| haiku | with Prism | 1.000 | 0.759 | 0.863 |
| sonnet | without Prism | 1.000 | 0.800 | 0.889 |
| sonnet | with Prism | 1.000 | 0.745 | 0.854 |
| opus | without Prism | 1.000 | 0.612 | 0.759 |
| opus | with Prism | 1.000 | 0.745 | 0.854 |

Prism precision sits at ~0.74–0.92 (not ~0.1), so it is **not** inflating recall by dumping the blast radius. Two caveats: (1) derived from recall·gt/sites_submitted (n_sites may include a few test sites the exact scorer excludes, so this slightly *under*states precision); (2) ground truth is the sites the PR *actually changed* — a subset of the full caller set `change_impact` returns — so many "false positives" are real callers that specific PR didn't touch. The engine's precision against the true blast radius is 0.948 (see RESULTS.md).

## With Prism vs without — recall gain, token savings, speedup

| Model | Recall (w/o → with) | Token savings | Turns (w/o → with) | Speed |
|---|---|---:|---|---:|
| local | 0.156 → 1.000 | 96% | 13 → 3 | 2.3× |
| haiku | 0.843 → 1.000 | 90% | 31 → 5 | 2.5× |
| sonnet | 1.000 → 1.000 | 89% | 46 → 4 | 7.2× |
| opus | 1.000 → 1.000 | 82% | 20 → 4 | 4.4× |

## Recall by language (without → with Prism, all models pooled)

| Language | without Prism | with Prism |
|---|---:|---:|
| go | 1.000 | 1.000 |
| java | 0.941 | 1.000 |
| python | 0.766 | 1.000 |
| typescript | 0.946 | 0.946 |

## Per task (recall, without → with Prism)

| Task | sites | local | haiku | sonnet | opus |
|---|---:|---|---|---|---|
| jackson-jsonnode-get | 8 | 0.000→1.000 | 1.000→1.000 | 1.000→1.000 | 1.000→1.000 |
| jackson-settable-set | 22 | 0.000→1.000 | 0.955→1.000 | 0.955→1.000 | 1.000→1.000 |
| django-quotename | 32 | 0.156→1.000 | 0.750→1.000 | 1.000→1.000 | 1.000→1.000 |
| typeorm-driver-escape | 37 | 0.351→0.946 | 0.460→0.946 | 1.000→0.946 | 1.000→0.946 |
| jackson-writetypeprefix | 38 | 0.105→1.000 | 0.895→1.000 | 1.000→1.000 | 1.000→1.000 |
| grafana-checkhealth-impact | 41 | 1.000→1.000 | 1.000→1.000 | 1.000→1.000 | 1.000→1.000 |
| grafana-querydata-impact | 51 | 0.843→0.843 | 0.843→0.137 | 0.980→1.000 | 0.902→0.980 |
| jackson-serialize | 108 | 0.556→0.556 | 0.556→0.982 | 0.982→0.982 | 1.000→0.982 |
| guava-forwarding-delegate | 310 | 0.171→0.171 | 0.171→0.690 | 0.265→0.997 | 0.997→0.997 |

## Reading this

- **Scoring is neutral/agent-level**: the answer scored is what the model itself submits, identically for both arms. This is stricter than the payload-isolation scoring behind the tier-invariance numbers in RESULTS.md (where the harness captures the engine's complete output).
- **Where the graph wins big**: tasks whose call sites are NOT named after the changing method (jackson, django, typeorm) — grep can't reach them, so baseline collapses (0.0–0.35) while Prism is complete.
- **Where grep already suffices**: some tasks (grafana Go) have lexically findable callers, so the baseline is already strong and Prism matches rather than beats it. Honest: the graph's edge is task-shaped.
- **The relay ceiling** (local tier): on the largest tasks (jackson-serialize 108, guava 310 sites) the free 30B model cannot re-type a 100–300 item list, so with-Prism recall falls to the baseline level. The engine resolves these completely; the model's relay is the bottleneck — exactly what Mason's payload isolation removes.
- **The tier story**: baseline recall is bought with model strength (0.16 local → 0.84 Haiku) and costs turns + tokens to get there; with Prism, both tiers reach ~1.0 in 3–6 turns. The graph gives a weak local model what a stronger model otherwise buys with capability.
- **Honest outlier**: grafana-querydata Haiku+Prism (0.84→0.14) — the model mis-used the tool on 2 of 3 trials (submitted the wrong/oversized site set), dragging that one task below its baseline. The engine resolves it; the model's tool use was inconsistent there.
- All four tiers complete (local + Haiku + Sonnet + Opus), 54 cells each, no fast-fails. One task (grafana-securevalue) was dropped: its corpus fixture was a 3-file stub, not the real repo.
