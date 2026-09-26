# Prism Accuracy And Efficiency Evidence

Frozen evidence moved out of the Prism product repository on 2026-09-06.
The product keeps reports only. No benchmark was rerun for this relocation.

## Provenance

- Original Prism branch: `cand-search-context`, HEAD `e855442`.
- Original large commit: `ebda175`, followed by `e855442`.
- The snapshot also includes the completed, previously uncommitted guidance
  comparison and its updated implementation report and validation index.
- Harness baseline for this archive: research `552aa94`.
- Product-only equivalents: `e245668` and `7169b4a`, based on Prism `a1c7aa6`.
- `archive-manifest.json` records SHA-256 for all 638 copied files. All 594
  checks in the six original checksum inventories remain valid.

`artifacts/` preserves the original `docs/accuracy-efficiency-candidate/` tree,
byte-for-byte, excluding Python caches. `source-reports/` holds the original
top-level proposal and implementation report before their links were relocated.
Old commit names, absolute paths, and "uncommitted" statements are historical
provenance, not the current status of the cleaned product branch.

The original proposal also cited 18 local-only records already in research:
16 wide-bed records and two Grafana gate records. Their unchanged copies are
under `artifacts/legacy-references/`, with their source paths in the manifest.
They are historical proposal inputs, not additional new model executions.
The other 620 files came from Prism; no unrelated research run was staged.

## Reports

- [Jackson four-way pilot](artifacts/four-way-2026-09-06/REPORT.md)
- [24-cell native/Prism panel](artifacts/panel-2026-09-06/REPORT.md)
- [Eight-cell evidence-delivery comparison](artifacts/evidence-delivery-2026-09-06/comparison/REPORT.md)
- [Eight-cell guidance comparison](artifacts/routing-2026-09-06/comparison/REPORT.md)

These are distinct experiments with different controls, not cumulative savings.
The latest study retains 100% recall/precision but fails both efficiency targets:
11.1% median paired token saving and 21.4% aggregate estimated cost saving.

## Offline Verification

From this directory, using Python 3 and its standard library:

```sh
python3 -B verify_archive.py
```

This command is relocation-aware and read-only. It checks every copied byte and
original checksum, recomputes the three multi-task study summaries (40 cells),
and re-scores the 16 before/after answers with the frozen scorer. It also checks
their raw Codex usage and fixed-rate cost calculations. No model, API, installed
Prism binary, original checkout, or temporary corpus is required.

The original `run_*.py`, `archive*.py`, and probe files are frozen historical
sources, not portable launch commands. Some infer the old Prism directory layout
or reference original absolute paths. Do not run them in place or rewrite their
pinned manifests to accommodate relocation. A future experiment needs a new
runner/protocol that accepts explicit repository and binary paths, a new output
directory, and fresh identities. Original temporary binaries are identified by
hash but are not included in this archive.

The original offline unit tests can also be run on the originating machine:

```sh
python3 -B -m unittest discover -s artifacts/panel-2026-09-06 -p 'test_*.py'
python3 -B -m unittest discover -s artifacts/evidence-delivery-2026-09-06/comparison -p 'test_*.py'
python3 -B -m unittest discover -s artifacts/routing-2026-09-06/comparison -p 'test_*.py'
```

Those historical runner tests still import the original absolute harness path.
Use `verify_archive.py` for independent offline replay on another checkout.
