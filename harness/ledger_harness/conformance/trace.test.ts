import { test } from "node:test";
import assert from "node:assert/strict";

import { CollectingTrace, PricingEngine } from "../src/pricing.ts";
import { asStep, cls, RULES, TENANT, stubRule } from "./_support.ts";

/* ------------------------------------------------------------------ *
 * one test per rule: every rule records exactly one trace step
 * ------------------------------------------------------------------ */

for (const r of RULES) {
  test(`[t06_trace_param] ${r.cls} records exactly one trace step`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    const trace = new CollectingTrace();
    const ctx = r.moving();
    const out = rule.apply(ctx, trace);
    assert.deepEqual(trace.steps().map(asStep), [
      { ruleId: r.id, before: ctx.total, after: out.total },
    ]);
  });
}

/* one test per rule that can leave the total alone: it still records */

for (const r of RULES) {
  if (r.still === undefined) continue;
  const still = r.still;
  test(`[t06_trace_param] ${r.cls} records a step even when the total is unchanged`, async () => {
    const C = await cls(r.spec, r.cls);
    const rule = new C(...r.args);
    const trace = new CollectingTrace();
    const ctx = still();
    const out = rule.apply(ctx, trace);
    assert.equal(out.total, ctx.total, "fixture must be an unchanged-total case");
    assert.deepEqual(trace.steps().map(asStep), [
      { ruleId: r.id, before: ctx.total, after: ctx.total },
    ]);
  });
}

/* ------------------------------------------------------------ CollectingTrace */

test("[t06_trace_param] CollectingTrace starts with no steps", () => {
  assert.deepEqual(new CollectingTrace().steps(), []);
});

test("[t06_trace_param] CollectingTrace keeps steps in record order", () => {
  const t = new CollectingTrace();
  t.record("a", 1, 2);
  t.record("b", 2, 3);
  t.record("c", 3, 4);
  assert.deepEqual(t.steps().map(asStep), [
    { ruleId: "a", before: 1, after: 2 },
    { ruleId: "b", before: 2, after: 3 },
    { ruleId: "c", before: 3, after: 4 },
  ]);
});

test("[t06_trace_param] CollectingTrace.steps returns a copy", () => {
  const t = new CollectingTrace();
  t.record("a", 1, 2);
  const first = t.steps();
  const second = t.steps();
  assert.notEqual(first, second);
  first.push({ ruleId: "x", before: 0, after: 0 });
  assert.equal(t.steps().length, 1);
});

test("[t06_trace_param] CollectingTrace records a step whose before equals after", () => {
  const t = new CollectingTrace();
  t.record("noop", 500, 500);
  assert.deepEqual(t.steps().map(asStep), [{ ruleId: "noop", before: 500, after: 500 }]);
});

/* -------------------------------------------------------------- the engine */

test("[t06_trace_param] price passes the trace to every rule, in fold order", () => {
  const engine = new PricingEngine([
    stubRule("one", (t) => t + 100),
    stubRule("two", (t) => t + 10),
    stubRule("three", (t) => t + 1),
  ]);
  const trace = new CollectingTrace();
  engine.price(TENANT, [{ sku: "a", qty: 1, unit: 1000 }], trace);
  assert.deepEqual(trace.steps().map(asStep), [
    { ruleId: "one", before: 1000, after: 1100 },
    { ruleId: "two", before: 1100, after: 1110 },
    { ruleId: "three", before: 1110, after: 1111 },
  ]);
});

test("[t06_trace_param] price without a trace returns an identical context", async () => {
  const Tax = await cls("../src/rules/tax.ts", "TaxRule");
  const Cap = await cls("../src/rules/cap.ts", "CapRule");
  const engine = new PricingEngine([new Tax(0.1), new Cap(500000)]);
  const items = [{ sku: "a", qty: 3, unit: 12345 }];
  const withTrace = engine.price(TENANT, items, new CollectingTrace());
  const without = engine.price(TENANT, items);
  assert.deepEqual(without, withTrace);
});

test("[t06_trace_param] price without a trace does not throw on a rule that records", () => {
  const engine = new PricingEngine([stubRule("one", (t) => t * 2)]);
  const ctx = engine.price(TENANT, [{ sku: "a", qty: 1, unit: 50 }]);
  assert.equal(ctx.total, 100);
});

test("[t06_trace_param] a fresh trace on a second price call sees only that call's steps", () => {
  const engine = new PricingEngine([stubRule("one", (t) => t + 1)]);
  const first = new CollectingTrace();
  engine.price(TENANT, [{ sku: "a", qty: 1, unit: 10 }], first);
  const second = new CollectingTrace();
  engine.price(TENANT, [{ sku: "a", qty: 1, unit: 10 }], second);
  assert.equal(first.steps().length, 1);
  assert.equal(second.steps().length, 1);
});

test("[t06_trace_param] the same trace accumulates across two price calls", () => {
  const engine = new PricingEngine([stubRule("one", (t) => t + 1)]);
  const trace = new CollectingTrace();
  engine.price(TENANT, [{ sku: "a", qty: 1, unit: 10 }], trace);
  engine.price(TENANT, [{ sku: "a", qty: 1, unit: 20 }], trace);
  assert.equal(trace.steps().length, 2);
});
