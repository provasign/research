# Sonnet + Prism cost isolation study

Status: production evidence audit completed in S9. S9 supersedes the earlier
production recommendations and corrects validity/quality claims in S1–S8.
The combined implementation remains local and uncommitted. No release is
approved by this study.

## Question

Can Prism reduce Sonnet's cost on ordinary coding work without cost-specific
workflow steering? Test each proposed mechanism independently, always against
a contemporaneous Sonnet-only baseline, before deciding what belongs in the
product.

The mechanisms are:

1. tool-call and test-budget language;
2. prescriptive versus neutral tool semantics;
3. compact MCP result rendering;
4. repeated-envelope/result deduplication;
5. unchanged source-range caching.

## Non-negotiable controls

- Task: `pallets__click__pr3244` during isolation, followed by confirmation on
  the day-to-day suite for any candidate selected for adoption.
- Model: `claude-sonnet-5`, medium effort.
- Runner, task archive, prompt, timeout, CLI version, and held-out grader remain
  fixed within every comparison.
- Every Prism observation is paired with a fresh `sonnet_native` cell. A Prism
  cost is never reported without the paired native cost and delta.
- One mechanism changes at a time. Experimental binaries are local and
  identified by SHA-256; none are committed, pushed, tagged, or released.
- Cell order is rotated. A minimum of three valid paired trials is required for
  an isolation conclusion. Timeouts and invalid patches remain in the record.
- Every patch is scored against all 28 held-out Click tests. Cost reduction is
  unacceptable if task success regresses.

## Measurements

Primary measurement: paired cost delta
`(prism_cost - native_cost) / native_cost`.

Secondary measurements: resolved rate, turns, total tool calls, Prism calls,
input/cache-write/cache-read/output tokens, wall time, first repository action,
MCP result bytes, duplicate discovery calls, duplicate reads, test invocations,
and patch revision count.

### Beyond-oracle value review

Cost and held-out pass rate do not establish whether an agent's extra work is
useful. Each completed patch is also reviewed against behavior not asserted by
the benchmark oracle:

- child-process output is captured in both `Result.stderr` and the interleaved
  `Result.output`;
- ordering across Python writes and descriptor writes is preserved;
- the temporary descriptor is lazy where practical and is always closed;
- the existing file-like API and typing remain compatible;
- extra tests or revisions correspond to a real defect rather than churn.

This review is reported separately. It cannot rescue an oracle failure, but it
can distinguish a more expensive, materially stronger patch from wandering.

For each study, report all trials plus median paired delta. Do not substitute a
historical singleton for the paired baseline. Historical runs may be shown only
as context.

## Variants

### S1 — Tool-call/test quota

- Control: adoption/routing text with no numerical call cap, test cap, forced
  stop, or patch-polish language.
- Treatment: identical text plus the v0.72.4 local-fix quota language.
- Everything else, including tool descriptions and mechanical optimizations,
  is identical.

This isolates whether the quota itself reduces cost or distorts behavior.

### S2 — Tool semantics

- Control: factual descriptions that explain the output and accepted use case
  of each tool.
- Treatment: prescriptive v0.72.4 descriptions such as query-first,
  continuation-only, and locator-only.
- Neither arm contains numerical tool/test budgets or forced-stop language.

This isolates routing semantics from the quota.

### S3 — Compact result payloads

- Control: structurally equivalent JSON MCP results.
- Treatment: compact text renderers.
- Neutral tool semantics, no quota, and all other mechanical features enabled.

Verify content parity for each result shape before running the model cells.

### S4 — Deduplication

- Control: repeated fixed envelopes and identical long notes are returned in
  full.
- Treatment: the current once-per-session short forms/pointers are enabled.
- Neutral tool semantics, no quota, compact rendering, and range caching remain
  enabled.

Record whether a trial actually exercises the mechanism. A trial with no
repeatable result is valid for end-to-end cost but supplies no causal evidence
about deduplication.

### S5 — Unchanged source-range caching

- Control: a repeated `prism_read` returns the source again.
- Treatment: a fully covered, unchanged range returns the compact cached
  pointer.
- Neutral tool semantics, no quota, compact rendering, and envelope
  deduplication remain enabled.

Record whether a trial actually requests a cache-eligible repeated range. As
with S4, no exercised mechanism means no causal result.

## Decision rule

After all five isolation studies:

- Keep a mechanism only if it has a measurable exercised effect, preserves
  held-out success, and improves median paired cost by at least 10% without a
  material tail-cost regression.
- Treat purely instructional improvements separately from mechanical savings.
- If results are mixed or dominated by model variance, do not ship the change;
  expand trials or the task set first.
- A quality regression or repeated treatment timeouts may reject a mechanism
  early, but cannot establish a benefit. This safety-stop clarification was
  added after S1 produced an adverse sequential trial; it was not a
  preregistered efficacy rule.
- Confirm the selected combination on the complete day-to-day suite, again
  paired with Sonnet-only, before committing product code.

## Preliminary observations — not independent-study evidence

These runs motivated the protocol but changed multiple variables or lacked a
contemporaneous matched control, so they cannot decide any mechanism.

| Configuration | Cost | Turns | Calls | Prism calls | Held-out |
|---|---:|---:|---:|---:|---:|
| Historical Sonnet-only singleton | $0.1940 | 10 | 9 | 0 | passed |
| Fresh same-day Sonnet-only singleton | $0.5235 | 20 | 19 | 0 | 28/28 |
| Prism v0.72.3 trial 1 | $0.5472 | 30 | 29 | 8 | 28/28 |
| Prism v0.72.3 trial 2 | $0.6388 | 33 | 32 | 3 | 28/28 |
| Prism v0.72.4 released guidance | $0.3026 | 14 | 13 | 1 | 28/28 |
| Local neutral-guidance experiment | $0.4399 | 28 | 27 | 1 | 28/28 |

The neutral experiment selected `prism_search`, then repeated discovery with
native Grep and entered a longer edit/test loop. That is useful diagnostic
evidence, but one stochastic run cannot establish the effect of semantics.

