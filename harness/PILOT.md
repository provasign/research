# Phase-1 pilot — first results (2026-06-15)

First end-to-end pilot of the graph-vs-grep harness. **Goal (design §13): validate
the harness + metrics and see whether effects are detectable — not yet to prove
the thesis.** Mode A, arms T/G/V, 3 trials/cell.

## Tasks

| id | repo | type | sites | source |
|---|---|---|---|---|
| gin-4645 | gin | localization | 2 | PR #4645 (Hijack/CloseNotify panic) |
| grafana-120266 | grafana | localization | 1 | PR #120266 (Jaeger empty-trace panic) |
| grafana-124935 | grafana | localization | 2 | PR #124935 (alerting ORM table bug) |
| grafana-126004 | grafana | impact (rename) | 7 | PR #126004 (export ToSnowflakeRV +callers) |

## Result (initial 4-task Opus pilot — superseded by the Update below)

> The Opus-only result was "no effect"; adding **more trials** and a
> **weak-model arm** (next section) revealed a real **model × task-type**
> interaction. Read the Update for the actual conclusion.

**Every arm scored recall = precision = F1 = 1.0 on every task. Zero
over-confidence errors. Zero arm-boundary violations after re-runs.**

Median across the 27 scored Grafana runs (gin omitted; all 1.0):

| arm | recall | F1 | turns | wall (s) |
|---|---|---|---|---|
| T | 1.0 | 1.0 | 9 | 71 |
| G | 1.0 | 1.0 | 7 | 53 |
| V | 1.0 | 1.0 | 8 | 56 |

G is marginally more *direct* (fewer turns, lower wall) but the **outcome is
identical**. This is exactly the design's framing: on these tasks the only
difference is on the cheap axes, and even there it's small.

## What this validates

- **The harness works end-to-end** on a 218 MB / 93k-symbol repo: PR→task
  extraction, arm enforcement (proven per-run via `tool_trace`: T `graph=False`,
  G `graph=True`), Mode-A scoring, calibration + cost capture, error handling.
- **The metrics discriminate.** #126004 initially scored precision 0.64 — which
  correctly flagged a *ground-truth* bug (test call sites were excluded from GT
  but the agents rightly listed them). Fixed: test sites are scored neutral.
- **H1 holds.** On localization, graph = text (both 1.0).

## What this does NOT yet test — the critical gap

Every pilot task is **greppable**: a stack-trace-localized bug, or a rename
(textually findable). On #126004 **T and G produced identical answers** because
a rename is exactly what grep is good at. None of these tasks exercise the
thesis case — **interface / dynamic dispatch where grep is *silently
incomplete*** (the 11-of-58 / 45-fanout scenario, H2/H3). Until the task set
includes those, the pilot cannot move the headline metric.

**Next curation target:** Grafana PRs where the fix must touch all
implementations of an interface, or callers reached through an interface field
(e.g. the `SecretsStore.Get` dispatch family the grove v0.13.0 fix addressed),
where a grep on the method name over- or under-matches. These are the tasks
where recall(T) < recall(G) and over-confidence(T) > 0 should appear.

## Update (2026-06-16): the effect is real — it's a model × task-type interaction

Two follow-ups changed the conclusion from "no effect" to a **conditional
effect**.

**(1) More trials exposed the graph advantage on distributed dispatch.** The
single-trial probe misled: at 3 trials, on the cross-package task
`grafana-120119`, **T missed sites in 1/3 runs (overconfident) while G was 3/3**
— the graph's first reliability edge, exactly where predicted (impact spread
across packages).

**(2) The weak-model arm (Haiku) is the headline.** Re-running all 6 tasks with
Claude Haiku (`run.py --model haiku`, namespaced under `runs/<task>/haiku/`)
against the Opus baseline:

| task (type) | Haiku **T** recall | Haiku **G** recall |
|---|---|---|
| 120266, 124935 (localization) | [1,1,1] | [1,1,1] |
| 126004 (rename impact) | **[0.29,1,1]** +1 overconfident | **[1,1,1]** |
| 122750 (dispatch, Set×49) | [0.94,1,1] +1 overconfident | **[1,1,1]** |
| 120119 (cross-pkg) | [0.87,0.87,1] +2 oc | [0.87,0.87,0.93] +3 oc |

**Finding: the graph's value is a function of (model capability × task type).**
On localization it is nil for both models. On impact/dispatch tasks the weak
model with **text** drops recall and goes **overconfident**, but with the
**graph** it is reliably complete (Haiku-T 0.29 → Haiku-G 1.0 on 126004). Opus
is strong enough to read/grep its way to completeness, so the effect is *masked*
at the frontier model. This reframes the thesis from "graph beats grep" to
**"the graph is a completeness/calibration equalizer on completeness-critical
tasks, most valuable for weaker (cheaper) models"** — a cost/quality result.

`120119` is instructive, not broken. The two consistently-missed sites (across
18 runs) are **interface declarations** — `RouteService` and a second
package-private `routeService` interface, both declaring the changed methods.
Agents reason in terms of *functions* and miss the type decls whose method
signatures must also change; with two such interfaces, finding one and missing
the other is a real completeness gap (not a GT artifact — the extractor's
`type ... interface` capture is correct here). A clean qualitative example of
what "completeness" costs, and why an interface-aware graph helps.

