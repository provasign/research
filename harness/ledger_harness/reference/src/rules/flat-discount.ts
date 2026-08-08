import { sub, type Money } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class FlatDiscountRule implements PricingRule {
  readonly id = "flat-discount";
  private amount: Money;

  constructor(amount: Money) {
    this.amount = amount;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const result: PricingContext = {
      ...ctx,
      total: sub(ctx.total, this.amount),
      notes: [...ctx.notes, "flat discount"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
