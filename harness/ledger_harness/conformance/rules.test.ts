import { test } from "node:test";
import assert from "node:assert/strict";

import { CollectingTrace } from "../src/pricing.ts";
import { cls, RULES, makeCtx, frozenCtx, TENANT, ENTERPRISE } from "./_support.ts";

/** The turn that pins each rule's numeric behaviour. */
function turnOf(id: string): string {
  return id === "tiered" || id === "rounding" ? "t08_minor_units" : "t01_core";
}

for (const r of RULES) {
  test(`[t01_core] ${r.cls} exposes id "${r.id}"`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    assert.equal(rule.id, r.id);
  });

  test(`[${turnOf(r.id)}] ${r.cls} moves the total as specified`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    const ctx = r.moving();
    const out = rule.apply(ctx, new CollectingTrace());
    assert.equal(out.total, r.movingTo);
  });

  test(`[t01_core] ${r.cls} appends exactly its one note`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    const ctx = r.moving();
    ctx.notes = ["earlier"];
    const out = rule.apply(ctx, new CollectingTrace());
    assert.deepEqual(out.notes, ["earlier", r.note]);
  });

  test(`[t01_core] ${r.cls} never changes subtotal`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    const ctx = r.moving();
    const out = rule.apply(ctx, new CollectingTrace());
    assert.equal(out.subtotal, ctx.subtotal);
  });

  test(`[t01_core] ${r.cls} returns a new context and does not mutate its argument`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    const before = r.moving();
    const frozen = Object.freeze({ ...before, notes: Object.freeze([...before.notes]) });
    const out = rule.apply(frozen, new CollectingTrace());
    assert.notEqual(out, frozen, "apply must return a new context object");
    assert.equal(frozen.total, before.total, "the input context must be untouched");
    assert.deepEqual(frozen.notes, before.notes);
  });

  if (r.still !== undefined) {
    const still = r.still;
    test(`[${turnOf(r.id)}] ${r.cls} leaves the total alone outside its condition`, async () => {
      const C = await cls(r.spec, r.cls);
      const rule = new C(...r.args);
      const ctx = still();
      const out = rule.apply(ctx, new CollectingTrace());
      assert.equal(out.total, ctx.total);
      assert.deepEqual(out.notes, [r.note]);
    });
  }
}

/* ------------------------------------------- rule specifics beyond the table */

test("[t01_core] FlatDiscountRule can drive a total negative", async () => {
  const C = await cls("../src/rules/flat-discount.ts", "FlatDiscountRule");
  const out = new C(15000).apply(makeCtx({ total: 10000 }), new CollectingTrace());
  assert.equal(out.total, -5000);
});

test("[t01_core] PercentDiscountRule with pct 0 leaves the total alone", async () => {
  const C = await cls("../src/rules/percent-discount.ts", "PercentDiscountRule");
  const out = new C(0).apply(makeCtx({ total: 9999 }), new CollectingTrace());
  assert.equal(out.total, 9999);
});

test("[t01_core] PercentDiscountRule rounds to a whole cent", async () => {
  const C = await cls("../src/rules/percent-discount.ts", "PercentDiscountRule");
  const out = new C(0.1).apply(makeCtx({ total: 999 }), new CollectingTrace());
  assert.ok(Number.isInteger(out.total));
  assert.equal(out.total, 899);
});

test("[t01_core] VolumeDiscountRule triggers exactly at the quantity threshold", async () => {
  const C = await cls("../src/rules/volume-discount.ts", "VolumeDiscountRule");
  const rule = new C(10, 0.5);
  const at = rule.apply(
    makeCtx({ total: 10000, items: [{ sku: "a", qty: 6, unit: 1 }, { sku: "b", qty: 4, unit: 1 }] }),
    new CollectingTrace(),
  );
  assert.equal(at.total, 5000, "total item qty 10 must trigger");
});

test("[t08_minor_units] TieredPricingRule uses the 100000 cent top tier", async () => {
  const C = await cls("../src/rules/tiered.ts", "TieredPricingRule");
  const rule = new C();
  const at = rule.apply(makeCtx({ subtotal: 100000, total: 100000 }), new CollectingTrace());
  const below = rule.apply(makeCtx({ subtotal: 99999, total: 100000 }), new CollectingTrace());
  assert.equal(at.total, 90000);
  assert.equal(below.total, 95000);
});

