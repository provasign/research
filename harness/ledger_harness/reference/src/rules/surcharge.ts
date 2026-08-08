import { add, type Money } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class SurchargeRule implements PricingRule {
  readonly id = "surcharge";
  private amount: Money;

  constructor(amount: Money) {
    this.amount = amount;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const result: PricingContext = {
      ...ctx,
      total: add(ctx.total, this.amount),
      notes: [...ctx.notes, "surcharge"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
