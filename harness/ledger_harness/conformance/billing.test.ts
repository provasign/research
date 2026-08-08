import { test } from "node:test";
import assert from "node:assert/strict";

import { BillingService } from "../src/billing.ts";
import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { PricingEngine } from "../src/pricing.ts";
import { ProviderRegistry } from "../src/payments.ts";
import { Dispatcher } from "../src/notify.ts";
import { asAudit, cls, TENANT, stubChannel, stubProvider, stubRule } from "./_support.ts";

const AT = 1_700_000_000_000;
const ITEMS = [{ sku: "seat", qty: 2, unit: 5000 }];

interface Rig {
  billing: any;
  audit: any;
  journal: any;
  channel: any;
  dispatcher: any;
}

async function rig(providerOk: boolean, rules: any[] = []): Promise<Rig> {
  const Journal = await cls("../src/ledger/journal.ts", "Journal");
  const clock = new FixedClock(AT);
  const audit = new AuditLog(clock);
  const journal = new Journal(clock, []);
  const channel = stubChannel("spy", true);
  const dispatcher = new Dispatcher([channel]);
  const providers = new ProviderRegistry([stubProvider("card", providerOk)]);
  const billing = new BillingService(
    clock,
    audit,
    new PricingEngine(rules),
    providers,
    dispatcher,
    journal,
  );
  return { billing, audit, journal, channel, dispatcher };
}

/* ------------------------------------------------------------------ issue */

test("[t05_billing] issue numbers invoices inv-1, inv-2, inv-3", async () => {
  const { billing } = await rig(true);
  assert.equal(billing.issue(TENANT, ITEMS).id, "inv-1");
  assert.equal(billing.issue(TENANT, ITEMS).id, "inv-2");
  assert.equal(billing.issue(TENANT, ITEMS).id, "inv-3");
});

test("[t05_billing] issue carries tenant, items, subtotal, total and issuedAt", async () => {
  const { billing } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  assert.equal(invoice.tenantId, TENANT.id);
  assert.deepEqual(invoice.items, ITEMS);
  assert.equal(invoice.subtotal, 10000);
  assert.equal(invoice.total, 10000);
  assert.equal(invoice.issuedAt, AT);
});

test("[t05_billing] issue applies the pricing rules to the total", async () => {
  const { billing } = await rig(true, [stubRule("half", (t) => t / 2)]);
  const invoice = billing.issue(TENANT, ITEMS);
  assert.equal(invoice.subtotal, 10000);
  assert.equal(invoice.total, 5000);
});

test("[t05_billing] issue records billing/issue with the invoice id", async () => {
  const { billing, audit } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  assert.deepEqual(audit.entries().map(asAudit), [
    { actor: "billing", action: "issue", detail: invoice.id, at: AT },
  ]);
});

test("[t05_billing] issue journals nothing and dispatches nothing", async () => {
  const { billing, journal, channel } = await rig(true);
  billing.issue(TENANT, ITEMS);
  assert.deepEqual(journal.entries(), []);
  assert.deepEqual(channel.seen, []);
});

test("[t08_minor_units] issue produces an integer total", async () => {
  const Tax = await cls("../src/rules/tax.ts", "TaxRule");
  const { billing } = await rig(true, [new Tax(0.0825)]);
  const invoice = billing.issue(TENANT, [{ sku: "a", qty: 3, unit: 3333 }]);
  assert.ok(Number.isInteger(invoice.total));
  assert.equal(invoice.subtotal, 9999);
  assert.equal(invoice.total, 10824);
});

/* --------------------------------------------------------- settle: success */

test("[t05_billing] settle returns the charge result on the successful path", async () => {
  const { billing } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  const result = billing.settle(invoice, "card", "tok_ok");
  assert.equal(result.ok, true);
  assert.equal(result.providerId, "card");
});

test("[t05_billing] settle posts a payment journal entry for the invoice total", async () => {
  const { billing, journal } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  billing.settle(invoice, "card", "tok_ok");
  const entries = journal.entries();
  assert.equal(entries.length, 1);
  assert.equal(entries[0].tenantId, TENANT.id);
  assert.equal(entries[0].amount, invoice.total);
  assert.equal(entries[0].kind, "payment");
});

test("[t05_billing] settle dispatches a Payment received notification carrying the invoice id", async () => {
  const { billing, channel } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  billing.settle(invoice, "card", "tok_ok");
  assert.equal(channel.seen.length, 1);
  assert.equal(channel.seen[0].subject, "Payment received");
  assert.equal(channel.seen[0].body, invoice.id);
  assert.equal(channel.seen[0].tenantId, TENANT.id);
});

