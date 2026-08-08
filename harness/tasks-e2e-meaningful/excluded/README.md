# Excluded after leak audit

- pallets__werkzeug__pr3109 — the issue body contains the fix itself
  (maintainer spells out "check intersection of self.methods", naming the
  exact field and predicate to change), and it is a dependent follow-up to
  pr3038 which is already in the bed. Solution leakage + task coupling.