An added adversarial check writes `before`, launches a child whose stdout is
redirected to Click's captured stderr, then writes `after`. The expected value
of both `Result.stderr` and mixed `Result.output` is
`before\nchild\nafter\n`. Across the 34 S1–S3 patches reviewed so far, no patch
preserved the child bytes and ordering in both views. Some more expensive Prism
patches added lazy allocation, explicit close handling, or more documentation,
but still dropped the child bytes from mixed output. Thus the work was
occasionally more thorough in one dimension, but is not yet demonstrably
better end to end.

## Run ledger

### S1 — Tool-call/test quota

Control binary (neutral semantics, no quota):
`bca2c608ae8b63c90eee92556d8d6d933807e687a1e35d97934917b4c7015005`.

Treatment binary (same code and semantics, quota text only):
`335baceb673630575187785fa5a9b49e4f87e0d148152a69f79af9a183545066`.

| Arm | Trial | Native cost | Prism cost | Paired delta | Prism calls | Native result | Prism result | Note |
|---|---:|---:|---:|---:|---:|---|---|---|
| no quota | 1 | $0.4628 | $0.5049 | +9.1% | 1 | 28/28 | 28/28 | valid pair |
| no quota | 2 | $0.2579 | $0.2659 | +3.1% | 1 | 28/28 | 28/28 | valid pair |
| no quota | 3 | $0.2043 | — | — | 2 | 28/28 | 28/28 | Prism timed out; run overlapped another pair |
| no quota | 4 | $0.4822 | $0.2949 | -38.8% | 0 | 28/28 | 28/28 | valid pair; Prism was not adopted |
| quota | 1 | $0.4320 | $0.4473 | +3.5% | 1 | 28/28 | 28/28 | valid pair |
| quota | 2 | $0.3934 | — | — | 1 | 28/28 | 28/28 | Prism timed out; run overlapped another pair |
| quota | 3 | — | $0.4467 | — | 1 | 28/28 | 28/28 | native timed out; run overlapped another pair |
| quota | 4 | $0.4159 | — | — | 3 | 28/28 | failed | Prism timed out in a sequential pair |

The no-quota arm's median valid paired delta is +3.1%, although one of its
three valid nominal Prism cells made zero Prism calls. The quota arm has only
one valid pair, two Prism timeouts, and one held-out failure. Because the
sequential fourth trial shows a quality and tail-latency regression, S1 is
stopped for harm rather than repeatedly sampling for surviving rows.

S1 decision: do not ship numerical tool/test quotas or forced-stop language.
This is a risk rejection, not evidence that removing the quota reduces median
cost.

### S2 — Tool semantics

Neutral control binary (also used by S1 no-quota):
`bca2c608ae8b63c90eee92556d8d6d933807e687a1e35d97934917b4c7015005`.

Prescriptive treatment binary (v0.72.4 query-first semantics, no quota):
`4179b0142850739b89cb37e363ce5aebb7991baf605061a6d6bef4d8fc04a224`.

The three valid S1 no-quota pairs are the common neutral control. Each S2
treatment observation has its own fresh native baseline.

| Semantics | Trial | Native cost | Prism cost | Paired delta | Prism calls | Native result | Prism result |
|---|---:|---:|---:|---:|---:|---|---|
| neutral | 1 | $0.4628 | $0.5049 | +9.1% | 1 | 28/28 | 28/28 |
| neutral | 2 | $0.2579 | $0.2659 | +3.1% | 1 | 28/28 | 28/28 |
| neutral | 3 | $0.4822 | $0.2949 | -38.8% | 0 | 28/28 | 28/28 |
| prescriptive | 1 | $0.2721 | $0.3450 | +26.8% | 1 | 28/28 | 28/28 |
| prescriptive | 2 | $0.3429 | $0.5451 | +59.0% | 5 | 28/28 | 28/28 |
| prescriptive | 3 | $0.2486 | $0.8581 | +245.2% | 1 | 28/28 | 28/28 |

Median paired delta is +3.1% for neutral semantics and +59.0% for
prescriptive semantics. The neutral median includes a nominal Prism cell that
did not adopt Prism; this is an adoption weakness, not grounds to discard the
row. Prescriptive query-first routing preserved task success but substantially
increased median and tail cost on this task.

S2 decision: prefer factual, non-prescriptive tool semantics. Address adoption
separately rather than forcing a specific discovery trajectory.

### S3 — Compact result payloads

Switchable neutral-semantics binary:
`7c2bd9a66f02e356c2e4d7910f8da3a23cea43824197bc43ac4687c3d245124e`.
The binary emits compact text normally and structurally equivalent JSON when
`PRISM_JSON_RESULTS=1`; no other runtime behavior changes.

| Rendering | Trial | Native cost | Prism cost | Paired delta | Prism calls | Native result | Prism result | Note |
|---|---:|---:|---:|---:|---:|---|---|---|
| JSON | 1 | — | $0.4137 | — | 1 | 28/28 | 28/28 | native timed out |
| JSON | 2 | $0.4972 | $0.4502 | -9.4% | 1 | 28/28 | 28/28 | valid pair |
| JSON | 3 | $0.3338 | $0.5783 | +73.2% | 4 | 28/28 | 28/28 | valid pair |
| JSON | 4 | $0.6884 | $0.4410 | -35.9% | 2 | 28/28 | 28/28 | valid pair |
| compact | 1 | $0.1978 | $0.2900 | +46.6% | 4 | 28/28 | 28/28 | valid pair |
| compact | 2 | $0.3692 | $0.4639 | +25.7% | 1 | 28/28 | 28/28 | valid pair |
| compact | 3 | $0.1676 | $0.4690 | +179.8% | 2 | 28/28 | 28/28 | valid pair |

Median paired delta is -9.4% for JSON and +46.6% for compact rendering. The
result is contrary to the byte-level hypothesis. Tool trajectories diverged
substantially: one JSON run made four Prism calls totaling about 37 KB, while
compact runs made between one and four different calls. Thus compact rendering
did not reduce end-to-end cost in this sample, but the model runs do not isolate
the token effect from trajectory variance.

Deterministic MCP replay against the same unmodified Click tree produced:

