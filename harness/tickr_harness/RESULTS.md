# tickr A/B — does Prism help an agent BUILD a project?

**Date:** 2026-08-02 · **Model:** Sonnet (`claude -p`, effort medium) · **Arms:**
grep/read baseline vs Prism MCP · **Cells:** 10 complete 9-turn sessions
(small n=3/arm, large n=2/arm) · **Grading:** 155-test hidden conformance suite +
stdlib-`ast` completeness check, neither of which runs through Prism.

Every number here is new. Nothing is carried over from any earlier benchmark.

---

## The headline

**Correctness: a dead tie, at ceiling.** All 10 cells — both arms, both
conditions — finished at conformance **1.000** with **0** broken call sites and
a green self-authored test suite. There is no correctness difference to report,
because the baseline never made a mistake to begin with.

**Cost: Prism was consistently more expensive.** ~+24% tokens and +17–21% cost
in both conditions, for that identical result.

**Speed: one real win, narrow and reproducible.** On the two wide-blast-radius
refactor turns, the Prism arm was ~20% faster in wall-clock, and the per-trial
ranges do not overlap. Everywhere else the wall-clock difference is noise.

---

## What was built

`tickr`, a real-time stock tracking and prediction service (deterministic
synthetic feed, rolling store, five indicators, momentum+MACD predictor,
edge-triggered alert engine, journal/replay, portfolio valuation, CLI).

One cell = one **continuous** Sonnet session (`--session-id` / `--resume`)
walking 9 work items in a fresh git repo, the way a human and an agent actually
work through a sprint:

| # | turn | kind |
|---|---|---|
| 1 | scaffold the spec'd package + tests | build |
| 2 | add MACD, thread it through the predictor | feature |
| 3 | add tick journalling + replay | feature |
| 4 | add a **required first parameter to all 5 indicators** | refactor |
| 5 | rename `run_once`→`step`, `evaluate`→`check`, **delete** `tickr/alerts.py` | refactor |
| 6 | find and close test-coverage gaps | tests |
| 7 | P1 bug: alert spam → edge-triggered semantics | bugfix |
| 8 | portfolio forecast/valuation on the refactored API | feature |
| 9 | remove dead code, verify everything green | cleanup |

**Two conditions.** `small` is the app alone (~350 LOC). `large` is identical
for turns 1–3, then a 60-module / 2,134-LOC consumer package (`desk/`) is merged
in just before turn 4 — generated from the frozen SPEC, byte-identical in both
arms. That turns turn 4 from a ~15-site edit into a **213-site** one across 60
files, and turn 5 into **67** stale method refs + **32** stale module imports.

---

## Results

### Correctness and completeness

| condition | arm | n | conformance | broken call sites | own tests green |
|---|---|---|---|---|---|
| small | base | 3 | **1.000** | 0 | 3/3 |
| small | prism | 3 | **1.000** | 0 | 3/3 |
| large | base | 2 | **1.000** | 0 | 2/2 |
| large | prism | 2 | **1.000** | 0 | 2/2 |

In the large condition the baseline drove 213 → 0 stale indicator sites at turn
4 and 67 → 0 / 32 → 0 at turn 5. It missed nothing.

### Cost and time (per complete 9-turn session)

| condition | arm | tokens (per cell) | cost | wall |
|---|---|---|---|---|
| small | base | 9.1M, 9.6M, 10.0M | $4.28–4.67 | 9.8–10.2 min |
| small | prism | 9.6M, 11.9M, 15.8M | $4.59–6.52 | 9.9–16.1 min |
| large | base | 10.7M, 13.7M | $5.21–6.33 | 11.2–12.4 min |
| large | prism | 14.9M, 15.4M | $6.68–6.83 | 10.4–11.4 min |

Medians: Prism **+24.5%** tokens in both conditions; **+20.8%** cost (small),
**+17.1%** (large).

Note the spread. The baseline is tight (9.1–10.0M in small); the Prism arm is
wide (9.6–15.8M). The token penalty is directionally consistent but the small
condition's ranges touch — treat "+24%" as a median, not a precise effect.

### The one clean win: refactor turns (large, turns 4+5 combined)

