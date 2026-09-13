# Prism enclosing-body benchmark gate — 2026-09-13

The Prism candidate adds `include_bodies` to the locating search call. It can
deliver the exact bodies of up to two visible, nonoverlapping hits (160 lines,
10 KiB each, 4,000 estimated tokens total). Small bodies are also included by
default in compact MCP search when the existing first-result rule does not
apply. CLI `--include-bodies`, legacy MCP, and compact MCP use the same handler
option. Scope and completeness disclosures are preserved. A body beyond the
cap remains a locator.

The research harness now indexes Prism op sequences, second-call and follow-up
read/lookup flags, native discovery and edit-prerequisite Reads, whole-file
Reads, KiB read, edits, turns, cost, resolution, audited validity, and blocked
network attempts. The `run` scheduler now shares one bounded pool across task
and trial waves; `--concurrency` applies even to a single-arm run. See
[`BENCH.md`](BENCH.md) for the invocation and audit policy.

## Calibration evidence, not a product result

One paired Click cell is preserved at
`/private/tmp/prism-enclosing-smoke-click-20260913`. Both arms were audited
valid and resolved. Native: 29 turns, $0.4679, 6 Reads, 12.096 KiB read.
Prism: 16 turns, $0.3011, 3 Reads, 18.163 KiB read, one Prism search and no
follow-up Prism call. This is **one trial on a public merged PR**. The agent's
search targeted `class CliRunner` (393 lines) and `isolation stdout` (no
match), so the new body cap delivered **no source body** in that cell. The
numbers cannot be attributed to the candidate or used as its success claim.

A separate post-cutoff private-repo pilot was run at
`/private/tmp/prism-enclosing-private-pilot-20260913`. It was 0/2 resolved;
the Prism arm timed out. The initial network audit also mislabeled Python test
fixtures containing the text `curl ...` as executed fetches. The classifier
now separates Python code literals from obvious subprocess calls; all five
recorded commands classify as **suspect**, not definite. The historical
measurements remain unchanged. That hard, locally assembled task and its
nonportable corpus were removed from the runnable suite; the recorded run
remains diagnostic evidence.

## Decision gate

Do not call this candidate an improvement from the smoke. Before a product
decision, assemble and validate eight tasks whose fixes the agents could not
have memorized, with an independent fail-to-pass oracle and at least one task
in the useful middle of the difficulty range. The current `e2e` suite is
public merged PRs, and its urllib3 pilot was 0/6; it does not meet that gate.
Pre-register native discovery Reads, KiB read, whole-file Reads, and cost per
resolved cell. Run the complete set with native and Prism arms at three or
more trials, and compare the released binary with the candidate if the
question is whether this change helped. Count only audited-valid cells;
inspect thinking for upstream-fix hunting and network attempts. A task that
does not discriminate, an invalid audit, or a flat/worse cost per resolved cell
is a reason to stop the batch and repair the task set, not to rerun until a
favorable result appears.