| Result shape | Compact bytes | JSON bytes | Compact delta |
|---|---:|---:|---:|
| no-match search | 508 | 475 | +6.9% |
| matching search with context | 1,545 | 2,515 | -38.6% |
| edit-ready query | 32,367 | 34,804 | -7.0% |
| symbol lookup | 496 | 1,768 | -71.9% |

Compact rendering mechanically reduces matching, query, and lookup payloads,
but slightly enlarges the no-match search envelope. The Click agent trials do
not show an end-to-end cost benefit and in fact favor JSON at the median.

S3 decision: mechanical payload reduction is real, but end-to-end value is
inconclusive. Do not make a new product decision from Click alone; carry both
rendering modes into the broader confirmation if another mechanism produces a
candidate.

### S4 — Deduplication

Switchable neutral-semantics binary:
`ea0c5e25340991342a8f8982d6fcf81530bb8879fc4419173f1471122638f8bb`.
Deduplication is enabled normally and disabled with
`PRISM_NO_ONCE_DEDUP=1`. The S3 compact trials are the common dedup-on
control; every dedup-off treatment has its own native baseline.

| Dedup | Trial | Native cost | Prism cost | Paired delta | Prism calls | Native result | Prism result | Exercised? |
|---|---:|---:|---:|---:|---:|---|---|---|
| on | 1 | $0.1978 | $0.2900 | +46.6% | 4 | 28/28 | 28/28 | yes |
| on | 2 | $0.3692 | $0.4639 | +25.7% | 1 | 28/28 | 28/28 | no |
| on | 3 | $0.1676 | $0.4690 | +179.8% | 2 | 28/28 | 28/28 | no; search + verify |
| off | 1 | $0.3066 | $0.5487 | +79.0% | 1 | 28/28 | 28/28 | no |
| off | 2 | $0.5141 | $0.2838 | -44.8% | 1 | 28/28 | 28/28 | no |
| off | 3 | $0.2754 | $0.2992 | +8.7% | 3 | 28/28 | yes |

Median paired delta is +46.6% with dedup on and +8.7% with dedup off, but
four of the six rows never exercised the mechanism and the two exercised rows
followed different trajectories. The end-to-end comparison therefore cannot
attribute its median difference to deduplication.

Deterministic repeat-call replay produced:

| Repeated search shape | First bytes | Second, dedup on | Second, dedup off | Second-call reduction |
|---|---:|---:|---:|---:|
| matching search | 1,545 | 1,187 | 1,545 | 23.2% |
| no-match search | 508 | 467 | 508 | 8.1% |
| broad search | 4,477 | 4,275 | 4,477 | 4.5% |

S4 decision: retain repeat-note deduplication. It removes only boilerplate
already delivered in the same session, deterministically reduces exercised
payloads, and showed no held-out regression. Do not claim an end-to-end Click
cost reduction from it.

### S5 — Unchanged source-range caching

Switchable neutral-semantics binary:
`f7f97dbc78a8955484cfdfcbdc66bfccf46aac84697a5660dee50039f210387a`.
Caching is enabled normally and disabled with `PRISM_NO_RANGE_CACHE=1`. The S3
compact trials are the common cache-on control; every cache-off treatment has
its own native baseline.

| Cache | Trial | Native cost | Prism cost | Paired delta | Prism calls | Native result | Prism result | Exercised? |
|---|---:|---:|---:|---:|---:|---|---|---|
| on | 1 | $0.1978 | $0.2900 | +46.6% | 4 | 28/28 | 28/28 | no |
| on | 2 | $0.3692 | $0.4639 | +25.7% | 1 | 28/28 | 28/28 | no |
| on | 3 | $0.1676 | $0.4690 | +179.8% | 2 | 28/28 | 28/28 | no |
| off | 1 | $0.3496 | $0.5612 | +60.5% | 1 | 28/28 | 28/28 | no |
| off | 2 | — | $0.1819 | — | 3 | 28/28 | 28/28 | no; native timed out |
| off | 3 | — | $0.6918 | — | 1 | 28/28 | failed | no; native timed out |

No Click agent cell requested a fully covered unchanged range, so none can
measure the cache's causal end-to-end effect. Cache-off also produced one
held-out failure, but because the mechanism was not exercised that failure is
trajectory evidence rather than a cache correctness finding.

Deterministic repeat-call replay produced:

| Repeated range | First bytes | Second, cache on | Second, cache off | Second-call reduction |
|---|---:|---:|---:|---:|
| 20 lines | 626 | 130 | 626 | 79.2% |
| 70 lines | 2,080 | 132 | 2,080 | 93.7% |
| 150 lines | 4,337 | 130 | 4,337 | 97.0% |

S5 decision: retain unchanged-range caching. It is hash-gated, preserves a
pointer to source already present in the same context, and deterministically
eliminates nearly all repeated payload when exercised. Do not claim a Click
cost reduction because Click did not naturally activate it.

## Final decision

### Two-task confirmation

Both candidate renderings used neutral semantics, no quota, deduplication on,
and range caching on. Each task had a fresh Sonnet-only peer.

| Rendering | Task | Native cost | Prism cost | Paired delta | Native result | Prism result |
|---|---|---:|---:|---:|---|---|
| compact | Click | $0.3057 | $0.5466 | +78.8% | 28/28 | 28/28 |
| JSON | Click | $0.4635 | $0.3986 | -14.0% | 28/28 | 28/28 |
| compact | urllib3 | — | $0.4384 | — | failed, timeout | failed |
| JSON | urllib3 | — | $0.6935 | — | failed, timeout | failed |

The urllib3 task cannot rank cost because both native baselines timed out and
all four patches failed the fail-to-pass tests. On Click, JSON beat its native
peer while compact was substantially more expensive. Combining isolation and
confirmation gives four valid Click deltas per rendering: JSON has a median of
about -11.7%; compact has a median of about +62.7%.

The beyond-oracle capture check found the same behavior in all four Click
confirmation patches: child output appeared correctly in `Result.stderr` but
was absent from mixed `Result.output`. The more expensive compact Prism patch
was therefore not observably better than either native or JSON Prism on this
dimension.

### Recommended direction

1. Remove the numerical tool-call/test quota, forced-stop language, and
   patch-polish instructions. S1 showed adverse timeout/quality tail behavior.
