# Does a Code Graph Beat Text Search for Agentic Coding? — Study & Paper Design

**Status:** design draft v0.1
**Working title:** *Beyond Token Budgets: A Controlled Study of Code-Graph vs. Text-Search Context for LLM Coding Agents*

---

## 1. Thesis

The agentic-coding tooling conversation optimizes the **cheap** variables — tokens
and latency. Our own pilots show that on those axes a resolved code graph
(Grove/Prism) only *ties or marginally beats* text search (grep/ripgrep + read).

We argue the field is measuring the wrong axis. The value of a code graph is in
the **expensive** variables: **completeness, precision, and calibration** on
*change-* and *impact-* tasks — i.e., whether the agent produces a **correct and
complete** change, and whether it **knows what it doesn't know**. On those tasks
text search returns a *silently incomplete* answer (e.g. grep finds 11 of 58
interface-dispatched call sites) that the agent ships with confidence. Tokens are
cents; a missed call site is a broken build. The graph's value therefore scales
with **(a) task type, (b) graph accuracy (≈ language), and (c) cost of error** —
none of which token-centric evaluation captures.

**Decision relevance:** the paper's findings directly set Grove/Prism's product
direction — search-replacement vs. correctness/verifier layer; which languages
justify deeper resolution; whether the token framing is dead.

---

## 2. The variable framework (conceptual contribution #1)

A taxonomy for evaluating *any* code-context mechanism for agents. Three cost
axes, six quality axes, one outcome, one re-weighting meta-variable.

**Cost (what you pay)**
1. **Token usage** — context-budget consumed.
2. **Latency** — wall-clock per operation / per task.
3. **Round-trips** — tool calls / reasoning hops.
4. **Setup & maintenance** — index build, server, freshness upkeep (text = 0).

**Quality (what you get)**
5. **Completeness / recall** — found *all* relevant sites.
6. **Precision** — what was found is *correct* (no false positives).
7. **Calibration / trust** — answer signals its own reliability and *what it
   could not resolve*. (Text scores ~0 here by construction.)
8. **Freshness / drift-resistance** — reflects current code incl. uncommitted
   mid-task edits.
9. **Breadth / robustness** — works across languages & constructs; degrades
   gracefully on dynamic dispatch / reflection / codegen.
10. **Determinism** — same query → same answer.

**Outcome (the dependent variable that matters)**
11. **Task success** — agent ships a *correct, working* change (build green,
    fail-to-pass tests pass, pass-to-pass preserved).

**Meta (re-weights all of the above)**
12. **Cost of being wrong (stakes)** — a missed caller / false "safe to delete"
    costs a broken build, a bug, a rollback — orders of magnitude more than the
    tokens saved. This is *why* token optimization is the wrong objective on
    change tasks.

---

## 3. Research questions

- **RQ1 (Completeness/Precision).** For completeness-critical tasks (find every
  site a change must touch), what recall/precision does each approach yield,
  scored against an **independent compiler-grade oracle**?
- **RQ2 (Task success).** Does graph context raise the rate of *correct, working*
  patches, and how does the effect vary by task type?
- **RQ3 (Calibration).** Does the graph make the agent aware of unresolved /
  ambiguous cases, and does that reduce *confident errors* (claimed-complete but
  wrong)? Text provides no such signal — measure the gap.
- **RQ4 (Cost).** Tokens, latency, round-trips — reported as **cost-per-correct-
  outcome**, plus a **break-even analysis** over cost-of-error, not in isolation.
- **RQ5 (Modulators).** How do RQ1–4 vary with **graph accuracy** (Go ≈ high,
  Java ≈ medium, one more), **task type**, and **repo scale**?
- **RQ6 (Configuration).** Is the graph best as a *search replacement* (G arm) or
  as a *verifier/safety gate* on top of text (V arm)?
- **RQ7 (Causality, ablation).** Holding everything else fixed, does **graph
  precision itself** cause the outcome change? (We can toggle a known graph-
  precision knob — the interface-dispatch fix.)

---

## 4. Independent variables (factors)

