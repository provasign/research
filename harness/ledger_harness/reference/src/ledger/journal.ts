import type { Clock } from "../clock.ts";
import type { Money } from "../money.ts";
import type { JournalEntry } from "../models.ts";

export interface LedgerPolicy {
  readonly id: string;
  apply(entry: JournalEntry): JournalEntry;
}

export class Journal {
  private clock: Clock;
  private policies: LedgerPolicy[];
  private stored: JournalEntry[];

  constructor(clock: Clock, policies: LedgerPolicy[]) {
    this.clock = clock;
    this.policies = policies;
    this.stored = [];
  }

  post(tenantId: string, amount: Money, kind: string): JournalEntry {
    let entry: JournalEntry = {
      id: `je-${this.stored.length + 1}`,
      tenantId,
      amount,
      kind,
      at: this.clock.now(),
    };
    for (const policy of this.policies) {
      entry = policy.apply(entry);
    }
    this.stored.push(entry);
    return entry;
  }

  entries(): JournalEntry[] {
    return this.stored.slice();
  }

  balance(tenantId: string): Money {
    let sum = 0;
    for (const entry of this.stored) {
      if (entry.tenantId === tenantId) {
        sum += entry.amount;
      }
    }
    return sum;
  }
}
