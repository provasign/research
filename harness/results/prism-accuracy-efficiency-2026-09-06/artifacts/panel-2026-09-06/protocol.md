# Four-Way Validation: Next Batch

Status: approved by the user on 2026-09-06; the 24-cell panel is running.
The approximately $15 budget is a launch budget, not a hard provider billing cap.
Each four-cell wave requires $4 of remaining headroom, each Claude cell is capped
at $1, and every cell has a 600-second timeout. Unknown aggregate usage stops
subsequent launches. Codex's in-flight spend cannot be hard-capped by its CLI.
The outcome thresholds and task selection below are unchanged.

## Decision

Determine whether the current candidate is a dependable baseline for the next
accuracy and token-cost optimization phase. This is not a release-certification
or general product-superiority test. The first Jackson pilot remains exploratory
evidence and is not pooled into the new confirmatory-looking summary.

## Fixed Panel

| Task | Language | Kind | Expected sites | Purpose |
| --- | --- | --- | ---: | --- |
| gin-4645 | Go | Bug localization | 2 | Easy native-tools control; expose Prism overhead |
| django-connparams | Python | Backend signature impact | 8 | Declaration, overrides, and indirect backend structure |
| typeorm-driver-escape | TypeScript | Driver signature impact | 37 | Broader implementation family and callers |

Two repeats of each task, with four arms per repeat: Sonnet native, GPT-5.5
Codex native, Sonnet + Prism, GPT-5.5 Codex + Prism. Total: **24 cells**, yielding
six paired comparisons per client, across three tasks. Do not substitute tasks
after inspecting model outcomes. Two repeats reveal obvious instability but are
not enough to establish low-variance or statistically significant superiority.

Freeze the existing candidate binary and its source patch:
`63f5166f6adf40f768a9cf32701a13344abcf29c51064cc9fe372dbb210a7e7d`.
Its internal-source diff still matches the first four-way pilot. Use the same
models and medium effort. Use task-specific output wording: localization tasks
must not accidentally receive an instruction to enumerate all impact callers.

## Preconditions

1. Revalidate corpus pins and task/scorer hashes before execution. Use fresh
   archive snapshots without original Git history or model-visible ground truth.
2. Confirm the six local Prism MCP tools are explicitly approved in Codex's
   invocation config. Require server initialization and run a model-free MCP
   handshake/search against a separate fixture before launching paid cells.
3. Keep native tools available in both treatments; disable other MCPs, skills,
   memory, delegation, and network search. Preserve exact prompts and CLI configs.
4. Validate actual arm use from transcripts. An approval/transport failure that
   makes a Prism arm fall back entirely to native is not a valid Prism cell.
   Stop it promptly, retain its cost as setup overhead, and do not silently score
   the fallback as Prism. Ordinary successful-tool errors/recovery remain treatment
   costs, not conveniently excluded setup overhead.

## Ground-Truth Audit

- Gin: read `response_writer.go` from the actual task pin
  `8d0468f72897652485933b845253386f9147a8bf`, not the current checkout, which
  already contains a fix. The two unchecked interface assertions are in
  `Hijack` and `CloseNotify`; `Flush` already checks the interface. Expected
  production fix sites are unchanged.
- Django: checkout equals task pin `318a316a4c86a65bede68144f9546a6056d91379`.
  An independent Python AST scan of the production package finds five
  `get_connection_params` declarations and three references in `connect` and
  the Oracle/PostgreSQL `pool` methods. Its eight unique path/method sites
  exactly match the frozen task.
- TypeORM: checkout equals task pin `3d55188c0dd1256f520143379ecf97f45e71acba`.
  Reran the existing ts-morph oracle: 12 family members, 25 resolved call hits,
  37 unique expected sites, matching the task exactly. The apparently missing
  `InsertQueryBuilder` references are commented-out code, not active call sites.
  This is oracle reproducibility plus targeted review, not a claim that static
  analysis proves the absence of every possible dynamic reference.

Do not use the existing Django `quote_name` or Grafana `CheckHealth` tasks as
readiness gates without repairing their answer sets. The former omits
`BaseDatabaseSchemaEditor.quote_name`, which calls
`self.connection.ops.quote_name(name)` at the pinned revision. The latter's
41-site answer set omits HTTP handlers that call `pluginClient.CheckHealth`.
These defects were found before any new model output was observed. The existing
task files were not changed as part of this preparation.

## Execution And Accounting

- Predeclare and balance arm order between repeats. Keep scheduling comparable;
  record concurrency and start time. Do not selectively rerun low-quality cells.
- Separate per-invocation new spend, each measured cell's cost, and setup overhead.
  Do not mix earlier runs under the same manifest into fresh-cell costs. Preserve
  every attempt, including timeouts, missing aggregates, and excluded setup cells.
- Count all reported input/cache/output categories. Claude totals include
  auxiliary `modelUsage` entries; Codex cached tokens are a subset of input, not
  extra tokens to add twice. Preserve unknowns rather than invent zeros.
- Label dollars accurately: Claude CLI estimates and Codex API-equivalent
  estimates, not reconciled invoices or subscription charges. Record provider
  cache counters and report token results independently of cost results.
- Bound Claude cells with its dollar-cap option and all cells with a timeout.
  Codex exec has no equivalent hard dollar-cap flag; a proposed $15 budget must
  not be advertised as an enforceable hard cap without additional metering.
  Agree the launch/stop policy before running. Budget-incomplete panels are
  inconclusive, never PASS.
- Keep provider caching visible. Balanced launch order cannot guarantee cold
  provider caches or remove all cross-cell cache effects.

## Predeclared Readout

Report every task/repeat/client pair: required-site recall, precision,
false-complete claim, total reported tokens, estimated cost, time, and tool calls.
Show native versus Prism differences separately for Sonnet and Codex; do not let
one client's win conceal the other's loss. Show easy-control and broader-impact
results separately as well as a task-balanced summary.

Use these conservative diagnostic acceptance targets for this panel:

- All 24 cells have valid measurements and arm-use audits, or the panel is
  inconclusive. Retain setup failures separately and disclose their spend.
- Prism loses no required-site recall against its paired native cell, and adds
  no false-complete claims. Report absolute recall and precision; a tie at poor
  quality is not success. Require at least 95% mean recall and precision per client.
- For each client, target at least 25% lower median paired total-token use and
  30% lower summed estimated cell cost over the same task/repeat pairs. Show
  per-task regressions even when the aggregate improves.

A failure or unstable result becomes a concrete next-phase target; it must not
be hidden by more compression or a favorable rerun. Passing supports retaining
the current implementation as a baseline for the next optimization. It does not
prove that the recent changes caused the advantage: that requires an additional
released-Prism control. Release/product claims also require larger held-out
tasks, corrected hard-task oracles, and end-to-end patch/behavior validation.
