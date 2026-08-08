import { test } from "node:test";
import assert from "node:assert/strict";

import { ProviderRegistry } from "../src/payments.ts";
import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { cls, PROVIDERS, req, stubProvider } from "./_support.ts";

async function allProviders(): Promise<any[]> {
  const clock = new FixedClock(1);
  const log = new AuditLog(clock);
  const out: any[] = [];
  for (const p of PROVIDERS) {
    const C = await cls(p.spec, p.cls);
    out.push(new C(clock, log));
  }
  return out;
}

test("[t02_payments] ids() returns every provider id sorted ascending", async () => {
  const registry = new ProviderRegistry(await allProviders());
  const expected = PROVIDERS.map((p) => p.id).sort();
  assert.deepEqual(registry.ids(), expected);
});

test("[t02_payments] ids() sorts regardless of construction order", () => {
  const registry = new ProviderRegistry([
    stubProvider("zeta", true),
    stubProvider("alpha", true),
    stubProvider("mid", true),
  ]);
  assert.deepEqual(registry.ids(), ["alpha", "mid", "zeta"]);
});

test("[t02_payments] ids() of an empty registry is empty", () => {
  assert.deepEqual(new ProviderRegistry([]).ids(), []);
});

test("[t02_payments] get() returns the provider with that id", () => {
  const a = stubProvider("alpha", true);
  const b = stubProvider("beta", true);
  const registry = new ProviderRegistry([a, b]);
  assert.equal(registry.get("beta"), b);
});

test("[t02_payments] get() of an unknown id is undefined", () => {
  const registry = new ProviderRegistry([stubProvider("alpha", true)]);
  assert.equal(registry.get("nope"), undefined);
});

test("[t02_payments] charge() delegates to the named provider", () => {
  const registry = new ProviderRegistry([
    stubProvider("alpha", true),
    stubProvider("beta", false),
  ]);
  assert.deepEqual(registry.charge("alpha", req()), {
    ok: true,
    providerId: "alpha",
    reference: "alpha-inv-1",
    message: "ok",
  });
});

test("[t02_payments] charge() relays a provider's rejection", () => {
  const registry = new ProviderRegistry([stubProvider("beta", false)]);
  const r = registry.charge("beta", req());
  assert.equal(r.ok, false);
  assert.equal(r.message, "invalid request");
});

test("[t02_payments] charge() with an unknown id reports no such provider", () => {
  const registry = new ProviderRegistry([stubProvider("alpha", true)]);
  const r = registry.charge("ghost", req());
  assert.equal(r.ok, false);
  assert.equal(r.message, "no such provider");
});

test("[t02_payments] charge() on an empty registry reports no such provider", () => {
  const r = new ProviderRegistry([]).charge("anything", req());
  assert.equal(r.ok, false);
  assert.equal(r.message, "no such provider");
});
