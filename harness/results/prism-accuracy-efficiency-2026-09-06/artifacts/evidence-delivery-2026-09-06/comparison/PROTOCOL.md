# Codex Evidence Delivery Comparison

Authorized on 2026-09-06 after the free probes. No model results observed when
this protocol was written. Eight executions: two tasks, two repeats, two Prism
versions. This is a before/after candidate test, not a native-tools comparison.

## Frozen Inputs

- Before: panel binary SHA-256
  `63f5166f6adf40f768a9cf32701a13344abcf29c51064cc9fe372dbb210a7e7d`.
- After: evidence delivery binary SHA-256
  `b8819ec951c78823c0df87b9ac39a9916302322c4799760e772efd125e4c39d0`.
- Tasks: `gin-4645` and `django-connparams`, using the panel's saved task files,
  corpus commits, and original answer sets. Fresh archive per execution, no
  original Git history or agent customization files.
- Model: `gpt-5.5`, medium effort; the existing panel's CLI configuration,
  exact task/Prism prompt, native tools, explicit MCP approvals, usage auditing,
  and scorer. No added instruction specifically requiring batch adoption.
- Pairs: Gin repeat 1, Django repeat 1, Django repeat 2, Gin repeat 2. Submit
  before/after in repeat 1 and after/before in repeat 2; concurrency two within
  a pair. Actual timestamps are recorded; submission order is not guaranteed
  execution order. Provider caches are not controlled.
- No product, prompt, scorer, or threshold changes during the run. No outcome-
  based retries, no replacement for non-use, and no earlier cells pooled in.

## Spend And Failure Rules

About $3 is a launch budget, not a hard billing cap. Require $0.75 remaining
headroom before starting each two-cell pair. Both cells retain the previous
600-second timeout. Preserve every attempt and its cost in this invocation.
Stop subsequent launches on unknown/non-finite usage or cost, or an MCP setup
failure. Ordinary argument errors and recovery remain operating costs.

Codex dollar estimates use the same $5/$0.50/$30 per million uncached
input/cached input/output rates as the previous panel, not subscription billing
or an invoice. Report tokens independently; cached input is a subset of input.
Indexing time is separate from agent time and uses no model tokens.

## Acceptance

All eight cells must pass usage/arm-use audits, or the result is inconclusive.
For the four paired measurements, require:

1. No paired recall loss and no added false-complete claim.
2. Candidate mean recall and precision each at least 95%.
3. At least 25% median paired total-token reduction against old Prism.
4. At least 30% summed estimated-cost reduction against old Prism.

Show per-task regressions regardless of aggregate results. Diagnose successful
batch adoption, tool errors, and searches/lookups/native commands after the
first successful impact call. These counts describe behavior, not separately
attributed billing or proof that all following reads were redundant.

Two tasks with two repeats cannot establish statistical or product-wide
superiority. Even a pass requires later native-tool and Sonnet comparisons.
