# Routing program — why agents under-reach the graph, and what moves it

## The problem, evidenced

- v0.51 study (190 paired cells): prism_change_impact reached in 2/190.
- full38: graph consulted 8/198 calls; failures EDIT THE RIGHT FILE with the
  wrong (narrow) fix; wrong-design diffs verify clean. Only falsifiable bed:
  mandated-wide-fix tasks.
- Field (recent 14d, this machine): search 963 / read 837 / change_impact 119
  / query 6 — and this machine skews expert-user.
- Steering channel findings: directive MUST moves routing ~100% in-harness;
  advisory nudges failed replication (n=2); a BLOCKING channel with a stated
  consequence steers ~100%.

The engine's completeness is proven (ci_invariants recall 1.0); the loss is
at the routing layer: agents holding a fan-out question never ask it.

## What every prior arm got wrong for THIS question

All e2e arms coach the agent ("CONTEXT TOOL: ... call prism_query(...)").
That measures the tool under ideal routing, not routing itself. The missing
condition is FIELD: the worktree carries exactly what `prism init` writes
(CLAUDE.md steering block + .mcp.json), the prompt is the bare task, and the
agent decides everything. `claude -p` auto-loads CLAUDE.md from cwd, so the
field condition is free.

## Metrics (per cell)

- routing: per-tool prism calls, read from prism's own ledger (v0.56.8)
  diffed around the cell — ground truth, no transcript parsing.
- completeness: gold-file recall of the agent's diff vs the merged PR's
  gold_files (docs/CHANGES excluded) — the diff-level proxy for "found the
  whole fan-out". Docker resolve is phase-2 confirmation, not the screen.
- cost: tokens, turns.

## Phases

R0 — baseline field measurement. 3 fanout tasks (real PRs, mined as
mandated-wide sweeps) x {field-prism, field-bare} x 2 seeds, haiku.
Question: does the realistic agent call change_impact at all, and what is
its gold-file recall without it? Decision input only, no gate.

R1 — interventions, each ab_gate-style fail-fast, one variable at a time:
  a. steering-consequence: the change_impact line rewritten from advisory to
     consequence-framed (the channel finding says consequence is the active
     ingredient, not volume).
  b. in-result consequence: strengthen structuralNote in search/read results
     (the channel agents actually read mid-task) — when a searched symbol
     has fan-out, say the count and the cost of ignoring it.
  Success: gold-file recall up at <=1.2x tokens, routing rate as the
  mediating variable. A variant that moves routing but not recall is noise;
  a variant that moves recall without routing is confounded — investigate.

R2 — only if R1 moves: grow the bed via mine_wide_sweeps/promote_fanout
(the 3-task bed detects big effects only; ~50%/cell noise), and a
cross-model spot check.

## Guardrails

- Never coach in the prompt; the steering file is the only intervention
  surface. Changing BOTH steering and results in one variant is two
  experiments.
- Bed tasks are real merged PRs; gold = the PR's own diff. Audit GT before
  any conclusion (GVG lesson: audit before launch).
- The v0.55.12 batching change and v0.57.0 deferral both live in steering
  now — variants edit the SAME generated block prism init writes, so
  anything that wins ships as a one-line steering release.

## R0 results (2026-08-29, 12 cells, haiku)

- Routing: field agents used prism 5/6 cells; change_impact 2/6. The
  2/190 era is over — current steering routes at a usable baseline.
- Completeness: ZERO arm delta. Per-task recall identical (even the
  seed split reproduced in both arms). These tasks name their targets
  in the issue text: grep suffices, so the bed cannot discriminate.
  Prism arm paid ~32% more turns for equal outcome — matches the
  "enriched path on ordinary tasks" cost finding.
- REDIRECT: the bed must select FINDABILITY-HARD gold PRs (sites not
  reachable by name-grep: interface impls, registries, framework
  template/DI references). This converges with the framework-support
  question — the same mined tasks answer both "does the graph see it"
  (engine ground truth, free) and "does the agent find it" (agent
  cells). R1 steering variants are premature until the bed can detect
  a completeness delta at all.
