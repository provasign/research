# Claude and Codex native baselines and Prism comparison

Status (12 September 2026): **partial; paid runs stopped**. The [reviewed
comparison](../results/prism-compare-2026-09-12/comparison.json) has 27 valid
historical native/Prism pairs out of 34 planned. Five original Codex coding
cells attempted a Prism MCP call that Codex denied under its approval policy.
The original runner counted the attempt as Prism use, so its `audited_valid`
field was wrong for this comparison. Three of those cells subsequently used
the Prism CLI, but the denial still contaminated their protocol. The reviewed
comparison excludes all five and preserves the original summaries as raw
evidence. The two other missing pairs are the known Claude native impact
timeouts described below.

One Codex coding repair gate, `pallets__click__pr3466`, completed with two
successful Prism MCP calls and a valid score; it did **not** resolve the task.
It is archived [separately](../results/prism-compare-2026-09-12/coding-codex-repair-gate/summary.json)
and is not substituted into the aggregate. A four-task repair batch was
[stopped](../results/prism-compare-2026-09-12/coding-codex-repair-stopped/manifest.json)
before producing any completed summary row. No paid cells from this comparison
are running.

The 34 original Prism cells plus the one completed repair gate recorded
$15.832 in API list-price-equivalent cost. This is an estimate, not a bill.
The stopped cell has no final usage record, so its additional cost is unknown.

Offline harness tests pass (111 tests), and `git diff --check` passes. The
repository-wide `prism verify` verdict is `incomplete`: it reports five
untouched caller sites for concurrent `arms_for`/`agent_path` signature edits,
an unverified `Cell.tool_cli_dir` rename, and an index refresh limited by
oversized existing benchmark artifacts. These findings need review before any
commit; a passing test suite does not turn that verdict into a pass.

Scope: the two declared agent suites, `e2e` (8 coding tasks) and `manual`
(9 change-impact tasks). Both use Claude Sonnet 5 and Codex GPT-5.5 at
medium effort, one trial per task and arm. The native arms do not expose
Prism. The other task directories (`e2e-fanout`, `e2e-meaningful`, `seeded`,
`wide`) are not part of this matched agent comparison.

| Suite and baseline source | Valid Claude native | Valid Codex native | Scoring |
| --- | ---: | ---: | --- |
| `e2e` pilot: [`coding-suite-pilot-2026-09-07`](../results/coding-suite-pilot-2026-09-07/summary.json); remaining: [`product-proof-coding-remaining-2026-09-08`](../results/product-proof-coding-remaining-2026-09-08/summary.json) | 8/8 | 8/8 | Held-out FAIL_TO_PASS and PASS_TO_PASS tests |
| `manual` pilot: [`product-proof-impact-pilot-2026-09-08`](../results/product-proof-impact-pilot-2026-09-08/summary.json); remaining: [`product-proof-impact-remaining-2026-09-08`](../results/product-proof-impact-remaining-2026-09-08/summary.json) | 7/9 | 9/9 | Site-list oracle, scorer version 4 |

The two invalid Claude native cells in the `manual` remaining run are
`guava-forwarding-delegate` and `jackson-serialize`: both hit its 300-second
limit and have incomplete usage. [`four-head-impact-2026-09-07-stopped`](../results/four-head-impact-2026-09-07-stopped/summary.json)
has valid Claude native results for those same task pins and task hashes, but
that run allowed 1,200 seconds. Treat them as historical context, not as
300-second controls. Thus the strict matched impact set is seven tasks.

The task SHA-256 values in all four selected baseline manifests still match
the current task files. Their saved prompts match the current prompts after
normalizing CRLF to LF (the coding issue text contains CRLF). The baseline
manifests record task pin, source archive hash, agent versions, models,
timeout, and scoring configuration. Verify those fields again against each
new run before pairing rows. Keep invalid rows visible; never fill a missing
baseline with a timeout score or silently mix run protocols.

## What the completed cells show