2. Use factual, non-prescriptive descriptions. Keep only the high-level
   requirement that first repository discovery use Prism; let the model choose
   search, query, lookup, or impact by need. S2 strongly rejected forced
   query-first routing.
3. Restore JSON as the default MCP result representation for now. Compact text
   is mechanically smaller for useful results, but it lost decisively on
   end-to-end paired Click cost across four observations and showed no quality
   advantage. Keep compact rendering available for further study rather than
   claiming it as a cost optimization.
4. Retain hash-gated unchanged-range caching. Its end-to-end effect was not
   activated naturally, but exercised replay reduced repeated payload by
   79–97% without discarding source that was not already present.
5. Retain repeat-note deduplication only for any optional compact-text path. It
   reduced exercised repeated envelopes by 4–23%, but it is not an
   end-to-end Click cost win and is irrelevant to default JSON output.

This recommendation is deliberately narrower than the original proposal:
mechanically smaller payloads are not assumed to produce cheaper agent
trajectories. The measured agent outcome, paired with native every time, takes
priority.

## S6 — Combined conclusion candidate

Status: completed locally; no code committed or released.

Local, uncommitted candidate binary:
`32f5004d4718d3cb6fbb39a73a5b65496436acddca8396142e68215b37316052`.
It combines the five decisions above: neutral tool semantics without a
workflow quota, structured JSON by default, optional compact text via
`PRISM_TEXT_RESULTS=1`, repeat-note deduplication on that optional text path,
and hash-gated unchanged-range caching.

Protocol: run three fresh paired Sonnet trials on the Click task, with one
native and one Prism cell in every trial and rotating launch order. Neither arm
receives cost-specific steering. Record held-out result, cost, Prism adoption,
and whether the patch does useful work beyond the oracle. If all three paired
cells are valid, use the median paired cost delta as the primary cost result.
Then run one paired Click + urllib3 confirmation to check whether the conclusion
survives a second task; a task with a timed-out or failed native baseline is
reported but excluded from paired cost ranking.

Acceptance rule: retain the combined direction only if it introduces no
held-out regression, its median valid paired Click delta is no worse than
+10%, and any extra agent work is useful rather than merely additional. The
earlier S1–S5 and confirmation runs motivated this candidate but are not
counted as S6 observations.

### S6 results

| Trial | Native cost | Prism cost | Paired delta | Native turns/tools | Prism turns/tools/calls | Native result | Prism result |
|---:|---:|---:|---:|---:|---:|---|---|
| Click 1 | $0.3751 | $0.6153 | +64.0% | 28/27 | 33/32/3 | 28/28 | 28/28 |
| Click 2 | $0.4498 | $0.3860 | -14.2% | 23/22 | 26/25/1 | 28/28 | 28/28 |
| Click 3 | $0.4821 | $0.5245 | +8.8% | 30/29 | 33/32/2 | 28/28 | 28/28 |

The preregistered primary median is **+8.8%**. It meets the +10% ceiling and
introduces no held-out regression, but the range from -14.2% to +64.0% is too
wide to call a cost improvement. In all three trials the Prism arm took three
to five more turns/tool calls. The extra activity did not produce a stronger
beyond-oracle result.

| Confirmation task | Native cost | Prism cost | Paired delta | Native turns/tools | Prism turns/tools/calls | Native result | Prism result |
|---|---:|---:|---:|---:|---:|---|---|
| Click | $0.4547 | $0.2859 | -37.1% | 33/32 | 17/16/1 | 28/28 | 28/28 |
| urllib3 | $0.6057 | $0.4426 | not attributable | 35/34 | 27/26/0 | failed | failed |

The Click confirmation shows that the candidate can also shorten a trajectory;
it used one Prism call and roughly half as many turns. Across all four valid
paired Click observations the median delta is about **-2.7%**, but this pooled
number is descriptive rather than the preregistered primary statistic.

The urllib3 row does not measure Prism: the nominal Prism arm made zero Prism
calls, and both patches failed the fail-to-pass tests. Its cost difference is
therefore excluded from attribution and cost ranking. This is independent
evidence that neutral semantics do not guarantee adoption on every task.

The adversarial child-process capture check failed in all eight Click patches:
none included `before\nchild\nafter\n` in mixed `Result.output`. Five patches
had the correct value in `Result.stderr`; one native patch reordered the child
line, one Prism patch omitted the initial line, and another Prism patch omitted
the child line. The more expensive Prism trajectories were not observably
better beyond the oracle.

### S6 decision

Keep the combined implementation as the preferred design candidate, but do not
claim that it reduces Sonnet cost and do not release it from this evidence
alone. The study supports removing the quota and prescriptive routing, keeping
JSON as the default, and retaining the two mechanical reuse optimizations. It
does not show that additional Prism-driven work is useful, and it exposes an
adoption gap on urllib3. A release decision should require a broader task set
or a targeted adoption study rather than more repeated Click runs.

## S7 — Click launch-order study

Status: aborted after trial 1 because the audit found shared-state and
concurrent-resource confounds.

Question: does launching the Prism arm first cause the apparent saving?
Run four new paired Click trials sequentially, alternating launch order:
Prism/native, native/Prism, Prism/native, native/Prism. Each pair uses the
same frozen S6 binary and a fresh Sonnet-only baseline. Trials are not run in
parallel with other trials, although the two arms inside each pair retain the
harness's normal concurrent execution.

Primary comparison: median paired cost delta for the two Prism-first trials
versus the two native-first trials. Also report held-out success, turns, tool
calls, Prism calls, and the actual order logged by the harness. With only two
observations per group this can identify a large operational artifact, not
establish a general causal effect. Do not pool earlier S6 observations into the
primary S7 comparison.

Trial 1 logged Prism first. Prism completed at $0.3764 with one Prism call and
passed 28/28; native produced a passing patch but timed out before reporting
usage, so there is no paired cost delta. The harness inherited `HOME` and the
full environment except `CLAUDECODE`, and both arms ran concurrently under the
same Claude account. Although memory, settings sources, hooks, plugins, Chrome,
and session persistence were disabled, this does not isolate global Claude
storage or concurrent account/runtime capacity. S7 is therefore not continued.