| Factor | Levels |
|---|---|
| **Tool arm** | **T** text-only (rg/grep/find/read) · **G** graph-primitives + text-for-discovery · **V** text-primary, graph-as-verifier (check completeness before finalizing) · *(opt)* **G-only** |
| **Task type** | localization · impact/refactor · dead-code/safety · test-coverage · comprehension |
| **Language / graph accuracy** | **Go** (high, F1≈0.94) · **Java** (medium, F1≈0.76) · **TypeScript** (high, tsc-backed F1≈0.98) |
| **Graph quality (ablation, within G)** | dispatch-fix ON vs OFF (precision knob we control) |
| **Agent model** | **One**, pinned: a single Claude Opus snapshot (latest available; pin the exact build for reproducibility). *Single-model = a noted external-validity threat (see §10); mitigation: confirmatory subset on a 2nd model if a reviewer asks.* |

**Decisions locked (v0.1):** Primary mode **A**. Languages **Go / Java / TypeScript**.
Arms **T, G, V from day one**. One pinned Claude Opus model. Venue: **ACM TOSEM**
primary + **arXiv** preprint (§14).

**Language design note:** Go and TS are *both* high-accuracy graph conditions
(Go via `go/types`+SSA, TS via the tsc compiler API), Java is the medium-accuracy
condition. This gives two independent "graph is accurate" points (guards against a
Go-specific fluke) plus one "graph is imperfect" point for the graceful-degradation
story (H5).

---

## 5. Subjects: tasks from real projects

**Ground-truth mechanism (SWE-bench lineage, extended).** Each task is built from
a **merged PR** that fixes a bug or adds a small feature:
- Repo pinned at the **parent commit** (pre-fix).
- The **issue text** is the task prompt (symptom, not solution).
- The **PR** is ground truth: changed functions/files = completeness target;
  PR-added tests + build = task-success oracle (fail-to-pass / pass-to-pass).

**Two evaluation modes:**
- **Mode A — Context quality (primary, isolates the tool).** Agent must *answer
  the context question* (e.g. "list every site that must change to do X"). Score
  recall/precision/calibration vs the **independent oracle** + PR. No patch
  required → removes the LLM's coding-skill confound, scales to many tasks.
- **Mode B — Task success (validation, end-to-end).** Agent must produce a
  *patch*; we apply it and run the affected tests. Noisier (coding ability
  dominates) but shows the context effect survives end-to-end. Run on a tractable
  subset.

