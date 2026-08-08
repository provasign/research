// t10: the journal and its policies moved to src/ledger/, and the old paths
// must be gone — not left as re-export shims.
import { test } from "node:test";
import assert from "node:assert/strict";

import { existsSync } from "node:fs";
import { cls, clsUnder, POLICY_DIR, repoPath } from "./_support.ts";

test("[t10_rename_move] Journal lives at src/ledger/journal.ts", async () => {
  const J = await cls("../src/ledger/journal.ts", "Journal");
  assert.equal(typeof J, "function");
});

test("[t10_rename_move] the three policies live under src/ledger/policies/", async () => {
  for (const name of ["SignPolicy", "RoundPolicy", "ClampPolicy"]) {
    const C = await clsUnder(POLICY_DIR, name);
    assert.equal(typeof C, "function", `${name} must be reachable under src/ledger/policies/`);
  }
});

test("[t10_rename_move] importing src/journal.ts fails", async () => {
  await assert.rejects(
    async () => {
      await import("../src/journal.ts");
    },
    "importing ../journal.ts must fail — the module was deleted, not shimmed",
  );
});

test("[t10_rename_move] src/journal.ts no longer exists", () => {
  assert.equal(existsSync(repoPath("../src/journal.ts")), false);
});

test("[t10_rename_move] src/policies/ no longer exists", () => {
  assert.equal(existsSync(repoPath("../src/policies")), false);
});

test("[t10_rename_move] no policy module is importable from the old src/policies/ path", async () => {
  for (const file of ["sign.ts", "round.ts", "clamp.ts"]) {
    await assert.rejects(
      async () => {
        await import(`../src/policies/${file}`);
      },
      `../src/policies/${file} must be gone`,
    );
  }
});
