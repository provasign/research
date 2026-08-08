import { sub, type Money } from "../money.ts";
import type { PricingContext } from "../models.ts";
import type { PricingRule, PricingTrace } from "../pricing.ts";

export class PlanCreditRule implements PricingRule {
  readonly id = "plan-credit";
  private credit: Money;

  constructor(credit: Money) {
    this.credit = credit;
  }

  apply(ctx: PricingContext, trace: PricingTrace): PricingContext {
    const total =
      ctx.tenant.plan === "enterprise" ? sub(ctx.total, this.credit) : ctx.total;
    const result: PricingContext = {
      ...ctx,
      total,
      notes: [...ctx.notes, "plan credit"],
    };
    trace.record(this.id, ctx.total, result.total);
    return result;
  }
}
