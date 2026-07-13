# End-to-end agentic benchmark — does a code graph help a *regular* coding agent?

Design note. Status: arms defined (`ab_endtoend_arms.py`), runner + task set to
build. This is the benchmark that answers the practical question the
change-impact study does not: on the work a normal agent actually does — real
bug fixes, mostly localized — does a code graph beat agent-only, and is it
Prism's G/G* or CodeGraph?

## Why the existing benchmarks don't answer this

The change-impact study (paper) is rigorous but narrow: it measures **recall on
one task type** — "list every site a signature change breaks" — which is exactly
the task a type-resolved graph is built to win. It proves the *mechanism*
(completeness at task altitude, tier-invariance) but it does not tell you whether
a graph helps an agent fix an ordinary bug. Everything else Prism exposes
(`untested_surface`, `dead_code`, `affected`, `missing_implementations`) has **no
oracle-scored benchmark at all**, and the "add feature / explain code" tasks
exist only as n=1–3 directional product A/Bs. This benchmark fills that gap.

## The question, stated precisely

For each arm, **resolve rate** on real post-cutoff tasks: does the agent's edit
make the repo's own `fail→pass` test pass, with no `pass→fail` regression?

- **agent-only** (grep/read) — the default in Claude Code / Cursor / Amp
- **agent + Prism G** — primitives (agent orchestrates)
- **agent + Prism G\*** — task altitude (agent reads whole answers)
- **agent + CodeGraph** — its `explore`

## What makes it defensible

1. **Real oracle, not a proxy.** The repo's own test suite in Docker
   (`fail→pass` + `pass→pass`). Binary: the agent fixed it or it didn't. No
   synthetic recall metric we chose.
2. **Contamination-free by construction.** Tasks are issues merged **after the
   model's training cutoff** (Jan 2026) — verified with `contamination_check.py`
   against the gold patch, the same check that caught the SWE-bench run measuring
   memorization. A memorized 2024 fix can't stand in for tooling here.
3. **Representative, not cherry-picked.** Tasks are selected by an outcome-blind
   gate *before* anyone sees which arm wins — the opposite of hand-picking
   change-impact tasks. This is the whole point: let the natural task
   distribution decide.
4. **Only the context tool varies.** Every arm reads, edits, and builds
   identically (`ab_endtoend_arms.py::_EDIT_AND_BUILD`); the G/G\* split is
   enforced by **per-tool MCP allowlisting**, not by prompt, so an arm cannot
   drift into a capability it isn't supposed to have.

## Using G and G\* *correctly* — the design's core decision

The failure mode we are avoiding: **forcing `change_impact` (G\*) onto a
localized task.** `change_impact` answers "what breaks if this signature
changes" — irrelevant to an ordinary one-function bug fix. An arm steered to
call it on everything would misfire and make the graph look bad for a reason
that isn't real.

So **G\* ≠ change_impact. G\* = task altitude, and its everyday operation is
`prism_query`** (task + anchor terms → ranked code, callers, tests, coverage
gaps in one call). The task-shaped ops are *also* G\*, but they fire **only when
the task is that shape**:

| Task shape | Right G\* op |
|---|---|
| ordinary bug / localized fix | `prism_query` (the default; usually the only context call) |
| a signature/type is changing | `prism_change_impact` |
| a rename | `prism_rename_plan` |
| a new required interface member | `prism_missing_implementations` |
| "what should I test" | `prism_untested_surface` |
| cleanup / reachability | `prism_dead_code` |

The G\* steering (`_GSTAR_GUIDANCE`) says exactly this: **query first; task-shaped
op only on task shape; never force `change_impact` on a localized fix.** The
`G` arm, by contrast, gets only primitives and must assemble context itself —
that contrast is the paper's altitude thesis, tested end-to-end.

**CodeGraph's `explore` is the honest peer of `prism_query`** — both are one-call
task context. So the codegraph arm sits at the same altitude as the G\* default,
and Prism's G\* additionally carries the type-resolved tail ops CodeGraph lacks.
That is the fair form of the Prism-vs-CodeGraph comparison: not "our recall
metric," but "on real bug fixes, whose one-call context tool helped the agent
more."

## The honest result we pre-commit to reporting

On a random sample the graph's advantage will likely be **diluted**, because
most everyday fixes are localized — find the function, fix it, tests pass; grep
suffices. The graph should bite on the **tail**: changes with blast radius,
cross-file reasoning, wide inheritance. **A null result on localized tasks is a
real finding and we report it as one.**

So every task is **stratified by blast radius** (computed blind, by the graph
itself, before scoring), and we report two numbers:

- **aggregate** — does the graph help a *random* task? (possibly a wash)
- **conditional** — does it help on the high-blast-radius quartile? (where the
  mechanism predicts the gap, and where name-resolution CodeGraph should start
  losing to type-resolution Prism)

We also record, per task, **whether the agent used a graph op at all and which
altitude** (`GRAPH_TOOL_PREFIXES`) — so "on localized tasks the agent fell back
to grep even when the graph was available" is itself reportable.

## Reused vs to-build

- **Reuse:** `swebench_ab.py` (2 arms → 4; extend `ARMS` import from
  `ab_endtoend_arms.py`), its Docker `fail→pass`/`pass→pass` eval, the
  `tool_trace` allowlist enforcement, `contamination_check.py` (to *verify* the
  post-cutoff set is clean).
- **Build:** the post-cutoff task set (mine issues+PRs merged after 2026-02;
  Python first, where the Docker eval infra is turnkey — multi-language
  end-to-end test harnessing is the stretch goal), the blast-radius stratifier
  (one grove call per task), and the four-arm runner loop.

## Open decisions (cost/scope, not design)

1. **Headline model** — Sonnet (the "regular agent" a real user runs), and
   whether to add Haiku in the pilot to test the paper's weak-model
   amplification prediction from task one.
2. **Task mix** — bugs-only first (cleanest oracle), features later (a passing
   test doesn't prove a feature is *right*).
3. **Scale** — pilot ~25 tasks × 4 arms to read effect size, then 100+ for
   significance.
