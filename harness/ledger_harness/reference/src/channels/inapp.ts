import type { Clock } from "../clock.ts";
import type { AuditLog } from "../audit.ts";
import type { Notification } from "../models.ts";
import type { NotificationChannel } from "../notify.ts";

export class InAppChannel implements NotificationChannel {
  readonly id = "inapp";
  private clock: Clock;
  private audit: AuditLog;

  constructor(clock: Clock, audit: AuditLog) {
    this.clock = clock;
    this.audit = audit;
  }

  validate(msg: Notification): boolean {
    return true;
  }

  send(msg: Notification): boolean {
    return this.validate(msg);
  }

  describe(): string {
    return `${this.id} channel`;
  }
}
