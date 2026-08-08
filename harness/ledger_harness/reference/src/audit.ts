import type { Clock } from "./clock.ts";
import type { AuditRecord } from "./models.ts";

export class AuditLog {
  private clock: Clock;
  private records: AuditRecord[];

  constructor(clock: Clock) {
    this.clock = clock;
    this.records = [];
  }

  record(actor: string, action: string, detail: string): void {
    this.records.push({ actor, action, detail, at: this.clock.now() });
  }

  entries(): AuditRecord[] {
    return this.records.slice();
  }

  clear(): void {
    this.records = [];
  }
}