The eight Claude coding pairs are valid: held-out resolution was 2/8 native
and 3/8 with Prism. Only 3/8 Codex coding pairs passed the reviewed protocol,
so there is **no Codex coding suite result**. Among the impact tasks, seven
Claude pairs had mean recall 0.8849 native versus 0.9447 with Prism; nine
Codex pairs had 0.9820 versus 0.9983. These are one-trial descriptive results
against historical native controls. In particular, the Claude impact gain
does not erase a TypeORM task regression (recall 1.0 to 0.6757). Per-task
results and provenance are in the [comparison JSON](../results/prism-compare-2026-09-12/comparison.json).

The Codex MCP denial was a harness/configuration failure, not evidence about
Prism's ranking quality. The compact `prism` MCP tool needed an explicit
approval configuration under the runner's `never` policy. A single-task smoke
and the separate repair gate confirmed the corrected configuration, but that
does not retroactively validate the five earlier cells.

## Gate before any further paid run

Treat the next run as a new, bounded experiment. Record the exact tasks, pins,
binary hash, CLI versions, timeout, maximum spend, and stopping rule before
launch. First run **one** representative cell. It must finish with a score,
complete measurement, no agent or harness error, no approval denial, and at
least one **successful** Prism action (an attempted call is insufficient).
Check the saved prompt, task hash, and source pin against its native control.
Stop and inspect if any condition fails; do not repair and automatically
restart the batch. Even if the gate passes, report its result and remaining
cost exposure before starting the rest. This is the missing decision point
that made the run unpredictable.

## Prism-arm run protocol used

Build Prism from the intended checkout into a fixed binary and pass that
path explicitly. Record its SHA-256 and the checkout state. First run one
pilot task per suite with only the two Prism arms; inspect agent errors,
measurement completeness, protocol audit, Prism adoption, and scoring.
Stop if either cell is invalid. The coding runner and impact runner both
stop later waves after an invalid agent cell.

```sh
python3 harness/bench.py run --suite e2e --tasks pallets__click__pr3244 \
  --agents claude,codex --prism on --prism-binary "$PRISM_BINARY" \
  --out /private/tmp/prism-compare-e2e-gate

python3 harness/runners/product_impact_suite.py \
  --tasks jackson-jsonnode-get --arms sonnet_prism,gpt55_prism \
  --prism-binary "$PRISM_BINARY" \
  --run-dir /private/tmp/prism-compare-impact-gate
```

If both gates pass, run the other 15 tasks with the same binary and runner
configuration. The gates count toward the 17-task comparison; do not rerun
those two tasks. Use unique output directories and retain all manifests,
measurements, and patches/answers. The existing native rows are controls;
do not pay to rerun them as part of this historical comparison.

```sh
python3 harness/bench.py run --suite e2e \
  --tasks Textualize__rich__pr3882,Textualize__rich__pr3938,urllib3__urllib3__pr3786,pallets__click__pr3228,pallets__werkzeug__pr3006,pallets__click__pr3466,pallets__click__pr3695 \
  --agents claude,codex --prism on --prism-binary "$PRISM_BINARY" \
  --out /private/tmp/prism-compare-e2e-remaining

python3 harness/runners/product_impact_suite.py \
  --tasks jackson-settable-set,typeorm-driver-escape,django-quotename,jackson-writetypeprefix,guava-forwarding-delegate,jackson-serialize,grafana-checkhealth-impact,grafana-querydata-impact \
  --arms sonnet_prism,gpt55_prism --prism-binary "$PRISM_BINARY" \
  --run-dir /private/tmp/prism-compare-impact-remaining
```

For each task and agent, compare only valid Prism and native cells with
matching task pin/hash, model, prompt, timeout, and scorer. Coding outcomes
are resolved/FAIL_TO_PASS/PASS_TO_PASS plus tokens, cost, turns, and wall
time. Impact outcomes are recall, precision, F1, surfaced gaps, tokens,
cost, turns, and wall time. Report per-task rows before aggregates, and
show the denominator for each aggregate. Keep the two missing strict Claude
impact comparisons out of paired aggregates.

These saved native cells ran on earlier dates and agent CLI versions. A
historical comparison can show where to investigate, but it is not a
same-day randomized A/B estimate of Prism's causal effect. Repeat native
controls under the same current setup before making that stronger claim.
