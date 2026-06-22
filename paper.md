# Beyond Token Budgets: A Controlled Study of Code-Graph vs. Text-Search Context for LLM Coding Agents

**Status:** working draft (Results written from the Phase-1 pilot, 2026-06-20).
**Venue:** ACM TOSEM (primary) + arXiv cs.SE preprint. See
`grove-vs-grep-paper-design.md` for the locked study design and
`harness/PILOT.md` for the raw per-task/per-model data behind §5.

> Drafting note. The empirical sections below (§3–§5, §7) are written from the
> committed Go pilot: 7 tasks (Grafana + gin), arms T/G/V, 3 models
> (Haiku/Sonnet/Opus), 5 trials/cell, Mode A. Sections that depend on
> not-yet-collected data are explicitly marked **[PENDING]**: the Java
> (Jackson-databind) and TypeScript (NestJS) language conditions, Mode B
> end-to-end patches, the dispatch-fix ON/OFF causal ablation (H7), and the
> mixed-effects significance model. Do not present those as done.

---

## Abstract

Agentic-coding tools are largely evaluated on the variables that are cheapest to
measure — tokens consumed and latency. We argue the field is optimizing the wrong
axis. In a controlled, paired study of a resolved code graph (Grove/Prism) versus
text search (ripgrep/grep + read) as the context mechanism for an LLM coding
agent, we find the two **tie on tokens and latency** but diverge sharply on
**completeness and calibration for change-impact tasks**. Across 45 runs per arm
on three completeness-critical Go tasks spanning three Claude models, text search
is *silently incomplete* 16% of the time — it omits change-sites and asserts the
answer is complete anyway — while the graph reduces that confident-error rate
roughly **7×, to 2%**. The effect is largest for weaker/cheaper models but does
not fully vanish at the frontier. On localization / greppable tasks there is no
effect, an honest negative result.

**Scope and honesty (read this first).** This is a *pilot*, not a settled result.
The headline rests on **three tasks**, one codebase, one language (Go) — the
statistical unit is the task, so the sample is far too small for a general claim.
When we sampled *new* tasks by a fixed rule (§5.4) rather than picking for the
effect, the advantage **did not replicate**: on interface-declaration changes the
graph helped no more than text — both miss the declaring interface (§5.5), a
robust *negative*. The defensible claim is therefore narrow and conditional: a
code graph improves completeness and calibration **on tasks with dense,
ambiguously-named call sites**, and *fails to help* on at least one common
structure. We explicitly do **not** claim a code graph beats text search broadly.
Establishing whether the effect survives unbiased scaling is the central piece of
future work (§6, §8).

---

## 1. Introduction

LLM coding agents need repository context, and two paradigms have emerged for
supplying it: **text search** (the agent greps/reads its way to relevant code)
and a **resolved code graph** (a precomputed index of symbols, callers, callees,
and dispatch edges the agent can traverse). The public conversation around these
tools optimizes **token budgets** and **latency** — how little context can we
feed the model, how fast.

Our pilots show that on exactly those axes a code graph only *ties or marginally
beats* text search. If tokens and latency were the whole story, the graph would
not be worth its build and maintenance cost. We argue the field is measuring the
**cheap** variables and missing the **expensive** ones: **completeness,
precision, and calibration** on *change-* and *impact-* tasks — whether the agent
produces a *correct and complete* change, and whether it *knows what it doesn't
know*. On those tasks text search returns a **silently incomplete** answer that
the agent ships with confidence. Tokens are cents; a missed call site is a broken
build.

**Contributions.**

1. **Conceptual** — a 12-variable framework (§2) for evaluating *any* code-context
   mechanism for agents, separating three cost axes, six quality axes, an outcome,
   and a cost-of-error meta-variable that re-weights the rest.
2. **Methodological / artifact** — a controlled, paired benchmark and harness
   that *isolates the tool dimension* (only the tool description changes across
   arms) and scores against an **independent compiler-grade oracle**, never
   against the graph under test.
