# Proposed Routing Comparison

Status: proposed, not run. User approval requested for approximately $3 of
additional model spend. No result is implied by this document.

## Design

- Eight fresh Codex executions: Gin and Django, two repeats, old/new routing.
- Same candidate binary, model, effort, tools, task pins, answer schema, oracle,
  permissions, and execution helper in both arms. Native file/search tools remain
  available. The old arm also receives the search-label and rollup fixes; this
  experiment isolates guidance, not those code changes.
- Preserve the original panel's task/answer instructions byte-for-byte. Change
  only its appended TOOLS paragraph. Old: existing search/query-first guidance.
  New: known affected-site target -> impact; known method bodies -> batch lookup;
  unknown location -> search/query; subsequent calls address explicit evidence gaps.
  Both retain warnings and unresolved-edge safeguards. No expected answer names
  or task-specific stopping hints may be added to either paragraph.
- This measures a CLI-adapted routing paragraph, not deferred ToolSearch behavior
  or the entire generated project instruction file. Save both exact prompts and
  the source guidance before launch. Do not inject contradictory search-first
  text into the new arm through the existing helper.
- Fresh git archives per execution, no corpus history or earlier answers, no
  delegation/network/skills. Preserve raw output, usage, commands, timestamps,
  source/binary/harness hashes, and every failed attempt.
- Two executions per pair; reverse launch order on second repeats. No quality
  retries or result-dependent task substitutions. A non-use or setup failure is
  retained with its spend and classification, never treated as a zero-cost success.

## Budget And Readout

- $3 launch budget with $0.75 headroom before each pair; 600-second cell timeout.
  This is not a hard billing cap. Stop new launches on unknown cost, setup failure,
  or insufficient headroom; already-running costs remain in the report.
- Reuse the prior comparison thresholds, unchanged: no paired recall loss or added
  false-complete result; candidate mean recall and precision >=95%; median paired
  token saving >=25%; aggregate cost saving >=30%. All eight valid cells required
  for a complete decision. Missing usage is unknown, not zero.
- Separately report input/output/cache counters and per-run spend. Tool counts
  are diagnostic, not equivalent to model requests or context reprocessing.
- Inspect first successful discovery, search errors, searches after impact, batch
  lookups, and unresolved gaps. Reduced calls with lower recall is not success.
- Even a pass is a small guidance study, not statistical significance or proof
  of savings over native Codex/Sonnet. Follow with held-out four-way controls.
