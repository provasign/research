# ledger A/B — mid-size TypeScript service, with and without Prism

**Date:** 2026-08-02 · **Model:** Sonnet · **Cells:** 4 complete 13-turn sessions
(2 trials × 2 arms) · **Oracle:** 341 hidden tests + `tsc` · Nothing runs through
Prism. All numbers new.

## Verdict

| | base (n=2) | prism (n=2) |
|---|---|---|
| conformance (end) | **1.000** | **1.000** |
| genuine silent misses | **0** | **0** |
| typecheck clean | 2/2 | 2/2 |
| own tests green | 2/2 | 2/2 |
| src LOC produced | 1,080 | 1,073 |
| tokens | 38.0M | 41.2M (+8%) |
| cost | $14.96 | $15.89 (+6%) |
| wall | 23.3 min | 28.9 min (+24%, noisy: 24.6 / 33.1) |
| **Prism calls per 13-turn session** | — | **1** |

A tie on every correctness measure, at a small cost premium — and the treatment
was barely applied.

## The finding that matters

Across 13 work items, the Prism arm called Prism **once** — `prism_dead_code`,
on the final cleanup turn. It called it **zero** times on the five refactor
turns (t06–t10) it was explicitly instructed to use it for, including a
"required first parameter on every implementation" change and an "every
implementation must now audit" change. Its CLAUDE.md said *call
prism_change_impact FIRST, even if the change looks small*. It grepped instead
(15 and 5 times), or just edited from memory.

Sonnet does not reach for a code graph on code it wrote itself. That is an
adoption finding, not an accuracy finding, and it means this benchmark did not
measure what it was built to measure.

## An instrument bug I reported as a result, then corrected

Mid-run I reported that the baseline "shipped 8 silently-incomplete changes."
That was wrong, and the correction matters more than the original claim.

The oracle encodes the FINAL contract, so grading an intermediate snapshot fails
tests for reasons unrelated to the turn under measurement:

- the 3 "t07 audit misses" were t07 tests using **cent-scale amounts against a
  repo still in dollars** — t08 had not happened yet. They go to 0 when t08 lands.
- the 5 "t08 misses" were RoundPolicy tests importing `src/ledger/policies/`
  before the module **moved there at t10**. They go to 0 when t10 lands.

Both arms' RoundPolicy is semantically identical to the reference. Nobody missed
anything. The `SILENT@change=8` column in the report output is this artifact and
must not be cited.

Measuring completeness at the point of change requires a **versioned** oracle —
per-turn contract snapshots — not one final-contract suite. That is real work and
this study does not justify it.

## What three studies have now established

tickr (Python, small), tickr-large (Python, 213-site blast radius), and ledger
(TypeScript, mid-size, silent-change turns) all produced the same shape: the
baseline scores perfectly, so there is no correctness headroom, and the graph
costs 6–24% more.

The common flaw is structural and it is the design, not the tool: **all three are
greenfield.** The agent wrote every line minutes earlier and remembers it. There
is nothing to discover, which is exactly why the baseline never fails and why the
model never reaches for a graph. Prism is a tool for code you did not write.

Greenfield A/Bs cannot answer "does a code graph help." Three of them now say so.
The question needs a repo the agent has never seen — which is what the existing
`run_e2e` corpus already is.

## Reproducing

```
python3 ledger_ab.py --trials 2
python3 ledger_ab.py --report      # ignore the SILENT@chg column, see above
```

Artifacts: `~/ledger-ab/{results,snapshots}/`. Every turn is snapshotted, so
re-grading is offline and needs no agent re-runs.

## Harness bugs found and fixed while building this

1. Expected-test-count derived by regex missed loop-generated tests (184 vs the
   real 341) and scored the reference **1.85**. Now derived from a reference run.
2. `cp -r` dereferenced the `node_modules/.bin/tsc` symlink, so `tsc` failed to
   *run*; nearly scored as a type error. Now `symlinks=True`, and the grader
   distinguishes "tsc did not run" from "type errors".
3. Template lacked `@types/node`, making every `node:test` import a spurious type
   error and the compiler oracle useless.
4. The agent burned a turn asking for `npm install` approval it could not get;
   CLAUDE.md now states the toolchain is pre-installed.
5. Agents spawned subagents, which may not inherit the arm's MCP tools —
   degrading the prism arm only. Subagents now disallowed.
6. One oracle test pinned `format(-123450)` to `"$-1234.50"` when SPEC never says
   where the sign goes; loosened to accept both readings.