3. **Empirical** — graph-vs-text measured across these variables. Headline: the
   value is **correctness + calibration on completeness-critical tasks**, not
   tokens; it is modulated by model capability and task difficulty; and a
   **graph-as-verifier** configuration recovers most of the benefit.
4. **Causal [PENDING]** — a graph-precision ablation (the interface-dispatch fix,
   ON vs OFF) linking graph *quality*, not mere graph *presence*, to agent outcome.

---

## 2. A variable framework for agent code-context

A taxonomy for evaluating any code-context mechanism for agents: three cost axes,
six quality axes, one outcome, one re-weighting meta-variable.

**Cost (what you pay).** (1) **Token usage** — context budget consumed.
(2) **Latency** — wall-clock per operation / per task. (3) **Round-trips** — tool
calls / reasoning hops. (4) **Setup & maintenance** — index build, server,
freshness upkeep (text = 0).

**Quality (what you get).** (5) **Completeness / recall** — found *all* relevant
sites. (6) **Precision** — what was found is correct. (7) **Calibration / trust**
— the answer signals its own reliability and *what it could not resolve* (text
scores ≈0 here by construction). (8) **Freshness / drift-resistance** — reflects
current code, including uncommitted mid-task edits. (9) **Breadth / robustness** —
works across languages and constructs, degrades gracefully on dynamic dispatch /
reflection / codegen. (10) **Determinism** — same query → same answer.

**Outcome.** (11) **Task success** — the agent ships a *correct, working* change
(build green, fail-to-pass tests pass, pass-to-pass preserved).

**Meta.** (12) **Cost of being wrong (stakes)** — a missed caller or a false
"safe to delete" costs a broken build, a bug, a rollback — orders of magnitude
more than the tokens saved. This is *why* token optimization is the wrong
objective on change tasks, and it re-weights every variable above.

The field's tooling discourse lives almost entirely in variables 1–3. This study
moves the evaluation to 5–7 and 11, governed by 12.

---

## 3. Study design

The full design (locked decisions, hypotheses H1–H7, threats, venue) is in
`grove-vs-grep-paper-design.md`; this section summarizes what the pilot data
below was collected under.

**Arms (only the tool description differs).**
- **T (text)** — ripgrep / grep / find / read only.
- **G (graph)** — graph primitives (resolve, typed edges, scoped lookup) plus
  text for *discovery*; "search to find an anchor, traverse the graph to be
  complete."
- **V (verifier)** — text-primary, with the graph used to *check completeness*
  before finalizing.

Arm enforcement is mechanical, not prompt-only: the agent runs as the headless
`claude` CLI with `--allowedTools` + `--strict-mcp-config`, and each run records a
`tool_trace` proving which tools were reachable (T: `graph=False`, G/V:
`graph=True`). Runs that hit an API outage / timeout / zero tokens are detected,
retried, and **excluded** from scoring (never scored as recall 0).

**Mode A (context quality, primary).** The agent must *answer the context
question* — "list every site that must change to do X" — and declare
`complete: true|false` with an `unresolved` list. This isolates the tool from the
model's patch-writing skill and scales to many tasks. (**Mode B**, end-to-end
patch + test, is **[PENDING]**.)

**Ground truth — independent of the graph.** Tasks are built from merged PRs (repo
pinned at the parent commit, issue text as prompt, PR changed-sites + tests as
ground truth). Completeness is *additionally* checkable against a compiler-grade
oracle — Go's `go-ssa-vta` call graph via `grove-eval` — so the graph is never
scored against itself. Test call sites are scored **neutral** (`score.py`): a
rename legitimately changes them, a fix optionally adds them.

**Subjects in this pilot.** Go only — **Grafana** (218 MB, ~93k symbols; the
accurate-graph-at-scale condition) and **gin** (the oracle-grounded negative
control). The **Java (Jackson-databind)** and **TypeScript (NestJS)** conditions
in the design are **[PENDING]**.

