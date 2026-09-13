# Impact Coverage And Task Depth

2026-09-06. Product commit `cef7dad179276f40c3174391668ab350d99c834c` on
`cand-search-context-clean`. No benchmark model executions or model spend.

The preceding eight-cell experiment failed efficiency targets. Inspection of
its Gin trace found declarations-only `closed` impact results followed by text
searches revealing interface-dispatched calls. A new minimal Go fixture with an
embedded `http.CloseNotifier` interface reproduced the engine gap: one method
declaration, no callers, no declaring types, and `closed`, despite `Stream`
calling the method through the interface. The regression test failed before
the product change, as did the coverage-note rendering test.

## Change And Limits

- MCP/CLI `prism_change_impact` now classifies otherwise-closed Go method or
  interface results as `partial` with an actionable coverage note. This is a
  conservative language capability boundary, not a query-specific proof that
  every Go result omitted a site. Existing non-closed tiers are preserved.
- No engine site is removed, added or reclassified. The underlying Grove
  engine and adapter still return their original result. Missing interface
  callers are **not recovered** by this patch.
- The warning survives text rendering and cached pointers. Partial results do
  not feed the closed-impact scope counter. Wider-anchor hints preserve their
  candidates but cannot upgrade a partial Go set to a closed guarantee.
- Steering distinguishes known-body inspection from impact enumeration and
  avoids automatic body reads after enumeration. Before-edit and final-verify
  safeguards remain. No new task parser or model call was introduced.
- Existing agent config files and installed binaries were not regenerated.
  New steering applies when an installation regenerates its instructions.

## Free Replay

Fresh Gin and Django git archives at the prior study's pins, separate indexes,
no git HEAD. MCP and CLI JSON payloads were retained for both binaries.

| Check | Result |
| --- | --- |
| Gin CloseNotify impact | closed -> partial; 206 -> 372 response bytes |
| Gin Hijack impact | closed -> partial; 216 -> 382 response bytes |
| Gin site arrays and bodies | Identical |
| Gin interface caller in source | Still present; engine edge still missing |
| Django impact and eight-body lookup | Identical |
| Django gold identities already present in impact | 8/8 |
| Corpus changes / embedded history | None / none |
| Benchmark model calls / model spend | 0 / $0 |
| Session-token saving / new autonomous accuracy | Unmeasured / unmeasured |

Four new Go tests, including an eleven-case capability matrix, cover the real
fixture, inventory preservation, warning rendering, cached warnings and tier
compatibility. Existing wider-anchor and steering tests were updated. The full
race-enabled suite passed. Prism verify reported a manual-review obligation
for the steering constant, not missed sites: its declaration and `steeringBlock`
are the only references, and the routing/safeguard tests passed that review.

The first replay attempt is preserved in `failed-sandbox`: MCP succeeded, then
the CLI was denied access to its normal user-cache ledger lock. The same probe
and product source were rerun with cache permission; `results` is the passing
attempt. This was a setup permission issue, not an MCP or Prism search failure.
Both attempts used zero model calls. The standalone verifier checks all 58
artifact hashes and independently compares all inventories and raw responses:

```sh
python3 -I -B harness/runs/prism-impact-coverage-2026-09-06/verify.py
```

The original archive and preceding eight-cell raw answer/usage replay also
remain valid. Source hashes and a complete staged source patch tie the replay
to the product commit; binaries, corpus copies and caches are not archived.

## Decision

Do not declare a token win. Each affected Gin impact response gained 166 bytes
of necessary warning, and no autonomous measurement of the routing change ran.
The latest paid result remains 100% exact-site recall/precision, 9.4% more
aggregate tokens and 5.8% more estimated cost than the prior Prism binary.

Next work is the embedded engine's Go interface/embedded-method modeling, with
negative receiver/signature fixtures before restoring any closed claim. Broader
truthful completeness must precede stronger stopping advice. The task-depth
guidance still needs an isolated, frozen model comparison; eventual native
Sonnet/Codex controls are required before a product-wide savings claim.
