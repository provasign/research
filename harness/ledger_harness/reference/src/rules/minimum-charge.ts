import type { Money } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class MinimumChargeRule implements PricingRule {
  readonly id = "minimum-charge";
  private floorAmount: Money;

  constructor(floorAmount: Money) {
    this.floorAmount = floorAmount;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const result: PricingContext = {
      ...ctx,
      total: ctx.total < this.floorAmount ? this.floorAmount : ctx.total,
      notes: [...ctx.notes, "minimum charge"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