**Models.** The design pins one Opus build; the pilot instead swept **three**
Claude models — Haiku, Sonnet, Opus — turning the single-model threat into a
*capability curve*, which is a strength we keep.

**Trials & reporting.** 5 trials per (task × arm × model). Because the value of
the graph is in the **tails**, we report **min recall** and **over-confidence
count** alongside medians, not means alone.

---

## 4. Tasks

| id | repo | type | sites | source / character |
|---|---|---|---|---|
| gin-4645 | gin | localization | 2 | stack-trace-localized panic |
| grafana-120266 | grafana | localization | 1 | Jaeger empty-trace panic |
| grafana-124935 | grafana | localization | 2 | alerting ORM table bug |
| grafana-126004 | grafana | impact (rename) | 7 | export `ToSnowflakeRV` + callers |
| grafana-122750 | grafana | dispatch | 16 | `Set`-family, dense sites in large files |
| grafana-120119 | grafana | interface-decl | — | cross-package; two interfaces declare the changed methods |
| gin-render-impact | gin | impact (oracle) | 13 | 12 scattered `render.Render` impls + dispatcher |

The three **completeness-critical** tasks that carry the headline are
**126004** (impact), **122750** (dispatch), and **120119** (interface-decl). The
localization tasks and `gin-render-impact` are **negative controls** — greppable
by construction.

**Why `gin-render-impact` is a control, not a thesis task.** Its 12
implementations are uniformly named (`Render`), one per file, in a dedicated
`render/` package, so `grep "func.*Render" render/` finds all 12 even for Haiku —
all arms, both models, recall 1.0. *Implementation count alone does not defeat
grep.* The discriminator is **findability** — name ambiguity plus sites buried in
large files — not interface fan-out per se. This refines the finding: the
completeness gap on 126004/122750 is driven by dense call sites in large files and
ambiguous names (`Set` × 49), not "dispatch" as a category.

---

## 5. Results

### 5.1 Headline — completeness and calibration (RQ1, RQ3)

Across the three completeness-critical tasks × three models × 5 trials =
**45 runs per arm**:

| arm | mean recall | incomplete (recall<1) | **over-confident** |
|---|---|---|---|
| **T** (text) | 0.942 | 7/45 | **7/45 (16%)** |
| **G** (graph) | 0.984 | 1/45 | **1/45 (2%)** |
| **V** (verifier) | 0.980 | 4/45 | **4/45 (9%)** |

Two findings, both decisive:

1. **Completeness.** Text search is incomplete ~16% of the time on change-impact
   tasks; the graph cuts that **~7×**, to 2%. The verifier sits in between (9%).
2. **Calibration (the real headline).** `incomplete == over-confident` for
   *every* arm — **whenever an arm missed sites, it asserted `complete: true`
   with an empty `unresolved` list.** The two columns above are identical by row.
   Text does this 7× more often than the graph. The agent does not know it missed,
   which is precisely the failure that turns a missed call site into a shipped,
   broken build.

This is the empirical core of the paper. It directly supports **H3** (calibration
is the differentiator) and the change-impact half of **H2** (completeness), while
the localization controls confirm **H1** (graph ≠ better search on greppable
tasks).

### 5.2 Capability curve (Haiku → Sonnet → Opus)

Cells: **median recall (min recall, over-confidence count)**. The value is in the
tails.

**grafana-126004 (impact, 7 sites):**

| arm | Haiku | Sonnet | Opus |
|---|---|---|---|
| T | 1.00 (min **0.29**, oc 1/3) | 1.00 (min 1.00, oc 0) | 1.00 (min 1.00, oc 0) |
| **G** | **1.00 (min 1.00, oc 0)** | 1.00 (min 1.00, oc 0) | 1.00 (min 1.00, oc 0) |
| V | 0.29 (min **0.29**, oc 2/3) | 1.00 (min 1.00, oc 0) | 1.00 (min 1.00, oc 0) |

