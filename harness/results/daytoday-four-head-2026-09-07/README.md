# Fast day-to-day coding/search screen — 2026-09-07

## Outcome

The 32-cell screen completed in 12m31s wall time (24 read-only cells in 7m04s,
then 8 coding cells plus held-out scoring in 5m20s). Every task ran one trial
under four heads: Sonnet native, GPT-5.5 native, Sonnet with Prism available,
and GPT-5.5 with Prism available. Cells had a hard 120-second agent timeout,
four heads ran concurrently per task, and there were no quality retries.

This is a directional screen, not an inferential benchmark. The read-only task
mix is deliberately narrow: five test-coverage/call-chain searches in Flask and
one bug-localization task in Gin. The coding slice contains two real Python bug
fixes scored by held-out fail-to-pass and pass-to-pass tests.

## Read-only results

| Head | Exact | Timeouts | Median wall | Completed tokens | Prism adopted |
|---|---:|---:|---:|---:|---:|
| Sonnet native | 5/6 | 1 | 44.8s | 572,852 | — |
| Sonnet + Prism | 5/6 | 1 | 29.8s | 490,711 | 5/6 |
| GPT-5.5 native | 6/6 | 0 | 57.4s | 619,170 | — |
| GPT-5.5 + Prism | 6/6 | 0 | 63.4s | 888,568 | 1/6 |

All completed read-only answers were exact. Both Sonnet heads timed out on the
same harder `JSONTag.tag` call-chain task. For Sonnet, where Prism was actually
used on five tasks, availability preserved quality while reducing median wall
time by 14.9s (33%) and completed-token total by 82,141 (14%). For GPT-5.5,
Prism was used only once; the aggregate was 6.0s slower at the median and used
269,398 more completed tokens. Because five of six assigned GPT-5.5 Prism cells
did not invoke Prism, that row is primarily a tool-adoption result, not evidence
that Prism itself caused the aggregate difference.

## Coding results

| Head | Completed | Patch produced | Held-out resolved | Completed + resolved | Prism adopted |
|---|---:|---:|---:|---:|---:|
| Sonnet native | 1/2 | 1/2 | 0/2 | 0/2 | — |
| Sonnet + Prism | 0/2 | 1/2 | 1/2 | 0/2 | 0/2 |
| GPT-5.5 native | 1/2 | 1/2 | 1/2 | 1/2 | — |
| GPT-5.5 + Prism | 2/2 | 1/2 | 1/2 | 1/2 | 0/2 |

The Click task produced three test-passing patches: both GPT-5.5 heads and the
Sonnet+Prism head. The Sonnet+Prism process hit the 120-second cutoff after
writing its passing patch, so it is retained as `test_resolved` but not counted
as `completed_and_resolved`. Sonnet native completed but its patch failed both
the target and regression sets. No head fixed the harder Werkzeug task; one
GPT-5.5+Prism completion incorrectly concluded that the pre-existing partial fix
already solved the report.

No coding cell invoked Prism. Consequently, the coding comparison measures
assignment to a Prism-available environment, but provides no causal evidence
about Prism-assisted coding. This is the clearest actionable finding from the
screen: day-to-day coding prompts need either better automatic routing or a
separate encouraged-use treatment before patch-outcome gains can be evaluated.

## Interpretation

1. The fast protocol works operationally: 32 attempts, isolated pinned source,
   transcripts, model identity, token/tool measurements, and held-out patch
   scoring finished well under the 40-minute target.
2. Sonnet used Prism for call-chain search and became materially faster without
   losing accuracy in this small slice.
3. GPT-5.5 largely ignored Prism, and every model ignored it for coding. Those
   cells must not be presented as evidence for or against Prism's code-change
   effectiveness.
4. A broader day-to-day benchmark should rebalance the read-only slice toward
   direct lookup, usage search, and cross-file comprehension, and should add
   more coding tasks. Native baselines can be reused across Prism-only updates
   when model version, prompt, task pins, timeout, and harness are unchanged.

## Evidence

- `aggregate.json`: normalized arm summaries and limitations.
- `read-only/`: manifest, frozen tasks, per-cell prompts/transcripts/results,
  and scored summary for 24 cells.
- `code/`: manifest, frozen tasks, per-cell prompts/transcripts/diffs/results,
  and held-out scoring summary for 8 cells.
- `run_readonly.py`, `run_code.py`, `summarize.py`: exact executed harnesses and
  aggregation logic. Workspaces, indexes, and copied binaries are intentionally
  omitted; their versions are recorded and the exact executed scripts are archived.
