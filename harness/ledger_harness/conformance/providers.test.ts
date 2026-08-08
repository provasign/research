import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { cls, PROVIDERS, req } from "./_support.ts";

function build(C: any): any {
  return new C(new FixedClock(1000), new AuditLog(new FixedClock(1000)));
}

/* ------------------------------------------------- validate: accepted case */

for (const p of PROVIDERS) {
  test(`[${p.turn}] ${p.cls}.validate accepts a valid request`, async () => {
    const C = await cls(p.spec, p.cls);
    assert.equal(build(C).validate(p.good()), true);
  });
}

/* ------------------------------------------------- validate: rejected case */

for (const p of PROVIDERS) {
  if (p.bad === undefined) continue;
  const bad = p.bad;
  test(`[${p.turn}] ${p.cls}.validate rejects at its boundary`, async () => {
    const C = await cls(p.spec, p.cls);
    assert.equal(build(C).validate(bad()), false);
  });
}

test("[t02_payments] ManualProvider.validate is always true", async () => {
  const C = await cls("../src/providers/manual.ts", "ManualProvider");
  const p = build(C);
  assert.equal(p.validate(req({ token: "", amount: -1, tenantId: "", invoiceId: "" })), true);
  assert.equal(p.validate(req({ amount: 999999999 })), true);
});

/* --------------------------------------------------- charge: accepted path */

for (const p of PROVIDERS) {
  test(`[t02_payments] ${p.cls}.charge succeeds on a valid request`, async () => {
    const C = await cls(p.spec, p.cls);
    const r = build(C).charge(p.good());
    assert.deepEqual(r, {
      ok: true,
      providerId: p.id,
      reference: `${p.ref}-inv-1`,
      message: "ok",
    });
  });
}

/* --------------------------------------------------- charge: rejected path */

for (const p of PROVIDERS) {
  if (p.bad === undefined) continue;
  const bad = p.bad;
  test(`[t02_payments] ${p.cls}.charge rejects an invalid request`, async () => {
    const C = await cls(p.spec, p.cls);
    const r = build(C).charge(bad());
    assert.deepEqual(r, {
      ok: false,
      providerId: p.id,
      reference: "",
      message: "invalid request",
    });
  });
}

/* ----------------------------------------------------------------- refund */

for (const p of PROVIDERS) {
  test(`[t02_payments] ${p.cls}.refund returns a refunded result`, async () => {
    const C = await cls(p.spec, p.cls);
    const r = build(C).refund(`${p.ref}-inv-1`, 500);
    assert.deepEqual(r, {
      ok: true,
      providerId: p.id,
      reference: `${p.ref}-inv-1`,
      message: "refunded",
    });
  });
}
