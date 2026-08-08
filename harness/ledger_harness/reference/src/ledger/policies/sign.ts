import type { JournalEntry } from "../../models.ts";
import type { LedgerPolicy } from "../journal.ts";

export class SignPolicy implements LedgerPolicy {
  readonly id = "sign";
  apply(entry: JournalEntry): JournalEntry {
    if (entry.kind === "credit") {
      return { ...entry, amount: -entry.amount };
    }
    return { ...entry };
  }
}
