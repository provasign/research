import type { JournalEntry } from "../../models.ts";
import type { LedgerPolicy } from "../journal.ts";

/** Round to a whole cent, which in minor units means a whole integer. */
export class RoundPolicy implements LedgerPolicy {
  readonly id = "round";
  apply(entry: JournalEntry): JournalEntry {
    const a = entry.amount;
    const rounded = a < 0 ? -Math.round(-a) : Math.round(a);
    return { ...entry, amount: rounded };
  }
}
