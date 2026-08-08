import type { Money } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class CapRule implements PricingRule {
  readonly id = "cap";
  private ceiling: Money;

  constructor(ceiling: Money) {
    this.ceiling = ceiling;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const result: PricingContext = {
      ...ctx,
      total: ctx.total > this.ceiling ? this.ceiling : ctx.total,
      notes: [...ctx.notes, "cap"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