**grafana-122750 (dispatch, 16 sites):**

| arm | Haiku | Sonnet | Opus |
|---|---|---|---|
| T | 1.00 (min 0.94, oc 1/3) | 1.00 (min 1.00, oc 0) | 1.00 (min 1.00, oc 0) |
| **G** | **1.00 (min 1.00, oc 0)** | 1.00 (min 1.00, oc 0) | 1.00 (min 1.00, oc 0) |

**Reading.** On the moderate impact/dispatch tasks the graph lifts the *weakest*
model to perfect, zero-over-confidence completeness while text and verifier let it
ship incomplete-but-confident answers (Haiku-T median 0.29 on 126004 → Haiku-G
1.00). The gap **closes as the model strengthens**: Sonnet and Opus need no help
here — the task "ages out."

But the effect does **not** fully vanish at the frontier. On the harder
**120119 (interface-decl)** task, text is incomplete + over-confident at *every*
capability level (even **Opus-T** has min recall 0.87 with over-confidence), and
the graph fixes Sonnet and Opus. Two thresholds therefore emerge:

- **Difficulty threshold** — harder tasks make the graph valuable to *stronger*
  models. gin-render (greppable) helps nobody; 126004/122750 (moderate) help only
  Haiku; 120119 (hard) helps Sonnet and Opus.
- **Capability floor** — the model must be strong enough to *use* the graph: Haiku
  cannot exploit it on 120119 (G still 0.87, over-confident 3/3).

The graph is thus a completeness/calibration aid needed only when a task exceeds
the model's read-it-yourself reach, and usable only when the model can drive the
graph.

### 5.3 Cost / quality (RQ4)

Median over 5 trials, `total_cost_usd`:

| task | Opus-T | Haiku-T | Haiku-G |
|---|---|---|---|
| 120266 | 1.00 / $0.18 | 1.00 / $0.20 | 1.00 / $0.26 |
| 124935 | 1.00 / $0.55 | 1.00 / $0.44 | 1.00 / $0.35 |
| 126004 | 1.00 / $0.36 | 1.00 / $0.17 | 1.00 / $0.16 |
| 122750 | 1.00 / $0.51 | 1.00 / $0.29 | 1.00 / $0.28 |
| 120119 | 1.00 / $0.85 | 0.87 / $0.39 | 0.87 / $0.43 |

**Haiku + graph matches Opus + text on median quality at roughly half the cost**
on the impact/dispatch tasks, *and* removes Haiku-text's catastrophic tails and
over-confidence (the 0.29 outlier on 126004). The exception is 120119, the
interface-declaration ceiling neither Haiku arm fully clears. Caveat: medians hide
variance — the calibration value of the graph is in the tails, so we report
worst-case recall and over-confidence rate, not medians alone.

*(Token accounting is currently approximated by turns / wall-clock; the stream
`result` event's `usage` reflects only the final turn. Cumulative per-turn token
totals are **[PENDING]** for the camera-ready RQ4 figure; `total_cost_usd` above
is cumulative and sound for cost-per-outcome.)*

### 5.4 Qualitative: the interface-declaration blind spot

Across the dispatch tasks the single most consistently-missed change-site is the
**interface *declaration*** — `DataKeyCache` (122750), `RouteService` and the
package-private `routeService` (120119). The transcripts show the same systematic
failure every time: the agent enumerates every *implementation* and *caller*
thoroughly (122750 Opus-V even lists the test doubles), then asserts
`"complete": true, "unresolved": []` while omitting the interface type whose
method signatures must also change.

This is a structural blind spot: agents reason in terms of functions/methods and
forget that a method's signature is *also declared on its interface*. It is
exactly the fact a graph encodes (`implements` / method-set), and it is a concrete
hook for the **graph-as-verifier** product: "you changed these methods but not the
interface(s) that declare them." Notably the **V arm had graph access and still
missed it** — so the current Prism output does not surface the declaring interface
prominently enough, or the agent did not think to query it. That is a precise,
actionable target rather than a vague "graph helps," and a lead for the verifier's
next iteration.

