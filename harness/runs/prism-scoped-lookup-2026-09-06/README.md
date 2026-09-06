# Exact File-Scoped Lookup: Free Evidence

Date: 2026-09-06. Product commit: Prism `71a509b`, on
`cand-search-context-clean`. Candidate source is byte-identical to the four
source/test hashes recorded in `results/manifest.json`.

## Result

The deterministic Django MCP replay passes. No models were invoked.

| Check | Result |
| --- | --- |
| Recorded legacy lookup sequence | Five calls, ten named requests |
| Candidate scoped delivery | One batch, the same ten requests in order |
| Valid scalar evidence preserved verbatim, once | 8/8 bodies/projections |
| Wrong scope/receiver requests | Two explicit misses; no substitute bodies |
| Full impact response | Identical between binaries |
| Original legacy requests | Identical responses between binaries |
| Batch versus ten scoped single-item calls | Exact concatenation equality |
| Original corpus files / git history | Unchanged / no HEAD, both arms |
| Response UTF-8 bytes | 14,212 -> 13,519 (4.9% fewer) |
| Serialized lookup schema/description UTF-8 bytes | 979 -> 1,375 (+396) |
| Model executions / estimated model spend | 0 / $0 |

The first recorded call asked for `DatabaseWrapper.get_connection_params` and
`DatabaseWrapper.pool` with a base-backend directory hint. Legacy lookup returned
the base class's differently qualified method for the first request and an
out-of-file pool implementation with an ambiguity warning for the second.
The new exact items identify both as misses in `base/base.py`. All eight valid
requests still receive the same complete evidence. This is an accuracy safeguard
at the retrieval boundary, not a measured increase in autonomous task accuracy.

The response-byte reduction partly reflects removal of those inappropriate
substitute bodies. It is not lossless compression of the entire old response,
not a tokenizer measurement, and not whole-session token savings. The schema
is larger; whether avoided requests offset that cost still needs a model study.
Five-to-one is demonstrated delivery capability, not observed agent adoption.

## Validation

- Ten new Go tests cover cross-file duplicates, projection, wrong files/types,
  path normalization, directories, traversal, absolute paths, external symlinks,
  ambiguity, >25-name collisions, legacy compatibility, unchanged arguments,
  invalid input, scoped omissions, unknown metadata, and schema/parser agreement.
- Seven functional tests failed on the prior implementation. All ten pass on
  the candidate, and `GOFLAGS= GOWORK=off go test ./... -race -count=1` passes.
- `git diff --check` passes. Prism verifies the four-file product diff as
  complete, including the changed internal batch-handler signature.
- Three probe tests cover expected versus unexpected JSON-RPC errors without
  discarding the original error packet. Both MCP tools/list schemas are retained.
- The original 638-file research archive and its 594 artifact checksum checks
  still pass, as do its 40-cell summary and 16-cell raw-answer/usage replays.

Control binary: `969239d7bb991c3feb64e48d952cc1ff17d1a449a5d58df588e0a005b28440a2`.
Candidate binary: `ac41360cd212fce40bd627884d3a606720d59e235806cd97978abb5cd2d0867d`.
Corpus: Django `318a316a4c86a65bede68144f9546a6056d91379`.

## Evidence And Limitations

`results/` contains the passing manifest, patch, requests, MCP replies, schema
responses, and checksums. `PROTOCOL.md` was written before the first attempt.
The transport helper is reused unchanged from the earlier frozen archive and
identified by SHA-256 in the manifest. The manifest's source head is `db23621`
with the candidate patch applied; the final product commit is `71a509b`.

Two probe-harness failures are retained, with their original script versions:

- `failed-preflight/`: compared the pretty-printed task file to the original
  source-task hash. Corrected by checking each file's own checksum and requiring
  equal parsed task data. MCP had not started.
- `failed-rpc-rejection/`: the control correctly rejected the new shape with a
  JSON-RPC error; the transport helper raised before the probe recorded it as
  the expected rejection. Corrected error handling is unit-tested.

Neither failure changed product source, discarded an agent-quality result, or
incurred model spend. The final replay used fresh archives again.

The frozen probe expects the original `db23621` checkout with
`results/candidate.patch` applied as working-tree changes, plus the two recorded
binaries and explicit `--prism-repo` / `--evidence-root` paths. It is a historical
replay script, not a general benchmark launcher. Temporary corpus/index files
are excluded from the archive; shared source checkouts and agent configs were
not modified.

Next: a separately frozen before/after model comparison, followed by native
Sonnet/Codex controls. Keep 25% median paired token and 30% aggregate estimated
cost targets, no paired recall loss, and explicit failures/non-use. No new paid
comparison has been launched or claimed here.
