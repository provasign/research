# When Does a Code Graph Help a Coding Agent? Blast Radius, Model Capability, and Tool Altitude

**Status:** full draft (tool-altitude extension, 2026-07-04). Canonical version:
`paper/paper.tex` (builds with tectonic). Thesis and falsifiable sub-claims in
`THESIS.md`; raw per-run data in `harness/runs/`, scored deterministically by
`rescore.py` / `rescore_java.py` against independent oracles (Go: `go-ssa-vta`;
Java: a Spoon type-resolution oracle, `harness/java-oracle/`). Engine-only
scores: `harness/score_grove_change_impact.py`; engine findings:
`harness/GROVE-CHANGE-IMPACT.md`.

> Honesty note. An earlier version reported a *negative* result ("code graphs
> don't beat text search") drawn from Go tasks that were almost all small and
> name-greppable. Extending to jackson-databind with a type-resolution oracle
> and a size-graded task set surfaced the first boundary (blast radius); a
> second extension surfaced an independent second condition (tool altitude).
> The honest result is **conditional twice over**: the graph's value is real but
> bounded to large-blast-radius change-impact, and *who can realize it* is
> gated by whether the tool demands orchestration the model cannot supply.

---

## Abstract

In a controlled, paired study across two languages (Go, Java), three model
tiers, and change-impact tasks spanning 1–108 change-sites, scored against
independent compiler-grade oracles, the intuition "a code graph makes agents
better on existing code" is **true but doubly conditional** — on task size, and
on the *altitude* at which the graph is exposed:

1. **Small / name-greppable changes: graph ≈ text** at every tier.
2. **Large-blast-radius changes (~100 sites), graph as *primitives*** (lookup /
   references / edges the agent orchestrates): a **partial capability
   equalizer** — +0.17–0.24 recall for weak models, variance collapse — but
   orchestrating a multi-turn traversal is itself a frontier skill, so the
   small tier plateaus at mean recall **0.833** with the same tools the
   frontier drives to **1.000**.
3. **Same graph at *task altitude*** — one deterministic
   `change_impact(method)` op computing declaration + override family +
   resolved callers inside the engine — **removes the barrier entirely**:
   every tier reaches mean recall **0.997**, tier-invariant per-task. The
   smallest model (+op, $0.11/task) **outperforms the frontier model on text**
   ($2.14/task) and matches the frontier on primitives ($3.06/task) at **1/28th
   the cost** and 5–15× fewer turns. The engine op alone scores **0.993 recall
   / 0.948 precision** against the oracle with **no LLM in the loop**.

Building the deterministic op also surfaced **five latent resolution defects**
every LLM-orchestrated arm had silently absorbed — task-shaped operations are
not only more effective, they are *testable*. Implication: ship change-impact
(and its siblings) as first-class operations, not primitive kits, and evaluate
context tools on completeness-at-fixed-cost conditioned on blast radius **and**
interface altitude.

---

## 1. Introduction

Agents work existing code through locate → read → traverse → stop. The graph
holds strictly more structural information than text search, so it "should"
help on change-impact, where a missed call site is a broken build.

The Go study could not confirm this (tasks too small/greppable — honest
negative). The Java extension (jackson-databind, size-graded 8→108 sites,
Spoon oracle) found the first boundary: **blast radius**. But it contained a
puzzle: the graph's advantage was largest where the model was weakest, *yet the
weak model left most of it on the table* (G mean 0.833 vs frontier 1.000, same
tools). The graph had the answer; the small model couldn't extract it. Moving
the extraction into the engine (`change_impact` as one deterministic op) found
the second boundary: **tool altitude**. At task altitude completeness is
tier-invariant and the cheapest model becomes the best-value system.

**Contributions.** (1) Tool-isolating methodology, two languages, enforced
allowlists, independent oracles. (2) The size-conditioned result; discriminator
= blast radius (caller-edge-only sites), not name ambiguity, not language.
(3) Capability-conditioned reading of the primitives arm. (4) **Tool altitude:**
task-level op ⇒ tier-invariant completeness; weak model beats frontier-text at
1/20th cost. (5) **Testability:** the deterministic op exposed 5 engine defects
the LLM arms masked. (6) Artifacts: Spoon oracle + task generator,
line→method scoring fix, the graph-native op itself.

---

## 2. Variable framework

Cost axes: tokens, latency, round-trips, setup. Quality: completeness,
precision, calibration, consistency, freshness, determinism. Outcome: task
success. Meta: cost-of-error. **New load-bearing design axis: interface
altitude** — primitives the agent orchestrates vs a task-shaped operation
returning the completed traversal. The graph's value lives in completeness +
consistency past a size threshold; *who collects it* depends on altitude.

---

## 3. Study design

**Arms** (only tool description/allowlist differs): **T** text (rg/grep/read);
**G** graph primitives (`prism` lookup/references/edges + rg for anchors);
**V** text + graph-as-verifier; **G\*** task-level graph
(`prism change-impact 'Type.method(Params)'` returns declaration + subtype-
closure family + resolved callers in one response). Enforcement via
`--allowedTools` + recorded `tool_trace`; violations (G never touching the
graph, G\* never calling change-impact) are excluded.

**Mode A** (context quality): "list every site that must change," declaring
`complete` + `unresolved`. Mode B (compile/fail-to-pass) is future work.

**Independent oracles — never the graph under test.** Go: `go-ssa-vta`. Java:
Spoon type-resolution oracle (declaration + override/implementation family +
call sites that *resolve by type* into the family; ~500 name-matched `get`/`set`
sites reduced to the 3–22 truly-jackson ones, 0 unresolved). Oracle and engine
are separate implementations (compiler frontend vs tree-sitter indexer);
agreement is the measurement, disagreement was the debugging signal (§5.4).

**Scoring pitfall (Java):** graph arms answer `File.java:114`; a name scorer
scores that 0 — silently penalizing the graph arm. We normalize line numbers to
enclosing methods via a Spoon line→method index (`rescore_java.py`). All Java
numbers are post-normalization.

**Subjects.** Go: 14 tasks (1–93 sites). Java: jackson-databind @ 2.18.8,
6 signature-change tasks at **8/22/38/58/104/108** sites. **Tiers:** Haiku /
Sonnet / Opus.

**Two experiments.** Exp 1: T/G/V, n=5/cell, 157 scored runs → blast-radius +
capability results. Exp 2 (altitude): G\* at all tiers + fresh T/G baselines on
the **repaired engine** (~50 runs; small-tier G\* replicated n=3; the op is
deterministic so G\* variance is confined to query formulation).

**Engine repair between experiments (a result in itself, §5.4):** scoring the
op's raw output against the oracle exposed 5 latent Java resolution defects
(recall 0.05→0.99 from engine fixes alone), all fixed with regression tests
before Exp 2. This makes Exp 2's G baseline *stronger*, biasing against the
altitude effect we report. T is engine-independent.

---

## 4. Results I — blast radius and capability (graph as primitives)

### 4.1 Small/greppable: graph ≈ text
Go: recall(G) ≈ recall(T) everywhere. Small Java ties despite 18–64× grep
over-match. Ambiguity did not help the graph.

### 4.2 The size curve (Exp 1, n=5)

| task | sites | Haiku T | Haiku G | Sonnet T | Sonnet G | Opus T → G |
|---|---|---|---|---|---|---|
| jsonnode-get | 8 | 0.97 | 0.97 | 0.78 | **0.93** | 0.93 → 0.95 |
| settable-set | 22 | 0.90 | 0.91 | 0.93 | 0.97 | 0.97 → 0.99 |
| writeTypePrefix | 38 | — | — | 0.97 | 1.00 | 1.00 → 1.00 |
| serializeWithType | 58 | — | — | 0.99 | 1.00 | 0.99 → 1.00 |
| deserialize | 104 | 0.52 | **0.69** | 0.76 | **0.93** | 0.92 → **0.96** |
| serialize | 108 | 0.62 | **0.85** | 0.86 | **1.00** | 1.00 → 1.00 |

Large tasks: +0.13–0.24 both non-frontier tiers. Mid-size ties. The exception
(`jsonnode-get`, Sonnet T 0.78) is the mechanism in miniature: the missed sites
(`has`, `hasNonNull`, `_at`) *call* `get` but aren't *named* get — reachable
only via caller edges. The predictor is **caller-edge-only sites**, which grows
with blast radius.

### 4.3 Across tiers
Δ(G−T) on serialize/deserialize: Haiku +0.24/+0.17 → Sonnet +0.13/+0.17 →
Opus +0.00/+0.04. Shrinks with capability; at the frontier converts to
reliability + cost (Opus T dipped to 0.71 on deserialize; G held 0.96, cheaper).
**Note the equalization is partial: Haiku G (0.69/0.85) ≪ Opus G (0.96/1.00),
same tools.**

### 4.4 Consistency
Sonnet T serialize swings 1.00→0.73 across identical runs; G is 0.996 ± ~0.
Zero catastrophic runs. Persists at the frontier on hard tasks.

### 4.5 Cost regimes
Large: G/T ≈ 1.07–1.16 (better answer, ~same price). Mid: G/T ≈ 0.63–0.77
(same answer, 25–37% cheaper). Small: G/T ≈ 1.24–1.28 (overhead tax). Frontier:
graph = cost lever (cheaper on 4/6).

### 4.6 Calibration
Tied on small tasks; the graph's calibration value is the large-task variance
collapse, not uniform over-confidence reduction.

---

## 5. Results II — tool altitude (graph as a task-level operation)

Exp 1's gap: the graph *knows* the answer; a weak model can't *extract* it
through primitives. G\* moves extraction into the engine; the agent identifies
the target, runs one command, relays the result.

### 5.1 Completeness becomes tier-invariant (Exp 2, repaired engine)

| task | sites | Haiku T/G/**G\*** | Sonnet T/G/**G\*** | Opus T/G/**G\*** |
|---|---|---|---|---|
| jsonnode-get | 8 | 1.00 / 1.00 / **1.00** | 1.00 / 1.00 / **1.00** | 1.00 / 1.00 / **1.00** |
| settable-set | 22 | 0.91 / 1.00 / **1.00** | 0.95 / 0.95 / **1.00** | 1.00 / 1.00 / **1.00** |
| writeTypePrefix | 38 | 0.84 / 1.00 / **1.00** | 1.00 / 1.00 / **1.00** | 1.00 / 1.00 / **1.00** |
| serializeWithType | 58 | 0.60 / 0.60 / **1.00** | 1.00 / 1.00 / **1.00** | 1.00 / 1.00 / **1.00** |
| deserialize | 104 | 0.43 / 0.67 / **1.00** | 0.75 / 0.93 / **1.00** | 0.71 / 1.00 / **1.00** |
| serialize | 108 | 0.76 / 0.72 / **0.98** | 1.00 / 0.98 / **0.98** | 1.00 / 1.00 / **0.98** |
| **mean** | | 0.76 / 0.83 / **0.997** | 0.95 / 0.98 / **0.997** | 0.95 / 1.00 / **0.997** |

Three observations. **(a) The G\* column is identical at every tier**, including
the one shared miss (serialize 0.982 — two chained-receiver call sites the
engine can't yet resolve: an *engine residual*, visible and fixable in one
place, not a stochastic model failure). **(b) The small tier gains most**:
0.758 → 0.833 → **0.997**. **(c) The frontier gains effort**: 4 turns instead
of 21, 70s instead of 429s. The Haiku transcript on the 8-site task is a single
tool call — `prism change-impact 'JsonNode.get(int)' .` — 2 turns, 22.6s,
$0.04, recall 1.0. The n=3 small-tier replication (18 runs) scored identically
in every trial; site sets were byte-identical in 4/6 tasks, and in the other
two a single trial transcribed one method's directory differently while naming
the same method — relay noise, scored identically.

### 5.2 The economics invert

| tier | arm | mean recall | $/task | agent turns |
|---|---|---|---|---|
| Haiku | T | 0.758 | 0.48 | 31 |
| Haiku | G | 0.833 | 0.53 | 41 |
| Haiku | **G\*** | **0.997** | **0.11** | **2.8** |
| Sonnet | T | 0.951 | 2.13 | 45 |
| Sonnet | G | 0.978 | 2.20 | 44 |
| Sonnet | **G\*** | **0.997** | **0.53** | **11.7** |
| Opus | T | 0.952 | 2.14 | 22 |
| Opus | G | 1.000 | 3.06 | 21 |
| Opus | **G\*** | 0.997 | **0.48** | **4.0** |

At primitive altitude completeness is bought with model capability (recall
ladder 0.833→0.978→1.000 tracks the price ladder $0.53→$2.20→$3.06). At task
altitude the ladder collapses: every tier delivers 0.997, so the rational
choice is the cheapest tier — **$3.06 → $0.11, a 28× reduction at −0.003
recall**. Against the strongest text baseline (Opus T: 0.952 mean, 0.71 dip)
Haiku+G\* is *strictly better*: higher mean, no tail risk, 1/20th cost.
Completeness becomes a property of the tool; the model reverts to what it's
needed for — identifying the target and consuming the result.

### 5.3 The engine ceiling, measured without an LLM
The op scored directly against the oracle (no model): **mean recall 0.993,
precision 0.948** (per-task recall ≥ 0.974; misses = 3 chained-receiver sites +
1 multi-line argc case). Agent-mediated G\* reproduces the ceiling (0.997).
This decomposition — tool's oracle score vs agent's realization — is only
possible because the traversal *is* a tool, and it's how structural code tools
should be evaluated. Precision: 0.80 on the overload-ambiguous 8-site task,
0.97–1.00 elsewhere.

### 5.4 What building the op revealed: LLM arms absorb engine defects
The op initially scored recall **0.05** on the 108-site task. Tracing oracle
misses exposed five engine defects: first-line-truncated signatures (killed
inheritance edges), generic bounds parsed as inheritance, wildcard imports
resolving to nothing, same-file shadowing beating typed receivers, nested
generics breaking field types. Fixed with regression tests → 0.99. **These were
invisible in Exp 1**: the G arm's LLM patched around the degraded graph with
its own reading, converting tool defects into quiet score depression ("the
graph helps somewhat") instead of a visible failure. An LLM in the loop is an
adaptive error-masker. A deterministic, oracle-scored op turns defects into
traceable, fixable failures — task-shaped tools make the structural layer
*testable*.

---

## 6. Mechanism

Three regimes:

- **Few, statically named sites:** grep+read enumerates them; graph is a wash.
- **Many sites, primitives:** grep+read *and driving the primitives* are both
  manual graph traversals at scale — choose seeds, chain
  lookup→references→overrides→callers, hold ~100 partial results over 30–60
  turns, union without loss. Each step easy; the conjunction is long-horizon
  orchestration whose success decays with length and model capability. The
  graph removes the *search* burden but leaves the *orchestration* burden.
- **Many sites, task altitude:** the traversal is one deterministic closure
  computed where the data lives. The LLM's residual surface — identify target,
  relay result — is short-horizon, low-variance, within every tier's
  competence. Completeness stops being a model property and becomes a tool
  property; tiers converge.

---

## 7. Discussion

- **Ship task-shaped operations, not primitive kits.** Identify traversals
  agents repeatedly orchestrate (change-impact, dead-code reachability,
  test-coverage closure) and expose each as one deterministic op. Primitives
  stay for ad-hoc exploration; they're the wrong *primary* interface for
  completeness-critical work.
- **The economics of completeness invert.** The marginal dollar should go to
  the engine, not the model. $0.11 Haiku+op strictly dominated $2.14 Opus+text
  here; local open-weights models become plausible carriers of frontier-grade
  change-impact (our 30B local probe succeeded via the op after failing
  entirely on primitives; full local grid = future work).
- **Evaluate conditioned on blast radius *and* altitude**, reporting the
  tool's oracle ceiling and the agent's realization separately.
- **Deterministic ops make agent systems testable** (the five-defect arc).
- **Language matters only through task size.**

---

## 8. Threats to validity

- **Exp 2 trial counts:** G\* n=3 (Haiku), n=1 (Sonnet/Opus); T/G baselines in
  §5.1 are fresh single trials on the repaired engine (Exp 1 supplies n=5
  history, consistent in direction). The op is deterministic and independently
  scored; G\* variance is confined to query formulation (no score variance in
  the replication; two single-site path transcriptions aside, site sets were
  byte-identical). Larger n is cheap and planned.
- **Query formulation is prompt-assisted:** tasks name the changing method (as
  a signature-change ticket would); localization-from-vague-report is a skill
  G\* does not address.
- **Oracle–engine independence:** separate implementations; initial 0.05 and
  residual 0.993 (≠1.0) show they don't trivially agree.
- **One framework for the large-Java regime** (replication: Spring/Guava, big
  Go); **Mode A only**; **one graph implementation**; construct/selection
  mitigations as in Exp 1 (bare-name Java GT discarded; outcome-blind Go
  sampling).
- **Determinism:** no LLM in the measurement loop; all numbers reproducible
  from run logs via the scorers.

---

## 9. Conclusion

Conditionally true, twice: **blast radius** decides *whether* the graph has
value; **tool altitude** decides *who can collect it*. Primitives partially
equalize (weak models lift but plateau — orchestration is a frontier skill).
The task-level op completes the equalization: recall 0.997 tier-invariant, the
smallest model strictly dominating frontier text at 1/20th the cost, and
completeness becoming a testable tool property. The blanket negative was a
small-task artifact; the blanket positive is equally wrong; and the
primitives-only framing under-sells the graph exactly where it matters most.
**A code graph pays off in proportion to how far a change exceeds what text
search reliably enumerates — and that payoff reaches whichever models the
tool's interface altitude permits. At task altitude, it reaches all of them.**

---

## Artifacts

Grove (engine + `change-impact` op), Prism (CLI + `prism_change_impact` MCP
tool), harness (`harness/`: arms runner, tasks, Spoon oracle, line→method
rescorer, aggregators). Engine findings: `harness/GROVE-CHANGE-IMPACT.md`.
Engine-only scorer: `harness/score_grove_change_impact.py`. All analyses
reproducible without an LLM from `runs/` via the deterministic scorers.
`THESIS.md` holds the falsifiable sub-claims and verdicts.