test("[t08_minor_units] TieredPricingRule uses the 50000 cent middle tier", async () => {
  const C = await cls("../src/rules/tiered.ts", "TieredPricingRule");
  const rule = new C();
  const at = rule.apply(makeCtx({ subtotal: 50000, total: 100000 }), new CollectingTrace());
  const below = rule.apply(makeCtx({ subtotal: 49999, total: 100000 }), new CollectingTrace());
  assert.equal(at.total, 95000);
  assert.equal(below.total, 100000);
});

test("[t08_minor_units] TieredPricingRule tiers off subtotal, not total", async () => {
  const C = await cls("../src/rules/tiered.ts", "TieredPricingRule");
  const out = new C().apply(
    makeCtx({ subtotal: 100000, total: 20000 }),
    new CollectingTrace(),
  );
  assert.equal(out.total, 18000);
});

test("[t01_core] MinimumChargeRule leaves a total exactly at the floor alone", async () => {
  const C = await cls("../src/rules/minimum-charge.ts", "MinimumChargeRule");
  const out = new C(5000).apply(makeCtx({ total: 5000 }), new CollectingTrace());
  assert.equal(out.total, 5000);
});

test("[t01_core] SurchargeRule adds to a negative total", async () => {
  const C = await cls("../src/rules/surcharge.ts", "SurchargeRule");
  const out = new C(750).apply(makeCtx({ total: -1000 }), new CollectingTrace());
  assert.equal(out.total, -250);
});

test("[t08_minor_units] RoundingRule rounds a fractional minor-unit total to an integer", async () => {
  const C = await cls("../src/rules/rounding.ts", "RoundingRule");
  const rule = new C();
  assert.equal(rule.apply(makeCtx({ total: 1000.4 }), new CollectingTrace()).total, 1000);
  assert.equal(rule.apply(makeCtx({ total: 1000.6 }), new CollectingTrace()).total, 1001);
});

test("[t08_minor_units] RoundingRule rounds halves away from zero", async () => {
  const C = await cls("../src/rules/rounding.ts", "RoundingRule");
  const rule = new C();
  assert.equal(rule.apply(makeCtx({ total: 1000.5 }), new CollectingTrace()).total, 1001);
  assert.equal(rule.apply(makeCtx({ total: -1000.5 }), new CollectingTrace()).total, -1001);
});

test("[t01_core] PlanCreditRule only credits the enterprise plan", async () => {
  const C = await cls("../src/rules/plan-credit.ts", "PlanCreditRule");
  const rule = new C(1500);
  const free = rule.apply(
    makeCtx({ tenant: { ...TENANT, plan: "free" }, total: 10000 }),
    new CollectingTrace(),
  );
  const ent = rule.apply(makeCtx({ tenant: ENTERPRISE, total: 10000 }), new CollectingTrace());
  assert.equal(free.total, 10000);
  assert.equal(ent.total, 8500);
});

test("[t01_core] TaxRule adds tax on top of the total", async () => {
  const C = await cls("../src/rules/tax.ts", "TaxRule");
  const out = new C(0.075).apply(makeCtx({ total: 20000 }), new CollectingTrace());
  assert.equal(out.total, 21500);
  assert.ok(Number.isInteger(out.total));
});

test("[t01_core] TaxRule with rate 0 leaves the total alone", async () => {
  const C = await cls("../src/rules/tax.ts", "TaxRule");
  const out = new C(0).apply(makeCtx({ total: 20000 }), new CollectingTrace());
  assert.equal(out.total, 20000);
});

test("[t01_core] CapRule leaves a total exactly at the ceiling alone", async () => {
  const C = await cls("../src/rules/cap.ts", "CapRule");
  const out = new C(9000).apply(makeCtx({ total: 9000 }), new CollectingTrace());
  assert.equal(out.total, 9000);
});

test("[t01_core] CapRule never raises a total", async () => {
  const C = await cls("../src/rules/cap.ts", "CapRule");
  const out = new C(9000).apply(frozenCtx({ total: 10 }), new CollectingTrace());
  assert.equal(out.total, 10);
});
