# Imported Go Interface Contract Recovery

Grove commit `8dad45479ff72b78c7c8e930c6d49cbed18b39a8`, on
`fix-go-interface-impact`, follows local inherited-family commit `184f8a9e`.
Both Prism arms use product commit `5bdc73df`; temporary binaries differ only
in the Grove source selected by an external modfile.

The deterministic three-package fixture reproduces a hard baseline failure.
With Grove `184f8a9e`, `change-impact Writer.CloseNotify --file api/api.go`
exits 1 and says the interface declares no such method. With `8dad4547`, the
same query returns four sites: the inherited API declaration, its declaring
interface, caller `api.Stream`, and exact implementation
`impl.Writer.CloseNotify`. The wrong-return `impl.Wrong.CloseNotify` decoy is
excluded, and an unrelated imported `util` package does not suppress the
contract.

The implementation source-loads only import-connected project packages that
declare interfaces, then uses `go/types` method-set identity. Synthetic
interface-member edges survive incremental partial/skipped-language carry and
are dropped when their owning symbol changes. Full Grove and
dependency-replaced Prism race suites pass; Prism verify reports no missed
sites.

The cost guard alternated six fresh-index trials per arm on the same 324-file
Prism archive. Median time was 0.6012s before and 0.5984s after, a -2.7ms
(-0.45%) descriptive delta. Both arms produced 1,454 symbols and 4,911 edges.
This shows no material regression in this sample; it is not evidence of a
performance improvement.

The replay retains 28 hashed artifacts plus its checksum manifest, including
raw stdout/stderr, payloads, timings, fixture, binary metadata, and exact Grove
source snapshots.

Model runs: **0**. Spend: **$0**. Autonomous accuracy and session token
savings: **unmeasured**. Generic interfaces and structurally compatible
implementations in packages with no import connection remain outside this
increment; keep Prism's `partial` boundary and recovery-search guidance.