First-message token accounting was stable across the preceding repeated runs:
native consistently read 5,454 cached tokens and Prism 8,990, with nearly
identical cache-creation sizes within each arm. There is no observed special
prompt-cache discount for the arm launched first, but the concurrent runtime
confound remains.

## S8 — Sequential Click launch-order study

Status: completed but underpowered; two of four attempted pairs were valid.

Run four fresh pairs with only one Claude process active at a time. Alternate
the sequence Prism/native, native/Prism, Prism/native, native/Prism. Each cell
gets a fresh worktree and no session persistence; the same frozen S6 binary is
used. This removes within-pair laptop and account concurrency. It does not
claim complete credential/cache isolation because an empty
`CLAUDE_CONFIG_DIR` is unauthenticated on this installation.

Primary comparison: paired cost deltas grouped by which arm ran first. Report
timeouts, held-out results, turns/tool calls, Prism adoption, first-message
cache accounting, and both group medians. Exclude any pair with incomplete
usage or a held-out failure from cost ranking. Earlier S6/S7 cells are not part
of the primary S8 comparison.

### S8 results

| Pair | Sequence | Native cost | Prism cost | Paired delta | Native result | Prism result | Prism calls |
|---:|---|---:|---:|---:|---|---|---:|
| 1 | Prism then native | $0.3114 | $0.4759 | +52.8% | 28/28 | 28/28 | 1 |
| 2 | native then Prism | $0.5099 | $0.5690 | +11.6% | 28/28 | 28/28 | 1 |
| 3 | Prism then native | — | $0.6465 | excluded | interrupted by quota; patch failed | 28/28 | 4 |
| 4 | native then Prism | — | not run | excluded | passing patch, usage timeout | — | — |

Pair 4's first attempt was rejected before inference because the shared Claude
account reached 100% of its five-hour session limit. It emitted zero tokens and
explicitly reported a rate-limit reset at 11:30 AM. A fresh native rerun after
the reset produced a patch that passed 28/28, but the five-minute process limit
killed Claude before its result event, leaving no complete usage or cost. The
Prism peer was not run because it could not form a valid cost pair.

The two valid pairs contradict the proposed launch-order saving: Prism cost
52.8% more when run first and 11.6% more when run second. There is only one
valid observation in each sequence group, so no group median or causal order
effect can be estimated.

Adoption quality also varied. Pair 1 made a narrow search for
`_NamedTextIOWrapper`, then used native Reads and Greps to discover the actual
`BytesIOCopy`/`StreamMixer` behavior; this was a legitimate locator but an
undersized and largely ornamental Prism use. Pair 2 batched three relevant
search terms but still used only a locator. Pair 3 used two searches, a whole
body lookup for `CliRunner.isolation`, and final verification; that was the
only clearly substantive multi-stage Prism workflow, and it was also the most
expensive Prism cell.

A separately supplied screenshot came from Prism v0.72.4 running on another
laptop. Its agent reported substantive impact, lookup, batched-search, and
verification use and retrospectively estimated a 20–40k token saving. This is
useful qualitative evidence for what good Prism adoption looks like, but it is
not an S8 observation or a measured counterfactual. No link between that
machine's session and this laptop's quota exists: it used a different Claude
account as well as a different laptop.

### S8 decision

There is no evidence that launching the Prism arm first causes savings. The
earlier concurrent pattern was confounded by simultaneous sessions, and the
sequential valid pairs both made Prism more expensive. Separately, the audit
proved that this benchmark's Claude sessions draw from a shared account quota;
it did not establish cross-device contribution. The existing flags suppress
memory, persisted sessions, hooks, plugins, settings sources, and Chrome, while
first-message prompt-cache accounting remained stable by arm; no special
first-launch cache discount was observed. Future cost studies should run one
Claude cell at a time, record rate-limit events, require complete usage, and
reserve a clean quota window.

## S9 — Production evidence audit (supersedes earlier recommendations)

This is a code and transcript audit with deterministic response replay. No new
paid model trials were launched. It covers every current uncommitted Prism
change and rechecks the prior evidence rather than treating historical
conclusions as established facts.

### 1. The large format headline depends heavily on different native baselines

Recomputed from the original measurement files for the four previously valid
Click pairs per format (S3 plus its first confirmation):

| Cohort | Median native session cost | Median Prism session cost | Median paired delta |
|---|---:|---:|---:|
| JSON | $0.4803 | $0.4456 | -11.72% |
| Compact | $0.2518 | $0.4664 | +62.70% |

The raw Prism medians differ by about 4.5%, while the native medians differ by
about 91%. Neither comparison alone estimates a causal format effect: these
are different trajectories, run blocks, and native controls. The paired
percentages were calculated correctly, but describing them as a decisive JSON
victory overstated the evidence. Repeating one task does not establish
cross-task generalization. These historical validity labels also need the
protocol corrections below.

Actual MCP responses confirm that format switching did take effect: the eight
calls in the four selected JSON cells were JSON, and all nine calls in the four
compact cells were text. However, neither group invoked `prism_query` or
`prism_change_impact`. JSON exercised four searches, three lookups, and one
verification; compact exercised five searches, two reads, and two
verifications. The study did not exercise equivalent tool mixes, and cannot
support a global default change for every tool.

### 2. Serialization, content projection, and guidance were mixed together

Both formats are delivered through MCP `content` entries with `type="text"`.
The JSON arm serializes the handler object into that text string; it does not
introduce a separate structured-content protocol or schema-aware client path.

`renderOneSearchText` adds locator/source-reuse guidance not present as those
same fields in the JSON object, truncates signatures above 100 bytes, and
projects symbol records to selected fields. `renderLookupAsText` projects the
symbol envelope and retains the main source body, while raw JSON can contain
the body in both `content` and symbol metadata. Therefore the switch changes
content selection and instructions as well as syntax. The hypothesis that
Sonnet simply understands JSON punctuation better is unproven.

Two reproducible probes verify these differences: a 100-plus-byte signature
is shortened in compact search and retained in JSON; an unknown top-level
field triggers JSON fallback, while an unknown nested symbol field is omitted
by the text projection. The latter is a boundary of the fallback guarantee,
not proof that a particular omitted field is required by today's contract.

