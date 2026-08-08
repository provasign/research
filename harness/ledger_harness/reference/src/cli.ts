import { FixedClock } from "./clock.ts";
import { AuditLog } from "./audit.ts";
import { money, format } from "./money.ts";
import { PricingEngine } from "./pricing.ts";
import { ProviderRegistry } from "./payments.ts";
import { Dispatcher } from "./notify.ts";
import { Journal } from "./ledger/journal.ts";
import { BillingService } from "./billing.ts";

import { TieredPricingRule } from "./rules/tiered.ts";
import { PercentDiscountRule } from "./rules/percent-discount.ts";
import { TaxRule } from "./rules/tax.ts";
import { RoundingRule } from "./rules/rounding.ts";

import { CardProvider } from "./providers/card.ts";
import { AchProvider } from "./providers/ach.ts";
import { ManualProvider } from "./providers/manual.ts";

import { EmailChannel } from "./channels/email.ts";
import { InAppChannel } from "./channels/inapp.ts";

import { SignPolicy } from "./ledger/policies/sign.ts";
import { RoundPolicy } from "./ledger/policies/round.ts";

import type { LineItem, Tenant } from "./models.ts";

export function main(argv: string[]): number {
  void argv;
  const clock = new FixedClock(1_700_000_000_000);
  const audit = new AuditLog(clock);

  const pricing = new PricingEngine([
    new TieredPricingRule(),
    new PercentDiscountRule(0.1),
    new TaxRule(0.08),
    new RoundingRule(),
  ]);
  const providers = new ProviderRegistry([
    new CardProvider(clock, audit),
    new AchProvider(clock, audit),
    new ManualProvider(clock, audit),
  ]);
  const dispatcher = new Dispatcher([
    new EmailChannel(clock, audit),
    new InAppChannel(clock, audit),
  ]);
  const journal = new Journal(clock, [new SignPolicy(), new RoundPolicy()]);
  const billing = new BillingService(clock, audit, pricing, providers, dispatcher, journal);

  const tenant: Tenant = { id: "t-1", name: "Acme", plan: "enterprise" };
  const items: LineItem[] = [
    { sku: "seat", qty: 10, unit: money(99.0) },
    { sku: "support", qty: 1, unit: money(250.0) },
  ];

  const invoice = billing.issue(tenant, items);
  const result = billing.settle(invoice, "card", "tok_live");

  console.log(`invoice ${invoice.id} subtotal ${format(invoice.subtotal)} total ${format(invoice.total)}`);
  console.log(`settle ${result.providerId} ok=${result.ok} ref=${result.reference} (${result.message})`);
  console.log(`balance ${format(journal.balance(tenant.id))} audit=${audit.entries().length}`);

  return 0;
}
