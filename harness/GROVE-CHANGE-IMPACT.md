# grove change-impact — the graph-native build

**Status: engine done, measured, 2026-07-03.** `grove change-impact
'Type.method(Params)'` computes the type-resolved change-set — declaration +
override/implementation family + resolved callers — inside Grove, independent
of the Spoon eval oracle. This replaces the tautological Spoon-powered PoC
(`change_impact.py`) with the real thing.

## Result (vs the independent Spoon oracle, GT scope src/main)

| task | sites | recall | precision |
|---|---|---|---|
| jsonnode-get `JsonNode.get(int)` | 8 | 1.000 | 0.727 |
| settable-set | 22 | 1.000 | 1.000 |
| writetypeprefix | 38 | 0.974 | 1.000 |
| serializewithtype | 58 | 1.000 | 1.000 |
| deserialize | 104 | 1.000 | 0.972 |
| serialize | 108 | 0.981 | 0.991 |

**Mean recall 0.993, mean precision 0.948.** One deterministic call,
milliseconds, $0. Compare: Opus+text ≈ recall 1.0 at 24–39 turns / ~$5.64/run;
Sonnet T swings 0.73–0.996. Scorer: `harness/score_grove_change_impact.py`
(run after reindexing the corpus with the current grove binary).

Residual misses (3 sites / 336): `ObjectNode.serializeWithType` (multi-line
call-site argc extraction), `WritableObjectId.writeAsField/writeAsId` (chained
receiver `w.serializer.serialize` — no chained-type inference). Residual
extras: callers of overloads the call-graph can't split without literal arg
evidence (jsonnode-get), plus `src/test-jdk17/` files the scorer's `/test/`
filter misses (scorer artifact, not a tool error — test callers are real
change sites, just outside GT scope).

## What it took: 5 Java resolution bugs in grove/astkit (all fixed + tested)

The traversal was designed and validated first as a SQLite prototype
(`harness/proto_sqlite_change_impact.py`) scored against GT; every recall gap
was then traced to an engine bug. Loop: score → inspect misses → find
mechanism → fix → reindex → rescore. Recall went 0.05 → 0.99 on the big tasks
purely from engine fixes:

1. **Multi-line Java signatures** (astkit): `Signature` was the declaration's
   FIRST LINE; jackson wraps `extends`/`implements` and params onto
   continuation lines, and a leading `@Override`/`@SuppressWarnings` became
   the whole signature. → `SignatureBeforeBody` (full header, annotations
   excised). This alone: serialize recall 0.05→0.68; overrides edges 0→2158.
2. **Generic bounds parsed as inheritance** (grove): `<T extends Enum<T>>`
   risked bogus extends edges → strip balanced `<…>` before the regex.
3. **Java wildcard imports resolved to nothing** (grove): `import pkg.*` has
   last-segment `*`; package paths are dir *suffixes* (src/main/java prefix) so
   the equality-keyed dir lookup missed → reverse suffix lookup.
   serializewithtype 0.66→0.90, deserialize 0.59→0.82.
4. **Same-file shadowing beat typed receivers** (grove): a file overriding
   `serialize` hid `JsonSerializer.serialize` from its own
   `serializer.serialize(...)` call sites (same-file candidates won outright).
   → same-file-wins disabled for Java calls through explicit non-self
   receivers. deserialize 0.82→0.98, serialize 0.81→0.98.
5. **Nested generics in field/local types** (grove):
   `JsonDeserializer<Enum<?>>` broke the one-level generic regex → one nesting
   level tolerated. deserialize →1.000; jsonnode-get precision 0.36→0.73.

These fixes improve every Grove consumer (prism_references, impact, calls
confidence) on any conventionally-formatted Java codebase — not just this op.

## The op (where it lives)

- `grove/internal/graph/changeimpact.go` — `CodeGraph.ChangeImpact(query)`:
  parse `Type.method(Params)` → resolve declaration via contains edges (+ param
  filter) → subtype closure over inbound extends/implements → family filtered
  by signature compatibility (type-parameter wildcards) → callers via inbound
  call edges to exact symbol IDs. Returns Declarations/Supers/Family/Callers.
- `grove/pkg/grove/grove.go` — `Engine.ChangeImpact` + `ChangeImpactResult.Sites()`.
- CLI: `grove change-impact 'JsonSerializer.serialize(T, JsonGenerator, SerializerProvider)' <dir>`.
- Regression tests: `internal/graph/fieldreceiver_test.go`, `edges_test.go`
  (generics), astkit `strategies_test.go` (multi-line signatures).

## Paper framing (Path A)

This is the honest version of the PoC's claim: the graph itself — not the
oracle — reconstructs the change-set at recall 0.993. Two findings worth
reporting: (a) tool altitude (the op) delivers the completeness no arm could
reliably orchestrate from primitives; (b) the engine bugs were invisible to
every LLM arm in the original study — G-arm agents silently inherited them,
which is itself evidence for deterministic, testable traversals over
LLM-orchestrated ones.

## Next

- Expose as `prism_change_impact` MCP tool (Path B rung 1 / prerequisite for
  the Claude-tier G* arm).
- G* arm in the harness (`arms.py`), then the re-grid (Path A).
- Known residuals if we want 1.0: chained-receiver typing, multi-line
  call-site argc, per-call-site overload evidence.
