import type { Clock } from "./clock.ts";
import type { AuditLog } from "./audit.ts";
import type { PricingEngine } from "./pricing.ts";
import type { ProviderRegistry } from "./payments.ts";
import type { Dispatcher } from "./notify.ts";
import type { Journal } from "./ledger/journal.ts";
import type { ChargeResult, Invoice, LineItem, Tenant } from "./models.ts";

export class BillingService {
  private clock: Clock;
  private audit: AuditLog;
  private pricing: PricingEngine;
  private providers: ProviderRegistry;
  private dispatcher: Dispatcher;
  private journal: Journal;
  private issuedCount: number;

  constructor(
    clock: Clock,
    audit: AuditLog,
    pricing: PricingEngine,
    providers: ProviderRegistry,
    dispatcher: Dispatcher,
    journal: Journal,
  ) {
    this.clock = clock;
    this.audit = audit;
    this.pricing = pricing;
    this.providers = providers;
    this.dispatcher = dispatcher;
    this.journal = journal;
    this.issuedCount = 0;
  }

  issue(tenant: Tenant, items: LineItem[]): Invoice {
    const ctx = this.pricing.price(tenant, items);
    this.issuedCount += 1;
    const invoice: Invoice = {
      id: `inv-${this.issuedCount}`,
      tenantId: tenant.id,
      items,
      subtotal: ctx.subtotal,
      total: ctx.total,
      issuedAt: this.clock.now(),
    };
    this.audit.record("billing", "issue", invoice.id);
    return invoice;
  }

  settle(invoice: Invoice, providerId: string, token: string): ChargeResult {
    const result = this.providers.charge(providerId, {
      invoiceId: invoice.id,
      tenantId: invoice.tenantId,
      amount: invoice.total,
      token,
    });
    if (result.ok) {
      this.journal.post(invoice.tenantId, invoice.total, "payment");
      this.dispatcher.fanout({
        tenantId: invoice.tenantId,
        subject: "Payment received",
        body: invoice.id,
      });
    }
    this.audit.record("billing", "settle", invoice.id);
    return result;
  }
}
