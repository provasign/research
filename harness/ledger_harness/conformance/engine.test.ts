import { test } from "node:test";
import assert from "node:assert/strict";

import { PricingEngine } from "../src/pricing.ts";
import { cls, TENANT, stubRule } from "./_support.ts";

test("[t01_core] price sums qty * unit into subtotal", () => {
  const ctx = new PricingEngine([]).price(TENANT, [
    { sku: "a", qty: 2, unit: 1500 },
    { sku: "b", qty: 3, unit: 1000 },
  ]);
  assert.equal(ctx.subtotal, 6000);
});

test("[t01_core] price starts total equal to subtotal", () => {
  const ctx = new PricingEngine([]).price(TENANT, [{ sku: "a", qty: 4, unit: 250 }]);
  assert.equal(ctx.total, 1000);
  assert.equal(ctx.total, ctx.subtotal);
});

test("[t01_core] price of no items is zero", () => {
  const ctx = new PricingEngine([]).price(TENANT, []);
  assert.equal(ctx.subtotal, 0);
  assert.equal(ctx.total, 0);
});

test("[t01_core] price starts with empty notes and carries the tenant and items", () => {
  const items = [{ sku: "a", qty: 1, unit: 100 }];
  const ctx = new PricingEngine([]).price(TENANT, items);
  assert.deepEqual(ctx.notes, []);
  assert.equal(ctx.tenant, TENANT);
  assert.deepEqual(ctx.items, items);
});

test("[t01_core] price folds the rules in list order", () => {
  const forward = new PricingEngine([
    stubRule("add", (t) => t + 1000),
    stubRule("half", (t) => t / 2),
  ]).price(TENANT, [{ sku: "a", qty: 1, unit: 1000 }]);
  const reversed = new PricingEngine([
    stubRule("half", (t) => t / 2),
    stubRule("add", (t) => t + 1000),
  ]).price(TENANT, [{ sku: "a", qty: 1, unit: 1000 }]);
  assert.equal(forward.total, 1000);
  assert.equal(reversed.total, 1500);
});

test("[t01_core] price accumulates every rule's note in order", () => {
  const ctx = new PricingEngine([
    stubRule("one", (t) => t),
    stubRule("two", (t) => t),
  ]).price(TENANT, [{ sku: "a", qty: 1, unit: 10 }]);
  assert.deepEqual(ctx.notes, ["one", "two"]);
});

test("[t01_core] rules never change the subtotal the engine computed", async () => {
  const Tax = await cls("../src/rules/tax.ts", "TaxRule");
  const Flat = await cls("../src/rules/flat-discount.ts", "FlatDiscountRule");
  const ctx = new PricingEngine([new Tax(0.2), new Flat(500)]).price(TENANT, [
    { sku: "a", qty: 1, unit: 10000 },
  ]);
  assert.equal(ctx.subtotal, 10000);
  assert.equal(ctx.total, 11500);
});

test("[t01_core] an engine with no rules leaves the total at the subtotal", () => {
  const ctx = new PricingEngine([]).price(TENANT, [{ sku: "a", qty: 7, unit: 111 }]);
  assert.equal(ctx.total, 777);
});

test("[t08_minor_units] a realistic fold stays in whole minor units", async () => {
  const Tiered = await cls("../src/rules/tiered.ts", "TieredPricingRule");
  const Pct = await cls("../src/rules/percent-discount.ts", "PercentDiscountRule");
  const Tax = await cls("../src/rules/tax.ts", "TaxRule");
  const ctx = new PricingEngine([new Tiered(), new Pct(0.1), new Tax(0.08)]).price(TENANT, [
    { sku: "a", qty: 10, unit: 9900 },
    { sku: "b", qty: 1, unit: 25000 },
  ]);
  assert.equal(ctx.subtotal, 124000);
  assert.ok(Number.isInteger(ctx.total));
  assert.equal(ctx.total, 108475);
});
