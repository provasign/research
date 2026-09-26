# Go Interface Family Materialization

Grove commit `184f8a9ee57170d41e96029e70d578655f901a34`, on
`fix-go-interface-impact`, follows caller recovery commit `ff9adefb`. Both
Prism arms use product commit `e757c6b`; temporary binaries differ only in the
Grove source linked through an external modfile.

On independent fresh archives of Gin commit `8d0468f7`, the concrete query
`responseWriter.CloseNotify` changes from one declaration and two callers to
the same sites plus the inherited `ResponseWriter.CloseNotify` super and its
declaring interface. The interface-rooted query gains that inherited synthetic
declaration and declaring interface while preserving its concrete family and
two callers. No site disappears. Both arms remain `partial`.

The engine now emits exact native implements/overrides edges for local Go
method sets and call edges to deterministic synthetic interface-member IDs.
That lets existing impact traversal connect a caller, an inherited external
member, its local interface, and local implementations without name guessing.
Signature, result, case, pointer/value, promotion, shadowing, ambiguity,
unresolved-type, exact-file, and incremental stale-edge controls pass.

Full Grove and dependency-replaced Prism race suites pass. Prism reports no
missed sites across the five-file follow-up diff; it identifies the standalone
`typeDeclaresMember` helper becoming a graph method as a contract change, and
all three callers were updated. The final replay verifies 25 artifact hashes;
its six Grove source hashes match commit `184f8a9e` exactly.

`pre-refactor-pass/` preserves the first successful replay. `results/` is the
final-source replay after a no-behavior helper simplification. These are
development checkpoints, not statistical repeats. Generated `go version -m`
files retain their original trailing tabs as raw evidence.

Model runs: **0**. Spend: **$0**. Autonomous accuracy and session token savings:
**unmeasured**. Larger result inventories are necessary evidence, not a token
saving. Cross-package project-source loading and generic interfaces remain
unfixed; retain Prism's partial boundary and recovery-search guidance.
