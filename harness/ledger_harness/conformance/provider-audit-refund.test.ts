// t07 (compliance): every provider must audit refunds. One test per provider.
import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { asAudit, cls, PROVIDERS } from "./_support.ts";

const AT = 777;

function fixture(C: any): { provider: any; log: any } {
  const clock = new FixedClock(AT);
  const log = new AuditLog(clock);
  return { provider: new C(clock, log), log };
}

function only(log: any, action: string): any[] {
  return log.entries().filter((e: any) => e.action === action).map(asAudit);
}

for (const p of PROVIDERS) {
  test(`[t07_provider_audit] ${p.cls} audits a refund`, async () => {
    const C = await cls(p.spec, p.cls);
    const { provider, log } = fixture(C);
    const reference = `${p.ref}-inv-1`;
    const result = provider.refund(reference, 2500);
    assert.equal(result.message, "refunded");
    assert.deepEqual(only(log, "refund"), [
      { actor: "payment", action: "refund", detail: `${p.id}:${reference}`, at: AT },
    ]);
  });
}

