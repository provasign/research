# Excluded tasks

Excluded 2026-08-30 after failure autopsies. Criterion: a task is excluded
only for a *defect* — unsolvable from its own inputs or mis-scored — never
for merely being hard. (pr705 and pr6018 stay in the bed: always-failing
but fair.)

- FasterXML__jackson-databind__pr6035 — problem statement is 35 chars
  ("Fix #6031, @JsonAlias/@JsonIgnore"); the referenced issue body is not
  in the task, and solving requires analogy to a prior fix the agent has
  no pointer to. Underspecified: unsolvable from its inputs.
- FasterXML__jackson-databind__pr6113 — the PR bundles a fix unrelated to
  the problem statement and fail_to_pass scores it; a correct fix for the
  stated problem cannot resolve. Mis-scored.
- pallets__click__pr3637 — design lottery: 1 resolve in 18 trials across
  all arms/binaries. Every trial builds a correct PowerShell completer;
  the hidden tests pin an arbitrary PR-invented wire format
  (`type\nvalue\nhelp`, `_` empty-help sentinel) that the repo's own
  precedents (bash `type,value`, fish `type,value\thelp`) point away
  from. Scores format-guessing luck, not capability.

Manifests (java-smoke, java-bounded) were swept of these ids the same day.
