# Model × arm benchmark — does Prism help, per tier, and at what cost?

9 change-impact tasks (Java/Go/TypeScript/Python, 8→310 sites), both arms steered, oracle-scored, medians across trials. Only the tool varies within a model row.

## Recall · turns · tokens · speed

| Model | Arm | Recall | Turns | Tokens in | Tokens out | Wall (s) |
|---|---|---:|---:|---:|---:|---:|
| local | without Prism | 0.156 | 13 | 47K | 1K | 71 |
| local | with Prism | 1.000 | 3 | 2K | 1K | 31 |
| haiku | without Prism | 0.843 | 31 | 1321K | 12K | 146 |
| haiku | with Prism | 1.000 | 5 | 127K | 6K | 59 |

## With Prism vs without — recall gain, token savings, speedup

| Model | Recall (w/o → with) | Token savings | Turns (w/o → with) | Speed |
|---|---|---:|---|---:|
| local | 0.156 → 1.000 | 96% | 13 → 3 | 2.3× |
| haiku | 0.843 → 1.000 | 90% | 31 → 5 | 2.5× |

## Recall by language (without → with Prism, all models pooled)

| Language | without Prism | with Prism |
|---|---:|---:|
| go | 0.921 | 0.921 |
| java | 0.171 | 1.000 |
| python | 0.344 | 1.000 |
| typescript | 0.351 | 0.946 |

## Per task (recall, without → with Prism)

| Task | sites | local | haiku |
|---|---:|---|---|
| jackson-jsonnode-get | 8 | 0.000→1.000 | 1.000→1.000 |
| jackson-settable-set | 22 | 0.000→1.000 | 0.955→1.000 |
| django-quotename | 32 | 0.156→1.000 | 0.750→1.000 |
| typeorm-driver-escape | 37 | 0.351→0.946 | 0.460→0.946 |
| jackson-writetypeprefix | 38 | 0.105→1.000 | 0.895→1.000 |
| grafana-checkhealth-impact | 41 | 1.000→1.000 | 1.000→1.000 |
| grafana-querydata-impact | 51 | 0.843→0.843 | 0.843→0.137 |
| jackson-serialize | 108 | 0.556→0.556 | 0.556→0.982 |
| guava-forwarding-delegate | 310 | 0.171→0.171 | 0.171→0.690 |

## Reading this

- **Scoring is neutral/agent-level**: the answer scored is what the model itself submits, identically for both arms. This is stricter than the payload-isolation scoring behind the tier-invariance numbers in RESULTS.md (where the harness captures the engine's complete output).
- **Where the graph wins big**: tasks whose call sites are NOT named after the changing method (jackson, django, typeorm) — grep can't reach them, so baseline collapses (0.0–0.35) while Prism is complete.
- **Where grep already suffices**: some tasks (grafana Go) have lexically findable callers, so the baseline is already strong and Prism matches rather than beats it. Honest: the graph's edge is task-shaped.
- **The relay ceiling** (local tier): on the largest tasks (jackson-serialize 108, guava 310 sites) the free 30B model cannot re-type a 100–300 item list, so with-Prism recall falls to the baseline level. The engine resolves these completely; the model's relay is the bottleneck — exactly what Mason's payload isolation removes.
- **The tier story**: baseline recall is bought with model strength (0.16 local → 0.84 Haiku) and costs turns + tokens to get there; with Prism, both tiers reach ~1.0 in 3–6 turns. The graph gives a weak local model what a stronger model otherwise buys with capability.
- **Honest outlier**: grafana-querydata Haiku+Prism (0.84→0.14) — the model mis-used the tool on 2 of 3 trials (submitted the wrong/oversized site set), dragging that one task below its baseline. The engine resolves it; the model's tool use was inconsistent there.
- Local + Haiku tiers complete; Sonnet/Opus pending. One task (grafana-securevalue) was dropped: its corpus fixture was a 3-file stub, not the real repo.
