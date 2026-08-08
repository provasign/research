import type { Clock } from "../clock.ts";
import type { AuditLog } from "../audit.ts";
import type { Notification } from "../models.ts";
import type { NotificationChannel } from "../notify.ts";

export class SmsChannel implements NotificationChannel {
  readonly id = "sms";
  private clock: Clock;
  private audit: AuditLog;

  constructor(clock: Clock, audit: AuditLog) {
    this.clock = clock;
    this.audit = audit;
  }

  validate(msg: Notification): boolean {
    return msg.body.length <= 160;
  }

  send(msg: Notification): boolean {
    return this.validate(msg);
  }

  describe(): string {
    return `${this.id} channel`;
  }
}
