# Accuracy-gap oracle audit — 2026-09-07

This audit was run against the released Prism v0.72.0 binary before the
four-head repeated panel. It classifies the four known accuracy gaps before
any product change.

## Conclusions

| Task | Observed v0.72.0 result | Classification | Measurement correction |
|---|---:|---|---|
| Guava `ForwardingObject.delegate` | R .9839 / P .9502 | Oracle omission plus five real anonymous-class misses | Add 15 valid `util.concurrent.ForwardingBlockingDeque` sites to GT |
| Jackson `JsonSerializer.serialize` | R 1 / P .9076 | Test-path and duplicate-answer scorer bugs | Maven `src/test/java` sites are neutral; score unique sites |
| Django `BaseDatabaseOperations.quote_name` | R 1 / P .8889 | Real heuristic receiver false positives | None |
| TypeORM `Driver.escape` | R 1 / P .9737 | Type-container output conflicts with method-site contract | Record `declaringTypes` as metadata, not scored sites |

After the measurement corrections, the deterministic one-call expectations
are Guava R .9846 / P .9969 / F1 .9907, Jackson 1 / 1 / 1, Django
1 / .8889 / .9412, and TypeORM 1 / 1 / 1. These are engine-ceiling probes,
not agent-panel results.

## Evidence and decisions

### Guava

The checked-in Spoon oracle contained the deprecated
`collect.ForwardingBlockingDeque` and `util.concurrent.ForwardingBlockingQueue`
but omitted the live `util.concurrent.ForwardingBlockingDeque`. That class
extends `ForwardingDeque`, so its `delegate` override and 14 callers are valid
members of the target change closure. Regenerating the Spoon result reproduced
the omission, consistent with a duplicate-simple-name hierarchy-resolution
failure. The task GT is manually amended with the 15 independently inspected
sites.

Prism still misses five real sites, all anonymous-class methods or methods
nested in anonymous classes:

- `ConcurrentHashMultiset.java:delegate`
- `MutableClassToInstanceMap.java:iterator`
- `MutableClassToInstanceMap.java:spliterator`
- `StandardTable.java:delegate`
- `Synchronized.java:delegate`

Prism also attributes the anonymous `MutableClassToInstanceMap` members to the
outer `entrySet` method, leaving one false positive after the GT correction.
The 77,908-byte response exceeds the existing 65,536-byte payload gate and is
tracked separately from localization accuracy.

### Jackson

All 11 unique extras were under Maven `src/test/java`; production-only ground
truth intentionally treats test sites as neutral. The scorer recognized Go,
Python, JavaScript/TypeScript, and some Java test naming patterns, but not the
Maven directory. Agent answers also repeated exact sites, and the scorer looped
over the list rather than applying the documented set metric. Scorer v4 fixes
both problems. Java task prompts now explicitly say “production source tree.”

### Django

The four extras are methods in `django/contrib/postgres/operations.py` that call
`schema_editor.quote_name`. That wrapper is
`BaseDatabaseSchemaEditor.quote_name`, which delegates to
`self.connection.ops.quote_name`. A signature change to
`BaseDatabaseOperations.quote_name` requires updating the wrapper body, but not
the wrapper's callers. The four sites are therefore genuine heuristic receiver
false positives; the production oracle is unchanged.

### TypeORM

Prism reports `src/driver/Driver.ts:escape` as the affected interface member and
also reports `src/driver/Driver.ts:Driver` as its declaring type. Both point to
the same source line, while the shared answer schema explicitly requires a
`FunctionOrMethodName`. Scoring both double-counted one edit location and
penalized a contract-compliant method answer. The harness now scores method
groups (`declarations`, `family`, `callers`, `supers`) and records
`declaringTypes` only as fidelity metadata.

## Reproducibility

The pre-correction four-task artifact is
`/private/tmp/prism-v072-gap-audit.json`; the regenerated Guava Spoon artifact is
`/private/tmp/guava-oracle-regenerated.json`. Temporary paths are noted for the
working audit only; the classifications and corrections above are the durable
record.