### 5.5 Replication check on out-of-sample tasks (the key caveat)

The §5.1 headline is built from three tasks selected, in part, because they
exercise the hypothesised mechanism. To test whether the effect is an artifact of
that selection, we built **new** completeness tasks by a fixed, outcome-blind rule
— recent merged Grafana PRs that change an interface method's signature, ground
truth taken from the PR diff (codegen/mocks filtered), audited to a single
interface. **The advantage did not replicate.**

| new task (full cell, 15 runs/arm) | T over-confident | G over-confident |
|---|---|---|
| `grafana-cleanup-impact` (LifecycleManager) | 8/15 | **8/15** (no gain) |
| `grafana-pr112043-impact` (ResourceIndex/SearchBackend) | 5/15 | **8/10** (worse) |

On both, the **graph reduced confident errors little or not at all**, and the
dominant missed site was again the **interface declaration** — exactly the §5.4
blind spot, which the graph does *not* currently fix. (Two further outcome-blind
tasks were queued; the campaign was stopped once the pattern was clear.) The
greppable controls (`querydata`/`checkhealth`/`callresource`) reached recall ≈1.0
for every arm — no effect, as expected.

**Interpretation, stated plainly.** The clean §5.1 effect appears tied to a
specific structure — *dense, ambiguously-named call sites* (e.g. 122750's `Set`×49)
— and does **not** generalise to interface-declaration changes, where neither text
nor the current graph succeeds. We cannot yet distinguish "the effect is real but
narrow" from "the three headline tasks were favourably selected." Resolving this
needs a pre-registered, outcome-blind task sample large enough for the task-level
statistics in §7 — the single most important open item.

---

## 6. Graph-quality ablation (H7) — *in progress*

The causal claim: hold everything constant and toggle a known graph-precision knob
— the interface-dispatch fix (grove v0.13.0, which collapsed a 45-way fanout to the
real implementors). If recall / over-confidence move with graph precision while
nothing else changes, graph *quality* — not mere graph *presence* — causes the
outcome.

**Implementation (clean toggle).** That fix and a new `Neighbors` accessor landed
in one commit. We surgically **reverse only the 12-line dispatch-fix hunk** in
`internal/graph/edges.go`, leaving `Neighbors` (and thus prism's graph path)
intact, and build the *released* prism v0.15.0 against this pre-fix grove. The ON
binary (`~/bin/prism`) and OFF binary therefore differ **only** in dispatch
precision — same prism code, same model, same task.

**Scope (1-day budget).** We run the OFF condition on **122750**, the task the fix
directly targets (interface-dispatch fanout on `Set`), G arm × 3 models × 5
trials, compared against the existing ON data. 126004 (rename) and 120119
(interface-decl) are not dispatch-fanout tasks, so the fix is not expected to move
them; 122750 is the decisive case. *Result pending this run; to be filled in.*

---

## 7. Discussion

**When a graph helps.** Not on greppable work (localization, uniformly-named
impls) — there it ties text on quality and on the cheap axes. It helps on
**completeness-critical change tasks** whose sites are ambiguous-by-name or buried
in large files, and its value is bounded **below** by task difficulty (easy tasks
need nothing) and gated **above** by model capability (the model must be able to
drive it). Within that band it converts silent, confident incompleteness into
complete, calibrated answers.

**The product implication.** The strongest, cheapest configuration is not "replace
grep with the graph." It is the **verifier**: search with text, then use the graph
to *check completeness* before declaring done. V recovers most of G's benefit
(over-confidence 9% vs T's 16%), and the interface-declaration blind spot — which V
still missed despite having graph access — tells us exactly what the verifier must
surface next. The likely real product is a **correctness gate**, not a search
replacement.

**Why token framing is the wrong objective.** The cost/quality table shows the
decision that matters is not tokens but cost-of-error: a graph that turns a 16%
confident-incompleteness rate into 2% pays for itself the first time it prevents a
shipped broken change, regardless of token deltas, which are a wash.

---

## 8. Threats to validity

- **Sample size / selection (the dominant threat).** The headline is **three
  tasks**; the unit of analysis is the task, so this is far below what a
  task-level significance test needs, and the three were chosen partly because
  they show the mechanism. Our own out-of-sample replication (§5.5) found the
  effect *did not* carry to interface-declaration tasks. Until a pre-registered,
  outcome-blind task sample (target ~15–30) reproduces it, the result must be read
  as a **pilot/existence-proof of a conditional effect**, not a general finding.
  This is the first thing a reader should weight, and the top future-work item.
- **Construct (recall-vs-PR).** PRs may over/under-change. We mitigate with the
  independent `go-ssa-vta` oracle as primary completeness ground truth and treat
  the PR diff as secondary; test sites are scored neutral. PR-diff ground truth
  *breaks on codegen* (a mockery-regenerated PR was excluded for touching ~15
  unrelated methods); codegen-heavy PRs are excluded, or routed through the
  semantic oracle.
- **Circularity.** The graph is never scored against itself — the oracle is
  external (compiler-grade).
- **Internal (stochasticity / prompt sensitivity).** 5 trials/cell with
  tail-aware reporting; one frozen prompt per arm; we observed and acknowledge
  prompt sensitivity. The mixed-effects significance model (Wilcoxon + Holm +
  Cliff's δ, task/project random effects) is **[PENDING]**.
- **External (project/task/model).** This pilot is **Go-only**; the Java and TS
  conditions (H5 graceful-degradation) are **[PENDING]**. The three-model sweep
  partially answers the single-model generalizability concern but breadth across
  languages is the open threat.
- **Build/test flakiness.** Mode A sidesteps it; Mode B (affected-tests-only,
  retry policy) is **[PENDING]**.
- **Data integrity.** After a week of interrupted collection (laptop sleep, /tmp
  cleanup, rate limits) all 332 ok runs were audited: process freezes resume or
  error out (excluded), one parser mis-score was found and fixed
  (`raw_decode`-based parser; reparsing all 332 changed exactly 1 run, a
  localization task outside the headline). The headline is unchanged. The corpus
  is persistent (`~/gvg-corpus`); runs are paced + caffeinated to survive rate
  limits.

---

## 9. Conclusion

A resolved code graph does not beat text search on the variables the field
optimizes — tokens and latency are a tie. On a small pilot we find a **conditional**
effect on the variables that matter for change tasks: on three tasks with dense,
ambiguously-named call sites, text search is intermittently and *silently*
incomplete (claims complete while wrong) and the graph cuts that confident-error
rate ~7× (16% → 2%), largest for weaker/cheaper models and most cheaply delivered
as a **verifier / correctness gate**. But the effect is **narrow and not yet
established**: when we sampled new tasks by an outcome-blind rule it did not
replicate, and on interface-declaration changes the graph fails just as text does
(a robust negative and a concrete target for the verifier). We therefore present
this as an existence proof of a conditional benefit plus a reproducible failure
mode — not as "graph beats grep." Whether the benefit survives a pre-registered,
outcome-blind task sample (the dominant open question), together with the causal
ablation (§6), Java/TypeScript breadth, and Mode B, determines whether this becomes
a general result; those are scoped in §3, §6, and §8.

---

## Artifacts

Harness, tasks, oracle integration, and raw logs target an ACM **Reusable**
artifact badge. Harness: `harness/` (`schema.py`, `score.py`, `run.py`,
`arms.py`, `extract_task.py`, `oracle_task.py`, `reparse_all.py`). Tasks:
`harness/tasks/*.json`. Run data: `harness/runs/` (gitignored; the source of §5).
Corpus is machine-local (`~/gvg-corpus`), regenerable per `HANDOFF.md` §4.
