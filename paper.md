# Code Graphs Don't Beat Text Search for Agentic Coding — A Controlled Negative Result

**Status:** working draft (honest-negative reframe, 2026-06-23). Thesis and the
rigorous isolation in `THESIS.md`; raw per-run data in `harness/runs/` (scored
deterministically by `rescore.py` against an independent oracle).

> Honesty note. This paper reports a **negative result** with one modest positive.
> It is grounded in 14 tasks, 1 language (Go), 3 Claude models. The sample is
> small and single-language — see §7. We deliberately do not overclaim; several
> intermediate hypotheses we *did* hold at various points (graph improves
> completeness; graph improves calibration; graph equalizes model capability) did
> not survive isolation, and we report exactly how each fell.

---

## Abstract

A widespread intuition holds that giving an LLM coding agent a resolved code
graph (callers, callees, implementors, dispatch) should make it more effective on
existing code than plain text search (grep/ripgrep + read), because the graph has
strictly more accurate structural information. In a controlled, paired study that
isolates the context mechanism and scores against an independent compiler-grade
oracle, we find this intuition **does not hold for change-impact tasks in Go**:

- **Completeness (recall) is statistically tied** between graph and text across 14
  tasks — a capable agent reaches the same change-site recall by grep+read,
  because most Go call sites are *name-greppable*.
- **Calibration is tied in aggregate** — the graph does not reliably make the
  agent "know when it's incomplete"; it helps on some tasks and hurts on others.
- **The cheap-model-reaches-frontier-quality story is a confound** — a cheap model
  with the graph does match a frontier model with text at lower cost, but
  *isolating the graph* (same model, text vs graph) shows the graph lifts recall
  on 1 of 10 tasks; the saving is model price, not the graph.
- The graph's one **measurable, graph-attributable benefit is token efficiency at
  scale**: it reaches the *same* answer at ~10–40% lower cost, a saving that grows
  with the change's blast radius and is *negative* on trivial changes.

We give the mechanism (greppability of statically-named call sites), the one
boundary where the graph did help (a rename, where the symbol name itself becomes
an unreliable search key), and argue the field should evaluate code-context tools
on **cost-at-fixed-quality**, not on an assumed completeness advantage that, at
least for Go, isn't there.

---

## 1. Introduction

LLM coding agents work on existing code through a loop: **locate** relevant code
(search), **read** it to understand, **traverse** structure (who calls / what
implements), and **stop** when subjectively confident. Two paradigms supply the
context: text search, and a resolved code graph. The graph demonstrably holds more
accurate structural information, so the natural hypothesis — and the one we set out
to confirm — is that it produces more complete, better-calibrated agent behavior
on change tasks, where a missed call site is a broken build.

We could not confirm it. This paper is the controlled story of *why*, and of the
one place the graph still pays. Contributions:

1. **A methodology that isolates the tool** — identical tasks, three arms (text /
   graph / graph-as-verifier), enforced tool allowlists, scored against an
   **independent** `go-ssa-vta` oracle (never the graph under test).
2. **The negative result**, across a 12-variable framework: graph ≈ text on
   completeness and calibration for Go change-impact tasks.
3. **A careful isolation** that dissolves two seductive false positives (the
   cost-quality "capability equalizer," and a calibration headline that held only
   on a hand-picked subset).
4. **The surviving positive** — a modest, scale-dependent token saving — and a
   mechanistic account (greppability) that predicts *when* the graph could still
   matter (when greppability breaks: renames, reflection, cross-language dispatch).

---

## 2. A variable framework for agent code-context

Three cost axes — **tokens, latency, round-trips, setup**; six quality axes —
**completeness, precision, calibration, freshness, breadth, determinism**; one
outcome — **task success**; one meta-variable — **cost-of-error**. The field
optimizes the cost axes (tokens/latency). Our prior belief was that the graph's
value lived in the quality axes (completeness/calibration). The result below is
that, for Go, it does *not* — and the only place it shows up is the cost axis we
had dismissed.

---

## 3. Study design

**Arms** (only the tool description/allowlist differs): **T** text (rg/grep/read),
**G** graph (typed `prism query --include graph` neighborhood + text for
discovery), **V** text-primary with graph-as-verifier. Arm enforcement is
mechanical (`--allowedTools`, recorded `tool_trace`).

**Mode A (context quality):** the agent answers "list every site that must change
to do X," declaring `complete` + `unresolved`. Isolates the tool from patch-writing
skill. (Mode B / compile-and-test is future work, §7.)

**Independent oracle:** ground truth is the `go-ssa-vta` call graph (via
`grove-eval`) and/or the merged-PR diff (codegen/mocks filtered) — **never** the
graph under test. Test-path sites scored neutral.

**Subjects:** 14 Go tasks (Grafana + gin), spanning 1–93 change-sites: localization
controls, greppable enumeration controls, and change-impact tasks (rename,
dispatch, interface-declaration). **Models:** Haiku, Sonnet, Opus. **Trials:** 5
per cell; we report tails (min, worst-case rate), not just medians.

---

## 4. Results — the negative

### 4.1 Completeness is tied