## Oracle-grounded adversarial tasks (design's primary oracle)

`grove-eval` (built `GOWORK=off go build ./cmd/grove-eval`) generates a
**go-ssa-vta** call graph — the independent, compiler-grade oracle (never grove
vs grove). `oracle_task.py` turns it into an impact task: for a target method,
ground truth = every implementation + their *complete* direct-caller set (which
can expose call sites a PR diff or a grep silently misses). `--impl-scope`
disambiguates same-named methods (gin's `Context.Render` vs the `render.Render`
interface).

First oracle task: **`gin-render-impact`** — gin's `render.Render` interface has
**12 implementations scattered across 12 files** + the `Context.Render`
dispatcher (13 sites). Enumerating all 12 is the adversarial completeness
challenge; results pending (running T/G/V × 5 on Opus + Haiku).

## gin-render negative control + the cost/quality headline

**`gin-render-impact` (oracle task, 12 scattered `render.Render` impls):** all
arms, both models, recall=1.0 (5/5). A clean **negative control** — the impls
are uniformly named (`Render`), one per file, in a dedicated `render/` package,
so `grep "func.*Render" render/` finds all 12 even for Haiku. *Implementation
count alone does not defeat grep;* the discriminator is **findability** (name
ambiguity + sites buried in large files), not interface fan-out. Refines the
earlier #126004/#122750 weak-model effect: it was driven by dense call sites in
large files + ambiguous names (`Set`×49), not "dispatch" per se.

**Cost/quality (median over 5 trials, `total_cost_usd`):**

| task | Opus-T | Haiku-T | Haiku-G |
|---|---|---|---|
| 120266 | 1.00 / $0.18 | 1.00 / $0.20 | 1.00 / $0.26 |
| 124935 | 1.00 / $0.55 | 1.00 / $0.44 | 1.00 / $0.35 |
| 126004 | 1.00 / $0.36 | 1.00 / $0.17 | 1.00 / $0.16 |
| 122750 | 1.00 / $0.51 | 1.00 / $0.29 | 1.00 / $0.28 |
| 120119 | 1.00 / $0.85 | 0.87 / $0.39 | 0.87 / $0.43 |

**Headline: Haiku+graph matches Opus+text median quality at ~half the cost** on
impact/dispatch tasks, *and* removes Haiku-text's catastrophic tails +
overconfidence (the 0.29 outlier on 126004). The exception is `120119` — the
interface-declaration task neither Haiku arm fully solves (0.87): a real ceiling.
(Caveat: medians hide variance; the calibration value of G is in the *tails* —
report worst-case recall + over-confidence rate, not just medians.)

## Qualitative finding: the interface-declaration blind spot

Across the dispatch tasks, the single most consistently-missed change-site is
the **interface *declaration*** — `DataKeyCache` (122750), `RouteService` and
`routeService` (120119). Reading the transcripts, the failure is systematic and
the same every time: the agent enumerates every *implementation* and *caller*
thoroughly (122750 Opus-V even listed the test doubles and test funcs), then
asserts `"complete": true, "unresolved": []` — while omitting the interface type
whose method signatures must also change.

This is a structural blind spot: agents reason in terms of functions/methods and
forget that a method's signature is *also declared on its interface*. It is
exactly the fact a graph encodes (`implements` / method-set), so it is a concrete
hook for the **graph-as-verifier** product: "you changed these methods but not
the interface(s) that declare them." Notably the **V arm had graph access and
still missed it** — so the current prism output doesn't surface the declaring
interface prominently, or the agent didn't think to check it. A precise,
actionable target rather than a vague "graph helps."

## Methodological lessons (captured in the harness)

1. **API-outage runs must be excluded, not scored 0.** The first batch hit an
   Anthropic API outage mid-run; naive scoring counted dead runs as recall 0.
   `run.py` now detects errored runs (API error / timeout / zero tokens),
   retries, and excludes them from scoring (`status:error`).
2. **Test-site scoring policy.** Production change-site completeness is the
   headline; test call sites are scored neutral (a rename legitimately changes
   them, a bug fix optionally adds them) — see `score.py:_is_test_path`.
3. **PR-diff ground truth is sound** for these tasks: #126004's extracted 7
   prod sites matched an independent grep of all callers.
4. **PR-diff ground truth breaks on codegen.** Candidate dispatch task #79392
   (signature change) was dropped: its merged PR regenerated mockery mocks, so
   the diff touched ~15 *unrelated* methods (DeleteProvenance, SetProvenance, …)
   that changed only as regeneration churn, not because of the signature change.
   A correct agent would be penalised for omitting them. Lesson: exclude
   codegen-heavy PRs, or use the go-ssa-vta semantic oracle (the design's
   primary oracle, task #7) which computes the true impact set. The chosen
   thesis task #122750 has hand-written implementations (no mock churn).
5. **Token accounting is not yet cumulative.** The stream `result` event's
   `usage.input_tokens` reflects only the final turn (~2.3k for all runs); sum
   per-assistant-event usage for true totals before reporting RQ4 token cost.
   Use `num_turns` / wall as the cost proxy until then.