Replaying eight captured S3 JSON responses through the current text renderers
with the same underlying result object produced these examples:

| Captured response | JSON bytes | Text bytes | Change |
|---|---:|---:|---:|
| no-match search, S3 JSON t2 | 477 | 510 | +6.9% |
| CliRunner search, S3 JSON t3 | 1,589 | 662 | -58.3% |
| CliRunner.isolation lookup | 17,635 | 7,604 | -56.9% |
| batched lookup | 13,834 | 5,395 | -61.0% |
| BytesIOCopy lookup | 1,768 | 496 | -71.9% |
| verify, S3 JSON t4 | 222 | 103 | -53.6% |

Replay verified preservation of nonempty top-level source content in the
lookup cases. It does not establish full semantic parity of every nested field
or client behavior. Measurements are UTF-8 byte counts, not tokenizer counts
or session-cost estimates. Replay does not reuse previous session dedup state.

### 3. Benchmark validity and attribution corrections

- The prompt contains "Make the smallest robust change", forbids test/doc
  modifications, and instructs a narrow test if time permits within five
  minutes. These constraints are identical between the arms, so they do not
  alone explain the format difference, but the studies were not free of
  workflow steering. They also prevent studying the full range of beneficial
  extra work shown in the independent laptop screenshot.
- The neutral candidate still has "go straight to the edit" in
  `Handler.deliverSource`, plus mandatory first-discovery/impact/verification
  requirements in other instruction surfaces. S2 changed selected descriptions,
  not all prescriptive guidance. None of the selected format trials exercised
  the query instruction path.
- The saved Click grader has one fail-to-pass test,
  `test_faulthandler_enable`, and 27 pass-to-pass tests. The added target test is
  absent from the inspected base test file; existing regression tests are
  naturally visible to agents. "28 held-out tests" was imprecise: there are
  28 selected grader checks, not 28 newly hidden task requirements.
- The task's saved reference patch explicitly documents that descriptor-level
  writes may go to the original terminal without being captured. Our mixed
  output capture probe asks for an additional capability. Failure on it is not
  by itself a failure to meet the requested fix. Capturing such output
  inconsistently can still reveal a defect in an agent's chosen extension, but
  task correctness and optional improvements must be scored separately.
- The harness marked cells valid even when tool commands attempted external
  package downloads. Concrete examples: S3 compact t2 native downloaded/read
  another Click package under `/tmp/clickdl`; S3 compact t3 Prism attempted
  `pip download click==8.2.1`; S3 JSON t4 Prism attempted `pip download click`.
  S1/S4 also contain such attempts. These violate the stated repository/network
  restrictions and need protocol-invalid labels independent of grader success.
  Whether an individual download used a package cache or the network does not
  establish clean source isolation.
  Transcript result inspection confirms that the compact t2 native cell used
  a cached Click 8.5.0 wheel, extracted it, and read its newer `testing.py`
  implementation. This is actual external-source exposure through laptop
  package storage, not merely a speculative network or Claude-memory effect.
- Concurrent peers in S3 compact t1, S3 compact t3, S3 JSON t2, and JSON
  confirmation used overlapping absolute `/tmp/sscce.py` or
  `/tmp/test_sscce.py` paths. This is an observed isolation gap with possible
  file interference; exact overwrites and their causal effects were not proved.
  A fresh working directory or TMPDIR alone cannot isolate hard-coded `/tmp`.
- S8 pair 3 native ended in HTTP 429 with `terminal_reason=api_error` after
  quota utilization reached 100%. The previous description as pure model
  variance was incorrect. Pair 4 also hit the quota; the post-reset native
  rerun then timed out. The observations do not establish an order effect.
- The first observed cache-read counts were stable by arm. That does not prove
  absence of every server/local cache effect. The screenshot session used a
  separate laptop and Claude account and supplies no evidence of local
  interference with this study.
- S6 relaxed its local acceptance rule to a +10% cost ceiling, whereas the
  original study rule required at least 10% improvement without tail harm.
  Meeting the relaxed rule cannot establish the original production gate.

### 4. Disposition of every unreleased product change

| Change / files | Production recommendation | Evidence and remaining requirement |
|---|---|---|
| Numerical quota and forced stop removed in server.go | Prefer a narrowly scoped removal candidate | They can stop necessary work independent of task size. Existing trials do not cleanly prove a cost or quality benefit; test separately from routing and format. Rename localFixBudgetGuidance if it becomes solely source-reuse guidance. |
| Neutral server instructions and query/read/search/lookup descriptions in server.go/tools.go | Keep experimental; separate from quota removal | Ornamental first-call adoption and native rediscovery remain. Instructions in source payloads and generated CLAUDE.md must be included in the audit. |
| JSON default plus PRISM_TEXT_RESULTS in server.go | Do not ship this default flip from current evidence | Keep the released compact default pending equivalent-content trials. Both runtime paths remain experimental candidates. Any nonempty value, including "0", currently enables text. The comment claiming better reliability exceeds the evidence. |
| Locator note rewrite in searchtext.go | Test as a guidance change | This affects only rendered search results and is itself a format-comparison confound. Require the same guidance in both format arms when isolating syntax. |
| Updated dedup keys in oncenotes.go | Keep aligned with whichever final wording is selected | Dedup already exists in released code; these edits update message matching, not its algorithm. The historical comment should not retroactively replace the old measured message with new wording. |
| Instruction/format assertions in coverage_test.go | Revise before shipping the selected behavior | Test fails when PRISM_TEXT_RESULTS=1 is inherited because it does not clear it before asserting the default. Prefix checks alone do not establish JSON validity or content parity. |
| Wording assertions in oncenotes_test.go | Keep only with corresponding chosen wording | They verify repeated-note behavior, not session-cost benefit. |
| Range caching | No new product change to release | readRange and its hash/range bookkeeping are unchanged from HEAD after removing experiment switches. Retain existing behavior, but a hash proves unchanged source, not that the client retained it after context compaction. |

Product worktree remains the original six modified files (62 insertions,
53 deletions). This audit did not alter those edits. The research repository's
pre-existing `harness/mason_bench.py` diff remains unrelated and untouched.

### 5. Evidence needed to choose a production format