Across all 14 tasks, mean recall(G) ≈ recall(T) (within ~0.01–0.07 every task;
no consistent direction). On the largest task (93 sites, 27 packages), Haiku-text
0.817 vs Haiku-graph 0.826 — **volume does not break text**: the agent greps the
(statically named) symbol and enumerates the call sites. Greppable controls
(uniformly-named handlers) reach recall ≈1.0 for *every* arm.

### 4.2 Calibration is tied in aggregate

Over-confidence (claims `complete` while recall<1) summed across all runs: **T ≈
43, G ≈ 42.** The graph lowers over-confidence on the three original dispatch
tasks (the basis of an earlier, withdrawn "16%→2%" headline) but *raises* it on
others (`pr112043`, `querydata`). It is task-dependent, not a property of the graph.

### 4.3 The "capability equalizer" is a confound

A cheap model + graph (Haiku-G) matches a frontier model + text (Opus-T) on quality
at **39–78% lower cost** on most tasks — superficially a strong result. But
isolating the graph (Haiku-**T** vs Haiku-**G**, same model) the graph lifts recall
on **1 of 10 tasks** (126004, +0.29) and ~0 elsewhere. The cheap model was already
≈ as good as the frontier model on these tasks; **the saving is model price, not
the graph.** We flag this because it is exactly the comparison a less careful study
would have reported as the headline.

### 4.4 Weak-model tail risk: weak signal

Catastrophic runs (recall<0.7) for Haiku: **text 9/45 → graph 6/45.** A real but
small reduction, concentrated in one task; the graph still leaves bad runs where
they occur (`pr112043`). Not enough to claim the graph makes weak models reliable.

### 4.5 The one survivor: token efficiency at scale

For matched recall, cost(G) < cost(T) on non-trivial tasks: **+11% to +37%** on
tasks ≥7 sites, largest on the biggest tasks (93-site: 37% cheaper), and *negative*
on 1–2-site tasks (prism overhead exceeds the grep+read it replaces). The graph
buys the *same answer for fewer tokens*, and the saving scales with blast radius.
Caveat: wall-clock latency is *higher* (prism call overhead; warm MCP would narrow
it) — an honest cost has both.

---

## 5. Why — the mechanism

Go call sites are **statically named and name-greppable**: a call `x.Foo(...)` and
an implementor `func (T) Foo(...)` both contain `Foo`. A capable agent greps the
name and reads to confirm, reaching the same recall the graph would. The graph's
structural precision (resolving *which* `Foo`) saves the agent reading effort —
hence the token win — but rarely changes *what it can find*. The graph's recall
advantage is therefore confined to cases where **greppability breaks**: the symbol
name is changing (renames — our one positive, 126004), the call is via
reflection/callback/embedding, or the language hides dispatch (Java, dynamic
languages). For Go, that's a minority of sites, which is exactly what the null shows.

---

## 6. Discussion — implications

- **Evaluate code-context tools on cost-at-fixed-quality, not assumed completeness.**
  For agentic Go coding the completeness premise is false; the honest figure of
  merit is tokens (and latency) for the same correct answer.
- **The graph is an optimization, not a capability.** Worth it on large changes
  where it amortizes its overhead; counterproductive on small ones.
- **The boundary is greppability.** The graph should be re-evaluated precisely
  where text search is structurally blind — other languages and name-breaking
  changes — which Go change-impact tasks largely are not.

---

## 7. Threats to validity

- **Single language, and the *easy* one for the null.** Go is highly greppable;
  this is the regime where the graph's edge is *smallest*. The negative falsifies
  "graphs universally help," but **does not** establish the null for Java /
  reflection-heavy / dynamic languages, where greppability is worse — explicitly
  untested and the most important external-validity gap.
- **Small N (14 tasks), Mode A only.** Task-level statistics are descriptive, not
  powered; Mode B (compile / fail-to-pass) — where incompleteness has teeth — is
  not yet run and could change the calibration story.
- **One tool implementation (Grove/Prism).** A different graph tool or a different
  delivery (an *enforced* gate rather than an offered tool) might differ; our
  soft-gate probe was inconclusive.
- **Construct / selection.** We mitigated GT pollution (cross-interface name
  collisions) and codegen churn after finding both; earlier positive readings came
  from hand-picked tasks and did not survive outcome-blind sampling.

---

## 8. Conclusion

The intuition that a resolved code graph makes an LLM coding agent more complete or
better-calibrated on change-impact tasks is, for Go, **not supported**: text search
reaches the same recall because the code is name-greppable, and the graph's only
measurable, graph-attributable benefit is a modest token saving that scales with
task size. The cheap-model-equalizer and calibration stories dissolve under
isolation. The honest figure of merit is cost-at-fixed-quality, and the open
question worth pursuing is the *boundary* — whether the graph earns its keep where
greppability breaks (other languages, name-changing edits), which this study marks
but does not settle.

---

## Artifacts

Harness, tasks, oracle integration, raw logs: `harness/`. Analyses reproducible
without an LLM via `rescore.py` over `runs/` (deterministic scoring). `THESIS.md`
holds the falsifiable sub-claims and their verdicts.
