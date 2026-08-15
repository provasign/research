# In-band consolidation nudge — test report (2026-08-15)

## Question tested

Agents hedge unknown symbol names by searching candidate terms one at a
time (formerly `grep "a\|b\|c"`, now sequential single-term
`prism_search` calls). v0.50.2 added steering prose telling them to
consolidate into one `prism_query(terms=[...])` call. Does delivering
that same advice **inside the search results at decision time** (the
channel where the PreToolUse hook's deny message achieves ~100%
compliance) change the behavior where prose did not?

## Setup (identical across all runs)

- Task: `Kinto__kinto-3566` — "Implement metric for cache hit ratio",
  Kinto/kinto @ `f4da0160f7eec83b5571548954ab64c59d63695a`
  (SWE-bench-Live valid instance)
- Model: sonnet via headless `claude -p`, fresh worktree per run
- Deployment: real `prism init --deny-builtin-search` (PreToolUse hook +
  permissions.deny + project `.mcp.json`), repo indexed before run
- Measured: tool-call sequence (single-term searches vs multi-term
  `prism_query`), nudge deliveries, turns, cost

## Mechanism check (free, no model)

Live MCP session, three sequential searches: results 1–2 clean, result 3
carries the note verbatim with the accumulated terms:

> this is your 3rd sequential search — one call covers all these
> candidates AND expands the call graph from whichever lands:
> prism_query(task="<what you are doing>", terms=["cache_hits",
> "cache_misses", "hit_ratio"])

Pinned by `TestSearchStreakNoteFiresOnThirdDistinctSearch`.

## Runs

| # | Version | Searches | Nudges | Consolidated? | Turns | Cost | Evidence |
|---|---------|----------|--------|---------------|-------|------|----------|
| 1 | v0.50.2 prose only | 9 | — | No | 19 | $0.48 | transcript deleted (process error) |
| 2 | v0.50.3 nudge | 10 | 2 | Yes, once: `terms=["cache","metrics","prometheus","counter"]`, then drifted back, ignored 2 later nudges | 19 | $0.38 | transcript deleted (process error) |
| 3 | v0.50.2 control | 5 | — | No | 11 | $0.51 | `control.jsonl`, `control.diff` |
| 4 | v0.50.3 treatment | 16 | **14** | **No — all 14 ignored** | 27 | $0.56 | `treatment.jsonl`, `treatment.diff` |

Run 4 search sequence (from the preserved transcript):
`cache_hits_total, cache_misses_total, cache_hit, metrics.count,
class Cache, metrics.count(, registry.metrics, hits_total,
cache hit ratio, grafana, cache_hits, permission_cache, lru_cache,
memoize, CHANGES.rst, class PrometheusService` — plus one
`prism_lookup(safe_wraps)`. Zero `prism_query`.

## Result

**The nudge does not reliably change behavior.** 1 consolidation in 2
treatment runs; the failing run was worse than its own control on every
metric. The mechanism works as coded; the behavioral effect is unproven.

Refined interpretation: the hook's ~100% steering number comes from
**channel + consequence** — a deny blocks the action, forcing a course
change. An advisory note in the same channel blocks nothing and performs
like ordinary advice. Channel placement is necessary but not sufficient.

## Limits

- One task, one model tier, n=2 per arm — direction, not proof, either way
- Fix correctness never scored against the SWE-bench oracle (diffs
  preserved, resolve status unknown)
- Runs 1–2 transcripts were deleted before review; only runs 3–4 are
  fully evidenced

## Ships resulting from this test

- **v0.50.3** — the nudge; shipped prematurely on run 2 alone (n=1)
- **v0.50.4** — correction: effectiveness claim retracted to "unproven";
  nudge throttled to once per streak (14 repeats demonstrably did
  nothing; wallpaper by the codebase's own `resolvedRefNote` discipline)