First establish a shared semantic result contract: same source, full required
signatures, paths, identity/ambiguity, completeness/omission facts, freshness,
and recovery pointers in each format. Make any optional guidance identical.
Separate serialization from projection by comparing full JSON, projected JSON,
and compact text generated from that same projected object. This can show
whether removing duplicate metadata matters more than JSON syntax.

Use deterministic fixtures for matches/no matches, batched and ambiguous
lookup, partial/exhaustive search, impact closure, modified files, repeated
ranges, and context reset. Verify unknown-field policy at nested as well as
top-level boundaries. Byte savings alone are not acceptance evidence.

Then run a predeclared initial block of three task classes (local bug,
multi-file signature change, and unfamiliar-code investigation), with two
repetitions each and four arms: Sonnet-only, full JSON, projected JSON, and
compact text. That is 24 cells. Balance the order of the four arms across
blocks, execute sequentially in isolated filesystem environments, and pin the
same model, binary, prompt, dependencies, and source snapshots. Keep guidance,
deduplication, and range caching fixed for this format block. A later block
can test guidance with representation fixed; do not change both together.

Before paid execution, the harness needs environment enforcement that blocks
external source/package access and cross-cell `/tmp` access, per-cell Claude
configuration with an explicit authentication strategy, rate-limit/error
classification, complete usage capture, and a manifest recording every switch
and binary/source hash. Do not extract/copy credentials implicitly. Label
incomplete and protocol-invalid cells; preserve their costs and partial patches
without counting them as successful cheap solutions. Always retain the native
baseline, and compare Prism formats directly within each task/repetition too.

Judge task correctness and regressions first, then session cost, completion
time, native rediscovery, evidence coverage, and optional quality gains. Record
both response bytes and model-reported cache/write/read/output usage. A small
block is a screening study; do not promote a format from a single pooled median
or repeatedly sample until it wins. A broad default change needs replication
across tasks and no meaningful correctness/completeness loss. Windows and other
release checks must run on the actual final candidate; prior v0.72.4 CI does
not validate these uncommitted changes.

Current release judgment: compact remains the prudent default. Quota removal
is the strongest independent design candidate. A broad neutral-routing rewrite
and JSON default flip remain unproven. The next implementation should repair
the experimental controls and establish equivalent payloads before another
paid comparison.

### Reproduction

`audit_evidence.py` reads saved measurements/transcripts and emits the format
cohorts, actual response formats/tool mixes, usage, rate events, external-package
commands, and temporary paths. Run it with Python 3 from any directory.

`format_audit_test.go` is a research-only probe injected into the MCP package
by `format-audit-overlay.json`; it does not add a product file. From the Prism
repository, set PRISM_AUDIT_ROOT to this study directory and run
`GOWORK=off go test -overlay <study>/format-audit-overlay.json ./internal/mcp -run '^TestStudy' -count=1 -v`.
Both deterministic probes passed and replayed eight captured result objects.
The deliberate compatibility check
`PRISM_TEXT_RESULTS=1 GOWORK=off go test ./internal/mcp -run '^TestDispatch_ToolsCall_OK$' -count=1`
fails at the new default-JSON assertion, documenting the inherited-environment
test defect. No production bug fix, commit, push, or release was performed by S9.

## S10 — Full-fidelity compact text prototype (2026-09-08)

### Question

Can text preserve every value exposed by JSON and still reduce the response
envelope, separating serialization savings from the much larger savings caused
by the existing task-specific projections?

### Experimental implementation

An uncommitted `PRISM_TEXT_RESULTS=full` mode was added locally. It first
round-trips the tool result through `encoding/json`, so its input contract is
exactly the JSON-visible value. It then recursively emits every JSON map key,
array item, scalar, unknown field, full signature, and source string. Safe keys
are unquoted and multiline strings use a byte-length prefix instead of JSON
escaping. It does not add routing guidance, truncate strings, merge records, or
drop metadata. Existing JSON and projected-text behavior is unchanged.

The first indentation-based prototype was retained only as a negative result:
on the eight captured responses it totaled 41,832 bytes versus 37,148 bytes for
minified JSON, **12.6% larger**. Structural whitespace erased the escaping/key
savings. It was immediately replaced by a relaxed minified notation; this is
an implementation iteration, not an extra benchmark sample.

### Deterministic replay result

The final relaxed notation replayed the identical eight captured JSON objects:

| Captured result | JSON bytes | Full text bytes | Delta |
|---|---:|---:|---:|
| search t1 | 871 | 815 | -6.4% |
| search t2 | 477 | 471 | -1.3% |
| search t3 | 1,589 | 1,510 | -5.0% |
| lookup t3a | 17,635 | 16,449 | -6.7% |
| lookup t3b | 13,834 | 12,934 | -6.5% |
| lookup t3c | 1,768 | 1,664 | -5.9% |
| search t4 | 752 | 708 | -5.9% |
| verify t4 | 222 | 202 | -9.0% |
| **Total** | **37,148** | **34,753** | **-6.4%** |

The final prototype includes a CSV-style optimization for arrays containing at
least two objects with one identical field set: column names are emitted once,
then each object becomes an ordered row. Cells still use the lossless recursive
encoding, so nested objects, arrays, types, nulls, and multiline source remain
distinguishable. Shared nested objects are recursively columnarized too (for
example, `span(end,start)` is declared once). This improved the earlier relaxed
full-text total from 35,346 bytes (-4.9%) to 34,753 bytes (-6.4%). Only the two
large homogeneous lookup payloads improved; the remaining six payloads were
unchanged. Thus the columnar layout contributed about another 1.5 percentage
points on this sample, not the order-of-magnitude reduction seen in projected
text.

For comparison, the existing projected text renderer totaled 16,215 bytes,
**56.4% smaller** than JSON. That larger reduction cannot be attributed to text
syntax: it primarily reflects projection, de-duplication, signature truncation,
and tool-specific presentation/guidance.

These are byte counts, not Claude tokenizer counts. A 6.4% byte reduction does
not prove a 6.4% input-token or session-cost reduction; JSON punctuation and
quoted keys may tokenize efficiently. It also does not establish that Sonnet
uses the unfamiliar relaxed notation as reliably as JSON. The result does prove
the narrower point: complete JSON-visible semantics can be represented in text
with a small envelope reduction on this captured sample.

