import type { Invoice } from "../models.ts";
import type { Validator } from "../validation.ts";

export class InvoiceValidator implements Validator<Invoice> {
  readonly id = "invoice";
  validate(value: Invoice): string[] {
    const problems: string[] = [];
    if (value.id === "") {
      problems.push("missing id");
    }
    if (value.items.length === 0) {
      problems.push("no items");
    }
    return problems;
  }
}
