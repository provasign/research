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

## Result

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
4. **Token accounting is not yet cumulative.** The stream `result` event's
   `usage.input_tokens` reflects only the final turn (~2.3k for all runs); sum
   per-assistant-event usage for true totals before reporting RQ4 token cost.
   Use `num_turns` / wall as the cost proxy until then.
