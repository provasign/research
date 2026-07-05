# TypeScript change-impact oracle (ts-morph)

The TS sibling of `../java-oracle` (Spoon): given `Type#method`, emits every
site that must change if that method's signature changes — the declaration,
every implementation/override (compiler-resolved via the TypeScript language
service, never name matching), and every call site that binds to a family
member, attributed to its enclosing method/function. Production sources only
(`src/`).

```sh
npm ci
node oracle.mjs --project ~/gvg-corpus/typeorm/tsconfig.json \
  --repo ~/gvg-corpus/typeorm \
  --target 'Driver#escape' --out gt.json
```

`--index idx.json` emits a line→name index (same JSON shape as the Spoon one)
for line-number normalization; the committed
`../java-oracle/typeorm-lineindex.json` was generated this way.

Used for the TypeORM `Driver.escape` task (37 GT sites) — the corpus behind
the paper's controlled ceiling-intervention result.
