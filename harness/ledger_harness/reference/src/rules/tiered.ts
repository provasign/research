import { mul } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class TieredPricingRule implements PricingRule {
  readonly id = "tiered";

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    let factor = 1;
    if (ctx.subtotal >= 100000) {
      factor = 0.9;
    } else if (ctx.subtotal >= 50000) {
      factor = 0.95;
    }
    const result: PricingContext = {
      ...ctx,
      total: mul(ctx.total, factor),
      notes: [...ctx.notes, "tiered pricing"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
