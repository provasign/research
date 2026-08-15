# redirect-run1 is INVALID — do not use

The /tmp repo cache was corrupted by macOS's periodic /tmp cleaner at
2026-08-15 00:00 (files untouched 3+ days deleted, directories kept: every
cached clone lost .git/HEAD and .git/config). This run's copy was made at
00:10 from the corrupted cache: `git checkout` to the base commit silently
failed, the agent ran against clone-time working-tree state (NOT
Kinto-3566's base commit) with every git command erroring — which explains
its 64-turn/$1.74 spiral and 0-byte diff. No conclusion about the
"redirect" steering variant can be drawn from it. The transcript is kept
only as evidence of the failure mode.

Harness fixes that came out of this (swebench_ab.py): cache moved to
~/.cache/prism-research (off /tmp), cache integrity re-clone check,
rev-parse HEAD == base_commit guard ("refusing to run an agent on the
wrong code"), and — found during the same audit — per-cell ref-stripped
local clones replacing shared-ref worktrees, closing the gold-fix
git-archaeology hole (21/228 benchmark cells had run `git log --all` +
`git show <sha>`; one provably showed its own task's fix commit).