test("[t05_billing] settle records billing/settle on the successful path", async () => {
  const { billing, audit } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  audit.clear();
  billing.settle(invoice, "card", "tok_ok");
  assert.deepEqual(
    audit.entries().filter((e: any) => e.actor === "billing").map(asAudit),
    [{ actor: "billing", action: "settle", detail: invoice.id, at: AT }],
  );
});

test("[t05_billing] settle charges the invoice's own id, tenant and total", async () => {
  const Journal = await cls("../src/ledger/journal.ts", "Journal");
  const clock = new FixedClock(AT);
  const seen: any[] = [];
  const provider = {
    id: "card",
    validate: () => true,
    charge(r: any) {
      seen.push(r);
      return { ok: true, providerId: "card", reference: "card-x", message: "ok" };
    },
    refund: (reference: string) => ({
      ok: true,
      providerId: "card",
      reference,
      message: "refunded",
    }),
  };
  const billing = new BillingService(
    clock,
    new AuditLog(clock),
    new PricingEngine([]),
    new ProviderRegistry([provider]),
    new Dispatcher([]),
    new Journal(clock, []),
  );
  const invoice = billing.issue(TENANT, ITEMS);
  billing.settle(invoice, "card", "tok_zz");
  assert.equal(seen.length, 1);
  assert.equal(seen[0].invoiceId, invoice.id);
  assert.equal(seen[0].tenantId, TENANT.id);
  assert.equal(seen[0].amount, invoice.total);
  assert.equal(seen[0].token, "tok_zz");
});

/* -------------------------------------------------------- settle: rejected */

test("[t05_billing] settle returns the failed charge result", async () => {
  const { billing } = await rig(false);
  const invoice = billing.issue(TENANT, ITEMS);
  const result = billing.settle(invoice, "card", "bad");
  assert.equal(result.ok, false);
  assert.equal(result.message, "invalid request");
});

test("[t05_billing] settle journals nothing when the charge fails", async () => {
  const { billing, journal } = await rig(false);
  const invoice = billing.issue(TENANT, ITEMS);
  billing.settle(invoice, "card", "bad");
  assert.deepEqual(journal.entries(), []);
});

test("[t05_billing] settle dispatches nothing when the charge fails", async () => {
  const { billing, channel } = await rig(false);
  const invoice = billing.issue(TENANT, ITEMS);
  billing.settle(invoice, "card", "bad");
  assert.deepEqual(channel.seen, []);
});

test("[t05_billing] settle records billing/settle even when the charge fails", async () => {
  const { billing, audit } = await rig(false);
  const invoice = billing.issue(TENANT, ITEMS);
  audit.clear();
  billing.settle(invoice, "card", "bad");
  assert.deepEqual(
    audit.entries().filter((e: any) => e.actor === "billing").map(asAudit),
    [{ actor: "billing", action: "settle", detail: invoice.id, at: AT }],
  );
});

test("[t05_billing] settle through an unknown provider fails and journals nothing", async () => {
  const { billing, journal, channel } = await rig(true);
  const invoice = billing.issue(TENANT, ITEMS);
  const result = billing.settle(invoice, "ghost", "tok_ok");
  assert.equal(result.ok, false);
  assert.equal(result.message, "no such provider");
  assert.deepEqual(journal.entries(), []);
  assert.deepEqual(channel.seen, []);
});

test("[t05_billing] two settled invoices produce two journal entries", async () => {
  const { billing, journal } = await rig(true);
  const a = billing.issue(TENANT, ITEMS);
  const b = billing.issue(TENANT, ITEMS);
  billing.settle(a, "card", "tok_ok");
  billing.settle(b, "card", "tok_ok");
  assert.deepEqual(
    journal.entries().map((e: any) => e.id),
    ["je-1", "je-2"],
  );
  assert.equal(journal.balance(TENANT.id), a.total + b.total);
});

test("[t05_billing] settle uses the dispatcher's fanout over every channel", async () => {
  const Journal = await cls("../src/ledger/journal.ts", "Journal");
  const clock = new FixedClock(AT);
  const one = stubChannel("one", true);
  const two = stubChannel("two", false);
  const billing = new BillingService(
    clock,
    new AuditLog(clock),
    new PricingEngine([]),
    new ProviderRegistry([stubProvider("card", true)]),
    new Dispatcher([one, two]),
    new Journal(clock, []),
  );
  const invoice = billing.issue(TENANT, ITEMS);
  billing.settle(invoice, "card", "tok_ok");
  assert.equal(one.seen.length, 1);
  assert.equal(two.seen.length, 1);
});
