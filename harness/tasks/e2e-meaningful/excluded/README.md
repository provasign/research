# Excluded after leak audit

- pallets__click__pr3637 — excluded 2026-08-30: design lottery, 1 resolve
  in 18 trials. Hidden tests pin an arbitrary PR-invented wire format
  (`type\nvalue\nhelp` with `_` empty-help sentinel) that the repo's own
  bash/fish precedents point away from; every trial builds a correct
  completer and fails on the format guess. See tasks-e2e/excluded/README.md.

- pallets__werkzeug__pr3109 — the issue body contains the fix itself
  (maintainer spells out "check intersection of self.methods", naming the
  exact field and predicate to change), and it is a dependent follow-up to
  pr3038 which is already in the bed. Solution leakage + task coupling.
