# Scoped Lookup Free Replay

Date: 2026-09-06. Model calls and model spend: zero.

## Hypothesis

Exact per-item file scopes can deliver the evidence requested by the observed
Django follow-up sequence in one batch, without substituting another file or
receiver. This is a deterministic capability test, not an agent-efficiency test.

## Inputs And Isolation

Use the five lookup requests from Django repeat 1, direct-routing arm of
`prism-routing-ab-y204tiw1`, retained in the frozen research archive. They contain
ten named requests with a common `fields=["signature","body"]` projection.
Convert the one directory hint `django/db/backends/base` to its exact
`django/db/backends/base/base.py` file. Preserve every requested name, in order.

Two requests in that base-file group are deliberately expected to miss under
exact scope: `DatabaseWrapper.get_connection_params` (the class there is
`BaseDatabaseWrapper`) and `DatabaseWrapper.pool` (defined in other backends).
Do not drop them or silently substitute their legacy fallback bodies.

Control binary SHA-256:
`969239d7bb991c3feb64e48d952cc1ff17d1a449a5d58df588e0a005b28440a2`.
The new binary, source files, patch, protocol, probe, and reused frozen MCP
transport helper are hashed in each invocation's manifest.

Each binary receives its own fresh archive of Django
`318a316a4c86a65bede68144f9546a6056d91379`, with no git history. The shared
corpus is read only. No installed Prism binary or global agent config is changed.
Original manifests, scripts, and transcripts remain untouched.

## Required Checks

1. The exact observed legacy requests render identically on both binaries.
2. Real MCP tools/list advertises the scoped item shape only on the candidate;
   the old binary rejects that new shape.
3. All eight valid scalar bodies/projections appear verbatim, once, in the
   candidate batch. The two wrong requests produce explicit misses, no bodies.
4. The ten single-item scoped outputs concatenate exactly to the batch output;
   there are no silent omissions, argument errors, or lost file identities.
5. The full impact response is unchanged between binaries; no site is filtered
   for comparison. All original corpus files remain byte-identical, with no HEAD.
6. Record response UTF-8 bytes, schema bytes, and available call reduction.
   Do not report these as tokenizer measurements or autonomous-session savings.

Each replay gets a new output directory. Failed replays retain diagnostics.
Passing this probe permits a subsequent model study; it does not meet the 25%
median token / 30% aggregate cost acceptance thresholds or prove general accuracy.
