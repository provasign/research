import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

/** Round to a whole cent, which in minor units means a whole integer. */
export class RoundingRule implements PricingRule {
  readonly id = "rounding";

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const t = ctx.total;
    const rounded = t < 0 ? -Math.round(-t) : Math.round(t);
    const result: PricingContext = {
      ...ctx,
      total: rounded,
      notes: [...ctx.notes, "rounding"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
