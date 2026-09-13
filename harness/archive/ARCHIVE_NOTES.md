# Archive notes

Scripts moved here are kept for history, not deleted. None of them are
imported by any live script (verified via repo-wide grep before archiving).
Path-relative fixes applied to the rest of the reorg were **not** applied to
these files — if one is ever resurrected, re-check its `Path(__file__)` /
`sys.path` assumptions (it still assumes it lives directly in `harness/`).

- **`_vb3.py`** — near-duplicate of `scoring/verify_bench.py`. Identical
  docstring and logic; the only differences are the target Prism binary
  (`/tmp/prism-v3` vs `/tmp/prism-task`) and the output directory
  (`runs/verify-bench-b3` vs `runs/verify-bench`). Leading-underscore,
  no references anywhere — a one-off rerun against a specific release
  candidate binary. Superseded by: `scoring/verify_bench.py`.

- **`run_local_hitool.py`** — explicitly superseded. Its replacement's own
  docstring (`runners/run_local_gstar.py`) says: "This replaces
  run_local_hitool.py (which used the Spoon-powered change_impact.py and was
  therefore tautological)." Superseded by: `runners/run_local_gstar.py`.

- **`change_impact.py`** — the Spoon-powered prototype `change_impact()` tool.
  Its only importer in the whole repo was `run_local_hitool.py` (archived
  above); `run_local_gstar.py` replaced that consumer with a call to the real
  `prism change-impact` engine instead of this tautological stand-in.
  Superseded by: `runners/run_local_gstar.py` (functionally) /
  `scoring/impact_oracle.py` (the real deterministic gate).

- **`proto_sqlite_change_impact.py`** — docstring says "Throwaway prototype:
  can a traversal over Grove's existing index (grove.db) reconstruct the
  Spoon-oracle ground truth for the 6 jackson tasks?" No references anywhere.
  Superseded by: the real engine (`prism change-impact`) as scored in
  `scoring/engine_comparison.py` / `scoring/ci_invariants.py`.

- **`score_grove_change_impact.py`** — UNCERTAIN, flagged rather than
  guessed. Old (2026-07-03) one-off script hardcoded to one machine's
  absolute paths (`/Users/tapabratapal/...`), scoring only the 6 jackson
  tasks against one `grove` binary via a single hardcoded task list. No
  references anywhere. Reads as an early prototype of what
  `scoring/engine_comparison.py` / `scoring/ci_invariants.py` later did more
  generally (many corpora, committed ground truth, CI-gated, argparse). No
  explicit "supersedes" text was found, so this is an inference, not a
  confirmed fact.

- **`gate_evidence.py`** and **`gate_experiment.py`** — UNCERTAIN, flagged
  rather than guessed. Both are June-2026 two-turn "completeness gate"
  experiments (turn 1: text-only agent; gate: feed back graph-flagged sites;
  turn 2: agent revises). Neither is imported anywhere, and the mechanism
  does not appear to be reused verbatim by any later script. The general
  idea (measuring what a graph surfaces that an agent missed) reappears in
  spirit in `runners/ab_routing.py` and `runners/ab_gate.py`, but those are
  independent, more rigorous designs, not direct descendants — so this is
  a judgment call, not a documented supersession.
