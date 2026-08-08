import { mul } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class PercentDiscountRule implements PricingRule {
  readonly id = "percent-discount";
  private pct: number;

  constructor(pct: number) {
    this.pct = pct;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const result: PricingContext = {
      ...ctx,
      total: mul(ctx.total, 1 - this.pct),
      notes: [...ctx.notes, "percent discount"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
