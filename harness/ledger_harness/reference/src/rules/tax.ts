import { add, mul } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class TaxRule implements PricingRule {
  readonly id = "tax";
  private rate: number;

  constructor(rate: number) {
    this.rate = rate;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const result: PricingContext = {
      ...ctx,
      total: add(ctx.total, mul(ctx.total, this.rate)),
      notes: [...ctx.notes, "tax"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