**Independent oracle (critical — avoids circularity).** Completeness ground truth
must **not** come from Grove. Reuse compiler-grade oracles already in the Grove
eval harness: `go-ssa-vta` (Go), `roslyn` (C#), `javac/WALA/Soot` (Java),
`ts-compiler-api` (TS), dynamic trace (Python). Both arms are scored against the
*same external oracle*. The PR diff is a second, human-validated ground truth.

**Projects (locked).**
- **Go — Grafana** (large, real; graph F1≈0.94) + one mid-size Go service for
  build-speed in Mode B. The accurate-graph @ scale condition.
- **Java — Jackson-databind** (chosen). Rationale: heavy **polymorphic
  serializer/deserializer dispatch** — exactly the interface-resolution case where
  a graph beats grep (the crux of H2/H5); disciplined issue→PR history with
  fail-to-pass tests; **fast per-class Maven tests** (essential for Mode B);
  moderate size, indexes cleanly. *Fallbacks if build friction: Apache Dubbo
  (even more SPI/interface dispatch, heavier build) or Apache Commons (small,
  fast, but utility-heavy → less dispatch).* The medium-accuracy condition.
- **TypeScript — NestJS** (chosen). Rationale: DI/providers + decorator-driven
  **interface dispatch**, large real issue/PR history, Jest tests; tsc-backed
  graph is high-accuracy, giving a *second* accurate-graph data point distinct
  from Go. *Fallback if build/test friction: a mid-size lib (e.g. TypeORM, or a
  smaller well-tested package).*

**Task selection (pre-registered criteria, to limit bias):** merged within a
bounded window; touches code present at the pin; has runnable tests; spans the
task-type taxonomy; excludes pure-docs/format; size-bounded (e.g. 1–15 changed
functions). Target ~30–60 tasks/language balanced across task types.

---

## 6. Metrics (operationalized)

| Variable | Metric |
|---|---|
| Completeness | **Recall** of required change-sites vs oracle |
| Precision | **Precision** of proposed change-sites; report **F1** |
| Task success | **% patches** that build + fail-to-pass pass + pass-to-pass preserved |
| Calibration | **Over-confidence rate** = P(agent asserts complete ∧ is incomplete); **gap-surfacing rate** = did the tool expose unresolved/ambiguous edges; *(opt)* Brier score from elicited confidence |
| Token usage | total context tokens consumed |
| Latency | wall-clock tool time (MCP, warm) and end-to-end |
| Round-trips | tool-call count |
| Cost-efficiency | **tokens-per-correct-outcome**; **break-even error cost** (threshold where G nets positive) |
| Robustness | metric deltas across language/graph-accuracy levels |

---

## 7. Protocol & statistics

- **Paired design:** identical tasks across arms; only the tool description differs.
- **Trials:** N = 5–10 runs per (task × arm × config) to handle agent stochasticity;
  report **median + IQR**, not means.
- **Tests:** paired non-parametric (**Wilcoxon signed-rank**) per RQ; **Holm**
  correction across comparisons; effect sizes (**Cliff's δ**). A **mixed-effects
  model** with *task* and *project* as random effects for generalization.
- **Blinding/automation:** build/test = objective; recall/precision = automated vs
  oracle; calibration from structured logs. Human validation on a sampled subset.
- **Reproducibility:** pinned commits, containerized build/test, fixed model
  snapshots, released harness + tasks + raw logs.

---

## 8. The causal ablation (contribution highlight)

We control a **graph-precision knob**: the interface-dispatch fix (45→3 fanout).
Run the **G arm with the fix ON vs OFF** on the same tasks. If task success /
recall move with graph precision while *everything else is held constant*, we get
a **causal** claim — graph *quality*, not merely graph *presence*, drives outcome.
This is rare in tool-comparison studies and strengthens the paper substantially.

---

## 9. Hypotheses (pre-registered)

- **H1.** On localization tasks, T and G are statistically indistinguishable on
  task success; G shows no token win large enough to matter. *(Graph ≠ better
  search.)*
- **H2.** On impact/refactor/dead-code tasks, G ≫ T on recall and task success;
  the gap widens with repo scale and interface/dynamic-dispatch density.
- **H3.** T exhibits high **over-confidence** (asserts complete while incomplete);
  G's gap-surfacing lowers confident errors even when recall is imperfect.
  *(Calibration is the differentiator.)*
- **H4.** Token/latency differences are small and do not predict task success;
  **cost-per-correct-outcome** favors G only once cost-of-error exceeds a low
  break-even.
- **H5 (modulator).** G's advantage shrinks as graph accuracy drops (Java < Go),
  but **calibration** (flagging unresolved cases) degrades gracefully and still
  helps. *(An imperfect-but-honest graph beats a silent text search.)*
- **H6 (config).** **V (graph-as-verifier)** matches or beats G on task success at
  lower token cost — the agent searches with text, *checks completeness* with the
  graph. *(Suggests the product is a correctness gate, not a search replacement.)*
- **H7 (causal).** Turning the dispatch-fix ON raises recall/task-success vs OFF.

---

## 10. Threats to validity (and mitigations)

- **Construct (is recall-vs-PR the right completeness measure?)** — PRs may
  over/under-change. Use the **independent compiler-grade oracle** as primary;
  PR as secondary; manual-validate a sample.
- **Circularity (scoring Grove against Grove).** — **Never.** Oracle is external.
- **Internal (agent stochasticity, prompt sensitivity).** — N trials + stats;
  one validated, frozen prompt per arm; report prompt as a fixed factor and
  acknowledge sensitivity (we observed it).
- **External (project/task/model bias).** — pre-registered selection; ≥3
  languages; ≥2 models; release everything.
- **Build/test flakiness.** — SWE-bench-style: run only affected tests; retry
  policy; exclude provably flaky tasks pre-registered.
- **Tool-effort imbalance (we tuned G's prompt).** — freeze prompts before the
  main run; report the pilot-tuning separately; give T the same engineering care.

---

## 11. Paper outline

1. **Introduction** — agentic coding needs repo context; two paradigms; the field
   optimizes tokens/latency; we argue that's the wrong axis; contributions.
2. **Background & related** — LLM SE agents; SWE-bench & repo-level benchmarks;
   retrieval/RAG for code; static call graphs & dispatch resolution.
3. **A variable framework for agent code-context** (§2).
4. **Study design** — RQs, arms, tasks/ground-truth, oracle, projects, metrics,
   protocol (§3–7).
5. **Results** — per RQ.
6. **Graph-quality ablation** — the causal knob (§8).
7. **Discussion** — when a graph helps; the verifier configuration; implications
   for tool builders and for Grove/Prism's direction.
8. **Threats to validity** (§10).
9. **Conclusion.**
- **Artifacts:** benchmark, harness, oracle integration, raw logs (badge-eligible).

---

## 12. Contributions (for the intro bullet list)

1. **Conceptual:** a 12-variable evaluation framework for agent code-context tools.
2. **Methodological/artifact:** a controlled, multi-language, real-issue benchmark
   + harness that **isolates the tool dimension** and scores against an
   **independent** oracle (not the graph under test).
3. **Empirical:** graph-vs-text across all variables; headline = value is
   *correctness + calibration on completeness-critical tasks*, not tokens,
   modulated by graph accuracy and cost-of-error; plus the **verifier** result.
4. **Causal:** a graph-precision ablation linking graph *quality* to agent outcome.

---

## 13. Execution plan (phased)

- **Phase 0 — Harness (build).** Agent runner with pluggable tool arms (T/G/V);
  containerized build/test; PR-based + oracle-based scorer; reuse Grove eval
  oracles. Logging that captures the calibration signals.
- **Phase 1 — Pilot.** 1 Go project, ~8–10 tasks across task types, arms T/G,
  5 trials, **Mode A** only. Goal: validate metrics + harness + that effects are
  detectable; refine task taxonomy and the over-confidence metric.
- **Phase 2 — Scale.** Add Java + 1 more; add V arm + dispatch ablation; full task
  set; ≥2 models; add Mode B on a subset.
- **Phase 3 — Analysis & writing.** Stats, figures, threats, draft.

**Start at Phase 1 pilot** — it tells us within days whether the thesis holds and
whether the metrics discriminate, before we invest in scale.

---

## 14. Target venue (locked)

- **Primary — ACM TOSEM** (*Transactions on Software Engineering and Methodology*):
  ACM's flagship SE journal, ideal for a controlled empirical study + artifact,
  open-access friendly.
- **Preprint — arXiv** (cs.SE), posted at submission for visibility/citation; this
  is the "online journal" presence.
- *Alternatives if scope/fit shifts:* IEEE TSE or EMSE (journals); ICSE/ESEC-FSE
  (conferences, even higher SE prestige) — keep as options after the pilot.
- **Artifact:** target an ACM **Reusable** artifact badge (released harness, tasks,
  oracle integration, raw logs).

---

## 15. Decisions — RESOLVED (v0.1)

1. **Primary mode:** Mode A (context-quality, isolates the tool). ✓
2. **Java project:** Jackson-databind (fallbacks: Dubbo, Commons). ✓
3. **Third language:** TypeScript — NestJS. ✓
4. **Model:** one pinned Claude Opus snapshot. ✓ *(single-model threat noted, §10)*
5. **Arms:** T, G, **and V** from day one. ✓
6. **Pilot size:** ~10 Go (Grafana) tasks across the task-type taxonomy, 5 trials
   each, arms T/G/V. ✓

### Single-model threat — explicit
Reviewers at TOSEM **will** flag generalizability across models. We accept one
model to keep the design tractable, and pre-register the mitigation: if asked, run
a **confirmatory subset** (e.g. the impact/dead-code tasks where the effect is
largest) on a second model. Pin the exact Opus build and report it.