| arm | wall-clock per trial | tokens per trial |
|---|---|---|
| base | 196s, 224s | 4.41M, 4.77M |
| prism | **149s, 180s** | 4.30M, 4.65M |

Non-overlapping ranges, ~20% faster, at equal tokens and equal (perfect)
correctness. On turn 4 alone the Prism arm ran `prism_change_impact` 5 times and
grepped **zero** times; the baseline grepped 6 times and read 19 files.

### Where Prism lost

Turn 6 (find-the-coverage-gaps) in the large condition: **4.13M tokens / $1.52**
for Prism vs **1.92M / $0.90** for the baseline — more than double, same
conformance. The task-altitude coverage path cost far more than it saved here.

### Tool use (median per session, large)

```
base : Bash=44  Read=36  Write=25  Edit=22  Grep=7   Glob=1
prism: Bash=58  Read=40  Write=26  Edit=18  change_impact=6  Grep=4
       ToolSearch=3  dead_code=1  rename_plan=1
```

The Prism arm did reach for the graph on exactly the turns it was designed for
(change_impact on the refactors, dead_code on the cleanup, rename_plan on the
rename) and cut its grepping roughly in half. It just did not convert that into
a better outcome, because there was no worse outcome available to avoid.

---

## What this does and does not show

**Shows:** for a greenfield Python service built by Sonnet over a 9-turn
session, up to ~2,500 LOC and a 213-site refactor, a code graph changes nothing
about correctness and costs about 20% more. Its one measurable benefit is
finishing wide refactors ~20% faster.

**Does not show:** anything about where Prism is actually supposed to win. Three
limits, stated plainly:

1. **The scorer saturated.** The baseline scored 1.000 in 10/10 cells. A
   benchmark whose control never fails cannot measure an improvement in
   correctness — it can only measure overhead. Every correctness claim from this
   study is bounded by that.
2. **Python with explicit imports is the friendliest possible case for grep.**
   Every call site in `desk/` was a literal `sma(` under a literal
   `from tickr.indicators import sma`. Prism's advantage is *type-resolved*
   traversal — overrides, interface implementations, indirect callers — which is
   precisely what text search cannot do and what a flat-function Python app does
   not contain. This benchmark never exercised the capability.
3. **Sonnet is strong enough not to need help here.** The published tier-invariance
   result is about weaker models reaching the engine's ceiling; a frontier model
   at 2,500 LOC is already at that ceiling with grep.

**The honest one-line version:** on this workload, Prism cost ~20% more and
bought ~20% faster refactors and nothing else. To find a correctness effect you
would need a condition where grep genuinely fails — inheritance/interface fan-out
in Java or TypeScript, a repo large enough that enumeration is not eyeballable,
or a weaker model. That is a different experiment, and this one should not be
cited as evidence for or against it.

---

## Reproducing

```
python3 tickr_ab.py --trials 3                      # small condition
python3 tickr_ab.py --condition large --trials 2    # large condition
python3 tickr_ab.py [--condition large] --report
python3 -m tickr_harness.regrade                    # re-score snapshots offline
```

Artifacts: `~/tickr-ab/{results,snapshots}[-large]/`. Every turn is snapshotted,
so grading is a pure offline function of the evidence and can be corrected
without re-running a single agent.

## Two harness bugs found mid-study (both would have corrupted the numbers)

1. **Oracle over-specification.** Four conformance tests asserted
   `pipeline.feed` / `.store` / `.alerts`, attributes SPEC never pins. An
   implementation storing them as `_feed` is fully conformant and was being
   marked wrong — it cost prism-t2 a spurious 0.974. Fixed; an AST sweep confirms
   no remaining assertions outside the contract's public surface.
2. **`platform/` shadowed the stdlib.** The seeded consumer package was
   originally named `platform`, and since the repo root is on `sys.path` it
   hijacked `import platform` and killed pytest itself — surfacing as a truncated
   JUnit file three turns in, not as anything naming the cause. Renamed to
   `desk/`, with a permanent guard that refuses any seed package name resolving
   to an importable module.

A third design flaw was caught before it mattered: the user's `~/.claude.json`
registers a Prism MCP server globally, so without `--strict-mcp-config` the
*baseline* arm would have had Prism available and the entire comparison would
have been void.
