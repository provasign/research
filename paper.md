# When Does a Code Graph Help an Agent? Blast-Radius–Bounded Gains for Change-Impact

**Status:** working draft (bounded-positive reframe, 2026-06-27). Thesis and
falsifiable sub-claims in `THESIS.md`; raw per-run data in `harness/runs/`, scored
deterministically by `rescore.py` / `rescore_java.py` against independent oracles
(Go: `go-ssa-vta`; Java: a Spoon type-resolution oracle, `harness/java-oracle/`).

> Honesty note. An earlier version of this paper reported a *negative* result
> ("code graphs don't beat text search"). That conclusion was **too broad**: it
> was drawn from Go tasks that were, in hindsight, almost all small and
> name-greppable. Extending the study to a larger, polymorphism-heavy Java
> framework (jackson-databind) — with a precise type-resolution oracle and a size-
> graded task set — surfaced the boundary the Go data had missed. The honest
> result is **conditional**: the graph's value is real but **bounded to large-
> blast-radius change-impact tasks**. We report exactly where it helps, where it
> doesn't, and the mechanism that predicts which is which.

---

## Abstract

A widespread intuition holds that giving an LLM coding agent a resolved code graph
(callers, callees, implementors, dispatch) makes it more effective on existing
code than plain text search (grep/ripgrep + read). In a controlled, paired study
that isolates the context mechanism and scores against independent compiler-grade
oracles, across two languages (Go, Java), 2–3 model tiers, and tasks spanning
1–108 change-sites, we find the intuition is **true but conditional**:

- **On small / name-greppable change-impact tasks, graph ≈ text** (recall tied).
  This covers most of our Go sample and the small Java tasks. A capable agent
  reaches the same recall by grep+read because the call sites are statically
  named and few enough to enumerate.
- **On large-blast-radius tasks (≈100 change-sites), the graph is a capability
  equalizer.** It lifts weaker models toward frontier-level completeness: on
  jackson-databind's `serialize`/`deserialize` interface methods (104–108 sites)
  it raises mean recall by **+0.24/+0.17 (Haiku)** and **+0.13/+0.17 (Sonnet)**
  and collapses variance (Sonnet text 0.87 swinging to 0.73 vs graph 0.996 ± ~0).
  **The recall gain shrinks with model capability and, at the frontier (Opus),
  vanishes on tasks the model can fully enumerate (serialize: T=G=1.00) but
  persists on harder ones (deserialize: T 0.92 with a 0.71 dip vs G 0.96 —
  higher, more consistent, and cheaper).** So the graph's frontier value is
  reliability + cost on hard changes, not raw recall.
