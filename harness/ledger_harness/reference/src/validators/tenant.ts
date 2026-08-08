import type { Tenant } from "../models.ts";
import type { Validator } from "../validation.ts";

const PLANS = ["free", "pro", "enterprise"];

export class TenantValidator implements Validator<Tenant> {
  readonly id = "tenant";
  validate(value: Tenant): string[] {
    const problems: string[] = [];
    if (value.id === "") {
      problems.push("missing id");
    }
    if (!PLANS.includes(value.plan)) {
      problems.push("bad plan");
    }
    return problems;
  }
}
