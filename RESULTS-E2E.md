# End-to-end benchmark — pilot results & morning summary (2026-07-14)

**Question:** on the work a regular coding agent actually does — real, localized
bug fixes — does a code graph help, and is it Prism-G/G\* or CodeGraph? Measured
end-to-end: the agent edits a throwaway worktree, and the repo's own test suite
scores it in Docker (`FAIL_TO_PASS` passes, no `PASS_TO_PASS` regression).

**TL;DR — the pilot's headline is methodological, not a scoreboard.** It did
exactly what a pilot is for: it surfaced a design flaw at n=5, before spending on
scale. Do **not** read the numbers below as "CodeGraph beats Prism."

---

## What was built and proven (all validated end-to-end)

A complete, reproducible, **contamination-free** benchmark pipeline:

`mine 2026 PRs → build SWE-bench task → Docker fail→pass verify → agent (4 arms
× 3 models) → Docker score`

- **Contamination-free by construction:** tasks are click PRs merged in 2026
  (post-cutoff); prompts use the linked **issue** text (bug report + repro), never
  the PR body (which leaks the fix — a leak caught and removed mid-build).
- **5 validated tasks** (click), each with a discriminating `FAIL_TO_PASS`.
- **45 informative cells** ran: haiku ×20, sonnet ×20, mason-local ×5.

## Raw resolve rate (read with the confound below)

| model | baseline | prism_g | prism_gstar | codegraph | mason |
|---|---|---|---|---|---|
| haiku  | 0/5 | 0/5 | 0/5 | **2/5** | – |
| sonnet | 0/5 | 0/5 | 0/5 | **2/5** | – |
| local  | (stage crashed — bug fixed) | | | | 0/5 (all timed out) |

CodeGraph resolved the same 2 tasks (pr3493, pr3534) on both cloud models.

## The confound that makes the arm comparison invalid (primary finding)

The graph arms' tool all-lists included `grep`/`rg`, and **the models preferred
grep and barely touched the graph.** Measured tool usage (local cells, pr3493):

| arm | graph-tool calls | grep calls | read calls |
|---|---:|---:|---:|
| baseline    | 0 | 12 | 26 |
| prism_g     | 4 | 11 | 13 |
| prism_gstar | **1** | **12** | 15 |
| codegraph   | 2 | 13 | 20 |

Every arm ran a grep-dominated loop. `prism_gstar` called `prism_query` **once**
and grep **twelve** times; even the CodeGraph arm called `explore` twice against
grep thirteen. So the graph arms collapsed toward baseline behavior, and the
resolve-rate differences **cannot be attributed to the graph.** CodeGraph's 2/5
is a weak, grep-confounded signal at n=1 per cell — not evidence the graph helped.

## What we *can* honestly say

1. **The pipeline works and is contamination-free** — the hard part (mining,
   Docker fail→pass, scoring agent diffs on fresh 2026 bugs) is proven.
2. **These subtle library bugs are hard for everything** — 0–2/5 across all
   arms and all models. Localized ≠ easy.
3. **Models default to grep even when a graph is offered** — itself a finding
   about tool adoption (steering/affordance), independent of graph quality.

## Caveats (do not over-read)

- **n=5 pilot, n=1 per cell** — directional only, not significant.
- **Mason-local 0/5 is not "Mason can't"** — all 5 cells hit the 10-min wall-clock
  cap and were killed mid-thrash (bloated diffs); it's budget-bounded
  non-convergence of a free 30B on subtle bugs.
- **Local neutral-loop stage is incomplete** — it crashed after 5 cells on a
  tool-arg bug (now fixed); it's the weak-loop control the paper already predicts.

## Two ways forward — a design fork (your call)

The confound admits two *different* valid experiments; they answer different
questions:

- **(A) Force graph use** — remove grep/rg from the graph arms' allowlists so
  discovery *must* go through the graph. Cleanly isolates "does the graph help
  vs grep." One-line change per arm; re-run haiku+sonnet graph arms (~$10–20,
  ~1–2 hr). Recommended for the headline claim.
- **(B) Keep grep available ("realistic")** — and report the real finding as
  *tool adoption*: models prefer grep even when the graph is offered, so the
  benchmark measures whether the graph is compelling enough to be used. Needs
  stronger steering to be a fair graph test.

I did **not** auto-re-run overnight: (A) spends API budget and (B) is a genuine
methodology choice that's yours to make. The lambda bug is fixed and the no-grep
arms are a one-line change away once you pick.
