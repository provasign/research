// t07 (compliance): every provider must write to the audit log it was
// constructed with, on BOTH charge paths. One test per provider per path so
// that the number of failures equals the number of providers missed.
import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { asAudit, cls, PROVIDERS } from "./_support.ts";

const AT = 4242;

function fixture(C: any): { provider: any; log: any } {
  const clock = new FixedClock(AT);
  const log = new AuditLog(clock);
  return { provider: new C(clock, log), log };
}

function only(log: any, action: string): any[] {
  return log.entries().filter((e: any) => e.action === action).map(asAudit);
}

/* ------------------------------------------------- successful charge path */

for (const p of PROVIDERS) {
  test(`[t07_provider_audit] ${p.cls} audits a successful charge`, async () => {
    const C = await cls(p.spec, p.cls);
    const { provider, log } = fixture(C);
    const result = provider.charge(p.good());
    assert.equal(result.ok, true, "fixture must be an accepted request");
    assert.deepEqual(only(log, "charge"), [
      { actor: "payment", action: "charge", detail: `${p.id}:inv-1`, at: AT },
    ]);
  });
}

/* --------------------------------------------------- rejected charge path */

for (const p of PROVIDERS) {
  const bad = p.bad;
  test(`[t07_provider_audit] ${p.cls} audits a rejected charge`, async () => {
    const C = await cls(p.spec, p.cls);
    const { provider, log } = fixture(C);
    if (bad === undefined) {
      // ManualProvider never rejects: the obligation is that the audit record
      // is written on every charge, which is what we check.
      const result = provider.charge({ ...p.good(), invoiceId: "inv-9" });
      assert.equal(result.ok, true);
      assert.deepEqual(only(log, "charge"), [
        { actor: "payment", action: "charge", detail: `${p.id}:inv-9`, at: AT },
      ]);
      return;
    }
    const result = provider.charge({ ...bad(), invoiceId: "inv-9" });
    assert.equal(result.ok, false, "fixture must be a rejected request");
    assert.deepEqual(only(log, "charge"), [
      { actor: "payment", action: "charge", detail: `${p.id}:inv-9`, at: AT },
    ]);
  });
}

