# Go Interface Dispatch Replay

Free deterministic engine replay, not an autonomous-agent benchmark. No model
calls or token-savings claim. Both binaries use the same Prism product source
(cef7dad; e757c6b adds reports only). Only Grove changes, from v0.43.1 to the
local native Go interface-dispatch patch captured with this run.

Use separate fresh, history-free archives of Gin commit
8d0468f72897652485933b845253386f9147a8bf. Query the same scoped CloseNotify and
Hijack impacts through MCP and CLI JSON. Record all sites, bytes and index
wall time; a single ordered replay is not an index-performance estimate.

Required positive: Context.Stream appears in the candidate CloseNotify callers
and is absent before. No previously returned sites may disappear. Both results
must retain Prism's partial coverage warning. Hijack is a second observational
probe, not an independently complete caller oracle. Exact negative receiver,
parameter, result, case and missing-method controls live in Grove tests.

Candidate scope: possible interface-call targets among types checked in the
caller's package, including methods promoted from locally declared embedded
types. No whole-project points-to analysis, generic-instantiation enumeration,
cross-package implementation discovery, or complete impact-family claim.
Native analysis must run; missing imports/types remain a coverage limitation.

Retain raw responses, failed attempts, hashes, binary build metadata and exact
changed Grove sources. Do not overwrite a retained run. Do not mutate original
corpora, installed binaries, or previous experiments.
