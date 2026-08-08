import type { Money } from "./money.ts";
import type { LineItem, PricingContext, Tenant } from "./models.ts";

export interface PricingTrace {
  record(ruleId: string, before: Money, after: Money): void;
}

export interface TraceStep {
  ruleId: string;
  before: Money;
  after: Money;
}

export class CollectingTrace implements PricingTrace {
  private collected: TraceStep[];

  constructor() {
    this.collected = [];
  }

  record(ruleId: string, before: Money, after: Money): void {
    this.collected.push({ ruleId, before, after });
  }

  steps(): TraceStep[] {
    return this.collected.slice();
  }
}

class NoopTrace implements PricingTrace {
  record(_ruleId: string, _before: Money, _after: Money): void {
    /* no-op */
  }
}

export interface PricingRule {
  readonly id: string;
  apply(ctx: PricingContext, trace: PricingTrace): PricingContext;
}

export class PricingEngine {
  private rules: PricingRule[];

  constructor(rules: PricingRule[]) {
    this.rules = rules;
  }

  price(tenant: Tenant, items: LineItem[], trace?: PricingTrace): PricingContext {
    const t: PricingTrace = trace ?? new NoopTrace();
    let subtotal = 0;
    for (const item of items) {
      subtotal += item.qty * item.unit;
    }
    let ctx: PricingContext = {
      tenant,
      items,
      subtotal,
      total: subtotal,
      notes: [],
    };
    for (const rule of this.rules) {
      ctx = rule.apply(ctx, t);
    }
    return ctx;
  }
}
