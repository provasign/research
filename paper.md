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
- **On large-blast-radius tasks (≈100 change-sites), the graph wins decisively**
  on completeness *and* consistency. On jackson-databind's `serialize`/
  `deserialize` interface methods (104–108 sites), the graph lifts mean recall
  by **+0.13 to +0.24** over text and **collapses its variance** — e.g. Sonnet
  text 0.87 (swinging to 0.73) vs graph **0.996 ± ~0**. The gain is **robust
  across model tiers** (Haiku and Sonnet): a stronger model improves text but the
  graph improves more and stays ahead.
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

### 4.2 Large-blast-radius change-impact: the graph wins (Java)

On jackson's ~100-site interface methods the picture inverts. Haiku, n=4–5,
post-normalization:

| task | sites | grep× | T recall | G recall | Δ | G/T cost |
|---|---|---|---|---|---|---|
| jsonnode-get | 8 | 63.6 | 0.97 | 0.97 | +0.00 | 1.07 |
| settable-set | 22 | 18.5 | 0.90 | 0.91 | +0.01 | 1.01 |
| deserialize | 104 | 4.1 | 0.52 | **0.69** | **+0.17** | 1.04 |
| serialize | 108 | 3.1 | 0.62 | **0.85** | **+0.24** | 1.04 |

The advantage appears only at scale, and grows with #sites — **not** with grep
ambiguity (which runs the other way).

### 4.3 The gain survives a stronger model (Haiku → Sonnet)

A natural objection: a stronger model brute-forces the large enumeration with
text and closes the gap. It does not. Sonnet, `serialize` (108 sites), n=5:

| arm | mean recall | per-trial | cost (USD/run) |
|---|---|---|---|
| text | 0.865 | 0.73, 0.89, 0.97, 1.00, **0.73** | $2.17 |
| **graph** | **0.996** | 1.00, 1.00, 0.99, 1.00, 0.99 | $2.32 |

Going Haiku→Sonnet, text *did* improve (0.62→0.87) — but graph improved more
(0.85→0.996) and stayed ahead. `deserialize` (partial) agrees: T 0.76 vs G 0.89.
(Opus frontier point in progress.)

### 4.4 The graph removes catastrophic misses (a consistency gain)

The Sonnet table shows more than a higher mean: the **variance** differs. Text
swings from 1.00 to 0.73 across nominally identical runs — it silently misses
~30% of sites on some trials. Graph is 0.996 ± ~0: **zero catastrophic runs.** On
a change task, where one missed site is a broken build, this reliability is
arguably more valuable than the mean lift. This is the completeness/calibration
benefit the single-tier Go study looked for and could not find; it emerges only
once tasks are large enough that text *can* fail.

### 4.5 Cost: better answer at the same price

Across every cell the graph's token and USD cost is within ~7% of text
(G/T ≈ 1.0–1.07). The Go framing ("same answer, fewer tokens") becomes, in Java
at scale, **"better answer, same price"**: text cannot reach the graph's recall
at any reasonable budget on a 100-site task — Sonnet text spent 50–65 turns and
still missed sites the graph found. An honest cost caveat remains: wall-clock
latency is comparable here (both arms run long on large tasks), but prism's
per-call overhead makes the graph slower on *small* tasks.

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
- **The graph is a reliability tool for large changes.** Its distinctive value is
  removing catastrophic completeness misses on big refactors — not a marginal
  mean lift, and not a token saving.
- **Language matters only through task size.** Java surfaced the effect not
  because Java is "harder to grep" but because framework interface methods
  produce 100-site change-sets that Go application code in our sample rarely did.
  The prediction is testable in large Go codebases with wide interfaces.

---

## 7. Threats to validity

- **Data in progress.** The Haiku Java curve (4 tasks) and Sonnet `serialize` are
  complete; Sonnet `deserialize` is partial, the two mid-size Java tasks (38/58)
  and the Opus tier are still running. The size-curve *shape* (tie→win across
  8/22/104/108) is solid; the mid-size points and the frontier tier will firm up
  the curve and are reported as they land.
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
change-impact tasks is **conditionally true**: it ties text on the small,
name-greppable changes that dominate Go and everyday edits, and it **wins
decisively on large-blast-radius changes** — higher recall, far lower variance,
at near-equal cost — robustly across model tiers, as shown on a polymorphism-heavy
Java framework. The discriminator is the size of the change-set, not name
ambiguity or language. The earlier blanket negative was an artifact of a
small-task sample; the earlier blanket positive ("graphs obviously help") is also
wrong. The defensible claim is bounded and mechanistic: **a code graph is a
completeness-and-reliability tool for large changes, and a wash for small ones.**

---

## Artifacts

Harness, tasks, oracle integrations, raw logs: `harness/`. Java oracle + task
generator + reproduction steps: `harness/java-oracle/README.md`. Analyses
reproducible without an LLM via `rescore.py` / `rescore_java.py` + `agg_jackson.py`
over `runs/` (deterministic scoring + recall/cost aggregation). `THESIS.md` holds
the falsifiable sub-claims and their verdicts.
