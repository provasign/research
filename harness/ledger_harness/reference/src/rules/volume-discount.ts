import { mul } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class VolumeDiscountRule implements PricingRule {
  readonly id = "volume-discount";
  private threshold: number;
  private pct: number;

  constructor(threshold: number, pct: number) {
    this.threshold = threshold;
    this.pct = pct;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    let qty = 0;
    for (const item of ctx.items) {
      qty += item.qty;
    }
    const total = qty >= this.threshold ? mul(ctx.total, 1 - this.pct) : ctx.total;
    const result: PricingContext = {
      ...ctx,
      total,
      notes: [...ctx.notes, "volume discount"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
