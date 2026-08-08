import type { LineItem } from "../models.ts";
import type { Validator } from "../validation.ts";

export class LineItemValidator implements Validator<LineItem> {
  readonly id = "line-item";
  validate(value: LineItem): string[] {
    const problems: string[] = [];
    if (value.qty <= 0) {
      problems.push("bad qty");
    }
    if (value.unit < 0) {
      problems.push("bad unit");
    }
    return problems;
  }
}