- **The discriminator is blast radius (#change-sites), not name ambiguity and not
  language per se.** Counter to our pre-registered guess, the graph did *not*
  win more on name-ambiguous targets (`get`/`set`, 18–64× grep over-match); those
  tasks were small and tied. Go simply rarely produced tasks large enough to
  cross the threshold.
- **Cost reframes from "cheaper" to "better at the same price."** The graph
  reaches its higher recall at **near-equal cost** (G/T ≈ 1.0–1.07 in tokens and
  USD). On large tasks, text cannot reach the graph's recall at *any* reasonable
  budget — it misses sites it never finds.

We give the mechanism (text cannot reliably enumerate a 100-site change-set;
the graph traverses it systematically), the boundary it predicts, and argue the
field should evaluate code-context tools on **completeness-and-consistency at
fixed cost, conditioned on task size** — not on a blanket "graphs help" or
"graphs don't."

---

## 1. Introduction

LLM coding agents work on existing code through a loop: **locate** relevant code
(search), **read** it, **traverse** structure (who calls / what implements), and
**stop** when subjectively confident. Two paradigms supply the context: text
search, and a resolved code graph. The graph holds strictly more accurate
structural information, so the natural hypothesis is that it produces more
complete, better-calibrated behavior on change-impact tasks, where a missed call
site is a broken build.

We set out to confirm this in Go and **could not** — graph tied text on
completeness and calibration. The honest reading at the time was a negative
result. But our Go tasks, after outcome-blind auditing, were almost all *small*
(1–22 change-sites) and *name-greppable*. The question the Go data could not
answer was whether the graph earns its keep where text search structurally
struggles. We therefore extended the study to **jackson-databind**, a
polymorphism- and reflection-heavy Java framework whose interface methods
(`JsonDeserializer.deserialize`, `JsonSerializer.serialize`, …) have dozens of
implementations and call sites — and built a **size-graded** task set with a
precise type-resolution oracle. That extension found the boundary.

Contributions:

1. **A methodology that isolates the tool across two languages** — identical
   tasks, three arms (text / graph / graph-as-verifier), enforced tool
   allowlists, scored against **independent** oracles (Go `go-ssa-vta`; a new Java
   Spoon oracle that resolves every call site by type, not by name).
2. **The conditional result**: graph ≈ text on small/greppable change-impact
   tasks; graph ≫ text on large-blast-radius tasks, on recall **and** variance.
3. **The discriminator** — blast radius, established against a confound we
   expected to matter (name ambiguity) and which did not.
4. **A reliability finding** the single-tier Go study missed: at scale the graph
   removes catastrophic completeness misses, not just lifts the mean.
5. **A reproducible Java change-impact oracle + size-graded task generator**
   (`harness/java-oracle/`) and a scoring fix (line→method normalization) without
   which the graph arm is silently under-credited.

---

## 2. A variable framework for agent code-context

Three cost axes — **tokens, latency, round-trips, setup**; six quality axes —
**completeness, precision, calibration, consistency, freshness, determinism**; one
outcome — **task success**; one meta-variable — **cost-of-error**. Our prior
belief was that the graph's value lived in the quality axes uniformly. The result
below is that it lives in **completeness + consistency, but only past a task-size
threshold**, and at near-zero extra cost — so the right figure of merit is
*quality-at-fixed-cost conditioned on blast radius*.

---

## 3. Study design

**Arms** (only the tool description/allowlist differs): **T** text (rg/grep/read),
**G** graph (typed `prism` call-graph CLI for traversal + rg for anchor discovery),
**V** text-primary with graph-as-verifier. Arm enforcement is by `--allowedTools`
with a recorded `tool_trace`; runs where the G arm never touched the graph are
flagged (`violation`) and excluded.

**Mode A (context quality):** the agent answers "list every site that must change
to do X," declaring `complete` + `unresolved`. Isolates the tool from
patch-writing skill. (Mode B / compile-and-test is future work, §7.)

**Independent oracles — never the graph under test.**
- *Go:* the `go-ssa-vta` call graph (via `grove-eval`) and/or the merged-PR diff
  (codegen/mocks filtered).
- *Java:* a **Spoon type-resolution oracle** (`harness/java-oracle/`). Given a
  target method, it emits the declaration + the full override/implementation
  family + every call site whose executable **resolves** (by type, not by name)
  into that family. This is the discipline a bare-name oracle lacks: a call to an
  unrelated same-named method on a different type is excluded. On jackson it
  resolved all ~500 `get`/`set` call sites and kept only the ~3–22 that are truly
  jackson's (0 unresolved). GT is human-spot-checked and, where text reaches it,
  validated by a text arm hitting recall 1.0.

**Scoring fix (Java).** `prism` reports authoritative `file:line`, so graph-arm
agents naturally answer sites as `File.java:114` rather than `File.java:method`.
The name-based scorer matched those at 0, silently penalizing the **graph** arm
(e.g. a 148-site correct answer scored 0.0). We build a Spoon line→method index
and normalize numeric answers to their innermost enclosing method before scoring
(`rescore_java.py`). All Java numbers below are post-normalization.

**Subjects & size grading.** Go: 14 tasks, 1–93 sites (localization controls,
greppable enumeration controls, change-impact). Java: jackson-databind @ 2.18.8,
6 interface-method signature-change tasks spanning **8, 22, 38, 58, 104, 108**
change-sites, chosen to trace a size curve and to vary name-ambiguity
independently of size. **Models:** Haiku, Sonnet (Opus in progress). **Trials:** 5
per cell; we report tails (min, variance), not just means.

---

## 4. Results

### 4.1 Small / greppable change-impact: graph ≈ text (the Go null, and small Java)

Across the Go tasks, mean recall(G) ≈ recall(T) (within ~0.01–0.07 every task; no
consistent direction). Greppable controls reach recall ≈1.0 for every arm. The
small Java tasks behave identically: `jsonnode-get` (8 sites) and `settable-set`
(22 sites) tie (Δrecall ≤ 0.01) on Haiku — *despite* being the most name-ambiguous
targets in the set (grep over-match 64× and 18×). Ambiguity did not help the
graph.

### 4.2 The size curve: the graph wins at scale, ties in the middle (Java)

The full size-graded curve (recall, n=5, post-normalization). Haiku ran the 4
original tasks; Sonnet and Opus ran all 6:

| task | sites | Haiku T | Haiku G | Sonnet T | Sonnet G | Opus T | Opus G |
|---|---|---|---|---|---|---|---|
| jsonnode-get | 8 | 0.97 | 0.97 | 0.78 | **0.93** | 0.93 | 0.95 |
| settable-set | 22 | 0.90 | 0.91 | 0.93 | 0.97 | 0.97 | 0.99 |
| writeTypePrefix | 38 | — | — | 0.97 | 1.00 | 1.00 | 1.00 |
| serializeWithType | 58 | — | — | 0.99 | 1.00 | 0.99 | 1.00 |
| deserialize | 104 | 0.52 | **0.69** | 0.76 | **0.93** | 0.92 | **0.96** |
| serialize | 108 | 0.62 | **0.85** | 0.86 | **1.00** | 1.00 | 1.00 |

The graph's **recall** advantage is largest for the weakest model on the largest
tasks (Haiku, 104/108: +0.17/+0.24), shrinks as the model strengthens, and is
≤0.04 everywhere at the frontier — Opus reaches near-perfect recall by text. At
that point the graph's payoff moves to **cost** (§4.5): it ties on recall but is
20–36% cheaper on the mid/large tasks.

The robust, large signal is at the **large tasks (104/108): graph +0.13 to +0.24,
both tiers.** The **mid-size dispatch tasks (38/58) tie on recall** — Sonnet's text
arm maxes out (0.97–0.99) because their change-sets are small and the call sites
are name-matched. And the advantage is **not** explained by grep ambiguity, which
runs opposite to the effect (the most ambiguous targets are the smallest).

**The one small-task exception is mechanistically informative.** On `jsonnode-get`
(8 sites) Sonnet's *text* arm drops to 0.78, and the graph recovers it (+0.15).
The sites text consistently missed are `JsonNode.has`, `JsonNode.hasNonNull`, and
`ArrayNode._at` — methods that **call** `get(int)` but whose own names do **not**
contain "get." A grep-for-`get` agent finds the get-named declarations and call
lines but misses *callers named after something else*; the graph's caller edges
return them directly. So the true predictor is not raw size but **the number of
change-sites reachable only via caller edges, not by the target's name** — which
grows with blast radius (the large tasks have many such indirect callers) but can
bite even a tiny task. Haiku tied on this task by luck of sampling; Sonnet's text
runs did not. This is the sharpest single illustration of the mechanism.

### 4.3 The gain survives a stronger model (Haiku → Sonnet)

A natural objection: a stronger model brute-forces the large enumeration with
text and closes the gap. It does not. Sonnet, both ~100-site tasks, n=5:

| task | sites | T recall (sd) | G recall (sd) | Δ |
|---|---|---|---|---|
| serialize | 108 | 0.865 (±0.115) | **0.996 (±0.005)** | +0.13 |
| deserialize | 104 | 0.762 (±0.057) | **0.935 (±0.036)** | +0.17 |

Going Haiku→Sonnet, text *did* improve (serialize 0.62→0.87) — but graph improved
more (0.85→0.996) and stayed ahead, on **both** large tasks.

**At the frontier (Opus) the advantage is conditioned on task difficulty.** Full
three-tier recall (Δ = G−T):

| tier | serialize (108) | deserialize (104, *harder*) |
|---|---|---|
| Haiku | .62 → .85 (**+.24**) | .52 → .69 (**+.17**) |
| Sonnet | .87 → 1.00 (**+.13**) | .76 → .94 (**+.17**) |
| Opus | 1.00 → 1.00 (**+.00**) | .92 → **.96** (**+.04**) |

On `serialize` Opus's text arm fully enumerates the change (1.00 ± 0, 24 turns) and
the graph is redundant. But on the *harder* `deserialize`, even Opus text drops
sites (mean 0.923, with one run at **0.71**), while the graph holds 0.962 — higher
recall, lower variance (sd .05 vs .12), **and cheaper** ($4.69 vs $5.64/run, it
traverses rather than grinding). So the recall advantage shrinks monotonically with
capability but **does not vanish on hard tasks** — it converts into a reliability +
cost edge. The graph is best read as a **capability equalizer**: it lifts weak
models to near-frontier completeness on large changes, and at the frontier still
pays off on the changes hard enough that even a frontier model's text search is
unreliable.

### 4.4 The graph removes catastrophic misses (a consistency gain)

The Sonnet table shows more than a higher mean: the **variance** differs. Text
swings from 1.00 to 0.73 across nominally identical runs — it silently misses
~30% of sites on some trials. Graph is 0.996 ± ~0: **zero catastrophic runs.** On
a change task, where one missed site is a broken build, this reliability is
arguably more valuable than the mean lift. This is the completeness/calibration
benefit the single-tier Go study looked for and could not find; it emerges only
once tasks are large enough that text *can* fail. **It persists to the frontier
on hard tasks:** Opus text on `deserialize` still dropped to 0.71 on one run
(sd .12), while the graph stayed at 0.96 (sd .05) — the graph removes the tail
risk even when the mean is close.

### 4.5 Cost: better answer at the same price

Cost (USD/run) depends on the regime (Sonnet G/T ratios):
- **Large tasks (104/108): G/T ≈ 1.07–1.16** — the graph buys +0.13–0.17 recall
  for ~10% more. The Go framing ("same answer, fewer tokens") becomes **"better
  answer, ~same price"**: text cannot reach the graph's recall at *any* reasonable
  budget here — Sonnet text spent 50–65 turns and still missed sites.
- **Mid-size tasks (38/58): G/T ≈ 0.63–0.77** — recall ties but the graph is
  ~25–37% **cheaper**, recovering the Go token-efficiency result at matched
  quality (a single authoritative traversal vs many grep+read turns).
- **Small tasks (8/22): G/T ≈ 1.24–1.28** — prism's per-call overhead makes the
  graph pricier where text was already near-complete.
- **At the frontier (Opus), the graph becomes a cost lever.** Recall ties on all
  six tasks (Δ ≤ 0.04 — Opus text enumerates everything), but the graph is
  *cheaper* on 4 of 6, including every mid/large task: G/T ≈ **0.64** (38),
  **0.71** (58), **0.83** (104, *at higher recall*), 1.03 (108), 0.90 (8); only
  the tiny `settable-set` is pricier (1.24). The graph's authoritative traversal
  undercuts a frontier model grinding 24–39 text turns. So at the frontier the
  graph stops being a quality lever and recovers the Go "same answer, fewer
  tokens" result.

So the graph is *cheaper* in the middle, *better at ~par cost* at the top, and a
*small overhead tax* at the bottom. Wall-clock latency is comparable on large
tasks (both run long); prism overhead makes the graph slower on small ones.

### 4.6 Calibration

In aggregate over small tasks, over-confidence is tied (both arms assert
`complete` at ~0.9 recall on `settable-set`: 5/5 each) — the Go negative holds
there. The graph's calibration benefit is specifically the **variance collapse on
large tasks** (4.4), not a uniform over-confidence reduction.

---

## 5. Why — the mechanism

A change to a method's signature forces every declaration/override **and** every
call site to change. Two regimes:

- **Few sites, statically named (Go, small Java).** A call `x.Foo(...)` and an
  implementor `func (T) Foo(...)` both contain `Foo`; with ≤~20 sites a capable
  agent greps the name, reads to confirm, and enumerates them all. The graph's
  structural precision saves reading effort (a token wash) but rarely changes
  *what it finds*. Hence the tie.
- **Many sites (Java framework interfaces, ~100).** Now grep+read is a manual
  graph traversal at scale: the agent must find every implementor and every
  polymorphic call, hold them in context, and not lose any across 50–65 turns.
  It is good on average but **unreliable** — it drops sites stochastically. The
  resolved graph enumerates the family and the resolved callers in one
  authoritative pass, so completeness is both higher and consistent.

This predicts the boundary: the graph earns its keep wherever the change-set is
too large to enumerate reliably by hand — large refactors, framework-wide
interface changes — and ties text on the small, local edits that dominate
everyday work. Name ambiguity is a red herring at these sizes: a capable agent
disambiguates `get`/`set` by reading, as long as there are few sites to check.

---

## 6. Discussion — implications

- **Evaluate code-context tools conditioned on blast radius.** "Graphs help" and
  "graphs don't" are both wrong; the honest figure of merit is
  completeness-and-consistency at fixed cost, as a function of #change-sites.
- **The graph's value morphs with model capability.** On large changes it is a
  *quality/reliability* lever for weak and mid models (big recall lift, variance
  collapse) and a *cost* lever at the frontier (recall ties, but it traverses
  more cheaply than a frontier model grinding dozens of text turns). One tool,
  two payoffs, selected by how capable the model already is.
- **Language matters only through task size.** Java surfaced the effect not
  because Java is "harder to grep" but because framework interface methods
  produce 100-site change-sets that Go application code in our sample rarely did.
  The prediction is testable in large Go codebases with wide interfaces.
- **Tool *altitude* gates who can realize the benefit.** The win is largest for
  weak/cheap models on large changes — but a weak model can only realize it if it
  can *operate* the graph. In a probe with a local open-weights model
  (qwen3-coder-30b), the graph exposed as *primitives* (a CLI, or MCP-style typed
  tools the model must orchestrate over many turns) yielded recall 0.0 — the model
  greps competently but cannot chain a multi-turn traversal or reliably emit the
  tool calls. Exposed instead as a single *high-altitude* operation —
  `change_impact(method) → declaration + override/impl family + resolved callers`,
  with an impact-routing scaffold that guarantees the call — the same model relayed
  a complete change-set in one call across all six tasks. (This probe demonstrates
  the *interaction*, not a graph-vs-text score: our prototype `change_impact` is
  built on the type-resolution engine that also produces our ground truth, so its
  recall is tautological; a scored claim requires this resolution to live inside
  the graph tool and be judged by an independent oracle. See the artifact repo.)
  The design implication is concrete: to deliver the graph's completeness win to
  the models where it matters most, ship *change-impact* as a first-class agent
  operation, not a kit of primitives.

---

## 7. Threats to validity

- **Data status: complete.** Haiku (4 tasks), Sonnet (6 tasks), and Opus (6 tasks)
  full grids, n=5/cell, 157 scored runs. The three-tier × size-curve result is
  final; numbers are deterministic via the oracle scorers (no LLM in the loop).
- **Two subjects per language, one framework for the large-Java regime.** The
  large-task win rests on jackson-databind interface methods; replication on
  another framework (Spring, Guava) and in a large Go codebase with wide
  interfaces is the key external-validity gap.
- **Mode A only.** We score the *answer*, not an applied patch. Mode B (compile /
  fail-to-pass) — where an incomplete change actually breaks the build — would
  test whether the graph's reliability gain converts to task success.
- **One graph implementation (Grove/Prism)** and a soft tool gate (the G arm can
  decline to use the graph; we exclude those runs but the offer-vs-enforce
  distinction is unmodeled).
- **Construct / selection.** Java GT is type-resolved (no bare-name pollution);
  an earlier bare-name Java attempt (commons-lang) was discarded after audit. Go
  GT pollution and codegen churn were mitigated after discovery; earlier positive
  readings on hand-picked tasks did not survive outcome-blind sampling.

---

## 8. Conclusion

The intuition that a resolved code graph makes an agent more complete on
change-impact tasks is **conditionally true, and the condition is capability ×
blast radius.** On small, name-greppable changes (most of Go, everyday edits) the
graph ties text at every model tier. On large-blast-radius changes it acts as a
**capability equalizer**: it lifts weaker/cheaper models toward frontier-level
completeness (Haiku +0.17/+0.24, Sonnet +0.13/+0.17) with far lower variance. That
recall gain shrinks as the model strengthens and, at the frontier, **vanishes on
tasks the model can fully enumerate by text yet persists on harder ones** — where
the graph still delivers higher recall, removes the tail risk (Opus text dipped to
0.71 on `deserialize`; the graph did not), and even costs less. The earlier
blanket negative was an artifact of a small-task sample; the blanket positive
("graphs obviously help") is equally wrong. The defensible, mechanistic claim:
**a code graph is a completeness-and-reliability tool that pays off in proportion
to how far a change exceeds what the model's text search can reliably enumerate —
large for weak models, narrowing to hard-task reliability at the frontier, and a
wash for small local edits.**

---

## Artifacts

Harness, tasks, oracle integrations, raw logs: `harness/`. Java oracle + task
generator + reproduction steps: `harness/java-oracle/README.md`. Analyses
reproducible without an LLM via `rescore.py` / `rescore_java.py` + `agg_jackson.py`
over `runs/` (deterministic scoring + recall/cost aggregation). `THESIS.md` holds
the falsifiable sub-claims and their verdicts.
