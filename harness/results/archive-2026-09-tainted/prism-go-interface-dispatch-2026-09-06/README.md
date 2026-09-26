# Native Go Interface Dispatch

Grove commit `ff9adefb7ce84c7124d95b35295f3d29aec111cd`, branch
`fix-go-interface-impact`, based on v0.43.1 (`bdafac48`). Final `results/`
contains exact source copies matching all four committed files. Prism stays
at `e757c6b` (product source `cef7dad`); a temporary external modfile links
Grove without modifying Prism's dependency manifest or installed binaries.

## Evidence

| Gin impact | Callers before | Callers after | Compact reply bytes before / after |
| --- | ---: | ---: | ---: |
| responseWriter.CloseNotify | 0 | 2 | 372 / 781 |
| responseWriter.Hijack | 0 | 3 | 382 / 960 |

CloseNotify recovers `Context.Stream` and `TestResponseWriterHijack`.
Hijack recovers `TestResponseWriterHijack`, `TestResponseWriterHijackAfterWrite`,
and `TestResponseWriterHijackAfterWriteHeaderNow`. All previous sites survive.
Prism still reports `partial`. Family, supers and declaringTypes remain empty.
This is a caller-recall repair, not complete contract coverage or an exhaustive
precision/recall oracle. Larger replies deliver missing evidence; they are not
evidence of session token savings.

Model runs: **0**. Model spend: **$0**. Autonomous accuracy and token savings:
**unmeasured**. Last paid comparison is still the scoped-lookup efficiency
failure, not superseded by this free replay.

## Verification

Seven new Grove tests cover type-compatible pointer/value receivers, promoted
methods, interface aliases and method expressions; incompatible parameters,
results and case, missing methods, ambiguous/shadowed embedding, unresolved
types/imports, exact-file symbol binding, and stale-edge removal. Full and
incremental post-edit edge sets agree.

Commands passed on the final source:

```sh
# Grove worktree
env GOFLAGS= GOWORK=off go test ./... -race -count=1
prism verify --base bdafac48 --format text
# Prism clean worktree, temporary replacement modfile
env GOFLAGS= GOWORK=off go test -modfile=/private/tmp/prism-go-interface.mod ./... -race -count=1
# This research worktree, no binaries or model calls
python3 -I -B harness/runs/prism-go-interface-dispatch-2026-09-06/verify.py
```

Prism verifies all four changed Grove files with no missed sites. The offline
verifier checks 117 artifact hashes and recomputes the three passing replay
summaries from raw responses. Source hashes also match the Grove commit.

`failed-sandbox/` retains the ledger-cache permission failure. `initial-pass/`
is the initial implementation replay; `import-hardening-pass/` adds incomplete
type rejection; `results/` is the final exact-file mapping replay. Each pins its
own binaries and sources. These are development iterations, not independent
statistical trials. The first incremental test assertion incorrectly assumed
alphabetical caller ordering; it was corrected to compare sorted caller names.
The initial sandboxed Prism test run could not use ledger caches/localhost;
the permission-enabled final suite passed. No such setup failure is counted
as a product-quality failure or hidden as a zero-cost model execution.

## Remaining Work

The new native edges cover possible targets checked in the caller's package.
Cross-package implementors, generic instantiations, unavailable native analysis,
and inherited interface declaration/family materialization remain limitations.
Heuristic graph edges are unchanged; this patch does not certify their precision.
Keep the partial warning. A Grove release/dependency update and fresh autonomous
tests are still needed before claiming product-wide accuracy or savings.

Neither source nor evidence branch is pushed or tagged. Frozen replay runners
must not be rerun in place; use a new experiment directory.
