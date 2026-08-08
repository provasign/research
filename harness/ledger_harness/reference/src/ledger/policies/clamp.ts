import type { Money } from "../../money.ts";
import type { JournalEntry } from "../../models.ts";
import type { LedgerPolicy } from "../journal.ts";

export class ClampPolicy implements LedgerPolicy {
  readonly id = "clamp";
  private max: Money;

  constructor(max: Money) {
    this.max = max;
  }

  apply(entry: JournalEntry): JournalEntry {
    const magnitude = Math.abs(entry.amount);
    if (magnitude <= this.max) {
      return { ...entry };
    }
    const clamped = entry.amount < 0 ? -this.max : this.max;
    return { ...entry, amount: clamped };
  }
}
