import { test } from "node:test";
import assert from "node:assert/strict";

import { clsUnder, VALIDATOR_DIR } from "./_support.ts";

const invoice = (over: Record<string, unknown> = {}): any => ({
  id: "inv-1",
  tenantId: "t-1",
  items: [{ sku: "a", qty: 1, unit: 100 }],
  subtotal: 100,
  total: 100,
  issuedAt: 0,
  ...over,
});

const tenant = (over: Record<string, unknown> = {}): any => ({
  id: "t-1",
  name: "Acme",
  plan: "pro",
  ...over,
});

const item = (over: Record<string, unknown> = {}): any => ({
  sku: "a",
  qty: 1,
  unit: 100,
  ...over,
});

function sorted(xs: string[]): string[] {
  return [...xs].sort();
}

/* ------------------------------------------------------- InvoiceValidator */

test("[t04_journal] InvoiceValidator has id invoice", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "InvoiceValidator");
  assert.equal(new C().id, "invoice");
});

test("[t04_journal] InvoiceValidator accepts a valid invoice", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "InvoiceValidator");
  assert.deepEqual(new C().validate(invoice()), []);
});

test("[t04_journal] InvoiceValidator reports missing id", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "InvoiceValidator");
  assert.deepEqual(new C().validate(invoice({ id: "" })), ["missing id"]);
});

test("[t04_journal] InvoiceValidator reports no items", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "InvoiceValidator");
  assert.deepEqual(new C().validate(invoice({ items: [] })), ["no items"]);
});

test("[t04_journal] InvoiceValidator reports both problems at once", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "InvoiceValidator");
  assert.deepEqual(sorted(new C().validate(invoice({ id: "", items: [] }))), [
    "missing id",
    "no items",
  ]);
});

/* -------------------------------------------------------- TenantValidator */

test("[t04_journal] TenantValidator has id tenant", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "TenantValidator");
  assert.equal(new C().id, "tenant");
});

test("[t04_journal] TenantValidator accepts every known plan", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "TenantValidator");
  const v = new C();
  for (const plan of ["free", "pro", "enterprise"]) {
    assert.deepEqual(v.validate(tenant({ plan })), [], `${plan} must be valid`);
  }
});

test("[t04_journal] TenantValidator reports missing id", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "TenantValidator");
  assert.deepEqual(new C().validate(tenant({ id: "" })), ["missing id"]);
});

test("[t04_journal] TenantValidator reports a bad plan", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "TenantValidator");
  assert.deepEqual(new C().validate(tenant({ plan: "platinum" })), ["bad plan"]);
});

test("[t04_journal] TenantValidator rejects an empty plan", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "TenantValidator");
  assert.deepEqual(new C().validate(tenant({ plan: "" })), ["bad plan"]);
});

test("[t04_journal] TenantValidator reports both problems at once", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "TenantValidator");
  assert.deepEqual(sorted(new C().validate(tenant({ id: "", plan: "x" }))), [
    "bad plan",
    "missing id",
  ]);
});

/* ------------------------------------------------------ LineItemValidator */

test("[t04_journal] LineItemValidator has id line-item", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.equal(new C().id, "line-item");
});

test("[t04_journal] LineItemValidator accepts a valid line item", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.deepEqual(new C().validate(item()), []);
});

test("[t04_journal] LineItemValidator rejects a zero quantity", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.deepEqual(new C().validate(item({ qty: 0 })), ["bad qty"]);
});

test("[t04_journal] LineItemValidator rejects a negative quantity", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.deepEqual(new C().validate(item({ qty: -3 })), ["bad qty"]);
});

test("[t04_journal] LineItemValidator rejects a negative unit price", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.deepEqual(new C().validate(item({ unit: -1 })), ["bad unit"]);
});

test("[t04_journal] LineItemValidator accepts a zero unit price", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.deepEqual(new C().validate(item({ unit: 0 })), []);
});

test("[t04_journal] LineItemValidator reports both problems at once", async () => {
  const C = await clsUnder(VALIDATOR_DIR, "LineItemValidator");
  assert.deepEqual(sorted(new C().validate(item({ qty: 0, unit: -5 }))), [
    "bad qty",
    "bad unit",
  ]);
});