### Disposition

Do not release this prototype. Keep it as the full-fidelity text arm for the
controlled format study. The next useful comparison is full JSON versus this
full text under identical guidance, followed separately by projected JSON
versus projected text built from one shared semantic object. No paid Sonnet
cells, commit, push, or release were performed in S10.

## S11 — Two-cell Click screen: native versus full-text/CSV Prism (2026-09-08)

### Protocol and result

Two Sonnet cells were run sequentially on `pallets__click__pr3244`, native
first, in separate work/evidence directories. The Prism cell used the locally
built uncommitted binary with SHA-256
`177cac1d5c21ccad6310de9d1b199008e692c0384ac70a1eb578a671e7db2a7b`
and `PRISM_TEXT_RESULTS=full`. Both patches passed the 28 selected grader tests.

| Arm | Cost | Tokens reported | Turns | Tool calls | Prism calls | Grader |
|---|---:|---:|---:|---:|---:|---:|
| Sonnet native | $0.2896978 | 421,281 | 17 | 16 | 0 | 28/28 |
| Sonnet + Prism full text/CSV | $0.5485204 | 960,745 | 29 | 28 | 1 | 28/28 |

The observed paired cost delta is +89.3% for the Prism arm. This is one
screening pair, not a format estimate.

### What the transcript actually tested

The sole Prism call was `prism_search(query="fileno",
path="src/click/testing.py")`. It returned a 520-byte no-match result with an
empty `symbols` array. Consequently, the response used the relaxed full-text
object syntax but contained **no `csv(...)` table**. Sonnet proceeded to read
the target file and did not display an observable misunderstanding of the
no-match response. This run therefore supplies no behavioral evidence for or
against the columnar repeated-record syntax.

The extra cost was trajectory work, not Prism payload volume: the Prism arm
made 12 more tool calls, produced 17,393 versus 9,392 output tokens, and read
895,467 versus 383,089 cached-input tokens. Its initial richer temporary-file
implementation triggered three full-suite failures from unclosed-file warnings;
it inspected the lifecycle tests, added cleanup, and reran the suites until
1,419 tests passed. Both final patches were similar in size and both satisfied
the selected grader. The Prism patch also attempted to preserve descriptor-level
subprocess output in Click's mixed output stream, an optional behavior beyond
the minimum grader requirement.

### Validity warning

The native agent began with `find / -name "testing.py" -path "*click*"`, which
violated the repository-only prompt and ran until the tool moved it to the
background after 120 seconds. Its result was not read, but the command makes
the native cell protocol-invalid under the stricter S9 criteria and also
distorts wall time. The harness failed to flag it. Separately, an attempted
`mason_bench.py --help` unexpectedly launched that script's default workload;
the accidental process was stopped before the intended Click cells, but this
is another reason to avoid treating the pair as clean causal evidence.

Disposition: retain the measurements, do not use this pair to choose CSV or a
production default. A valid CSV behavior cell must deterministically elicit at
least one repeated-record Prism response and confirm the exact delivered
`csv(...)` payload. No commit, push, or release was performed.

## S12 — Path-local miss recovery experiment (2026-09-08)

### Experimental change

An additional uncommitted `PRISM_NEARBY_ON_MISS=1` switch adds a bounded
`nearbySymbols` recovery set only when a search has no symbol or text match,
has completed without timeout/truncation/rejected paths, and specifies a narrow
path or glob. Candidates come from the existing path-filtered symbol index,
prefer top-level declarations, are capped at eight, omit bodies/index internals,
and are explicitly labelled as navigation candidates rather than matches.

A deterministic Click-like fixture passed: searching for absent `fileno` in
`src/click/testing.py` retained an empty exact `symbols` list and returned
`BytesIOCopy` among nearby declarations. Full-text delivery contained a real
lossless `nearbySymbols:csv(...)` table. Switch-off and unscoped searches
remained unchanged. The complete Go suite passed before agent execution. The
tested binary SHA-256 was
`a5784b96b7e5557d81714f95913cdcab9e527aa0326984807e59cc5f6ffa9b03`.

### Fresh sequential Sonnet pair

Order was reversed from S11: recovery Prism first, native second. Both cells
used fresh work/evidence directories and passed all 28 selected grader checks.

| Arm | Cost | Reported tokens | Turns | Tool calls | Prism calls | Grader |
|---|---:|---:|---:|---:|---:|---:|
| Prism full text/CSV + recovery | $0.5240946 | 1,045,110 | 31 | 30 | 2 | 28/28 |
| Native | $0.2364354 | 337,121 | 17 | 16 | 0 | 28/28 |

The observed Prism delta was +121.7%. Prism used 44,520 cache-creation,
986,063 cache-read, and 14,465 output tokens versus native's 21,277, 307,232,
and 8,578. Total Prism result payload was only 971 bytes.

### Activation audit

The natural run again did **not** exercise miss recovery or CSV. Sonnet searched
`query="class _NamedTextIOWrapper"` within `src/click/testing.py`; Prism found
the actual `_NamedTextIOWrapper` symbol plus its source line. Since this was not
a miss, adding nearby candidates would have violated the experiment's contract.
The returned arrays each had one record, below the CSV threshold. Sonnet's
second Prism call was `prism_verify`, which returned `verdict="complete"`.

The higher cost came from the trajectory: the Prism arm performed 14 additional
tool calls, inspected lifecycle behavior, ran more targeted/full suites, and
produced a 74-line lazy-temporary-file implementation with explicit stream
cleanup. The native arm produced a 56-line eager-temporary-file implementation.
Both passed the grader. Neither cell recorded a harness protocol violation in
this pair.

Disposition: the recovery implementation works deterministically, but this
natural Click pair supplies no evidence that Sonnet benefits from or is harmed
by its CSV response because the trigger did not occur. Do not infer that the
971 Prism bytes caused the large session delta. A representation-comprehension
probe may deliberately invoke the miss route, but it must be labelled as a
steered micro-evaluation rather than a natural coding-cost benchmark. No
commit, push, or release was performed.
