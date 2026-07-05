# Python change-impact oracle (Jedi)

The Python sibling of `../java-oracle` (Spoon) and `../ts-oracle` (ts-morph):
given `Type.method`, emits every site that must change if that method's
signature changes — the declaration, every override in the subtype closure
(AST-based transitive subclasses), and every call site Jedi's type inference
resolves to a family member. Name matching is never used: a call to an
unrelated same-named method on a different type resolves elsewhere and is
dropped. Production sources only; tests excluded.

```sh
python3 -m venv venv && venv/bin/pip install jedi
venv/bin/python oracle.py \
  --src ~/gvg-corpus/django/django --repo ~/gvg-corpus/django \
  --target 'BaseDatabaseOperations.quote_name' --out gt.json
```

Site format: `<repo-relative-path>:<enclosing-def-name>` (harness `Site` form).
`--index idx.json` emits a line→name index instead (same shape as the Spoon
one, for line-number normalization).

## Known limitation (documented in the paper)

Jedi cannot follow dynamic multi-hop attribute chains
(`self.connection.ops.quote_name(...)`). For the Django task it found 23 of
32 GT sites; the 9 callers reaching the target through `connection.ops` were
found by the Grove engine and **manually verified** before being added to the
ground truth. Dynamically typed corpora need this manual-verification step;
the statically typed oracles (Spoon, ts-morph) do not.
