import type { Clock } from "../clock.ts";
import type { AuditLog } from "../audit.ts";
import type { Middleware } from "../middleware.ts";

export class AuditMiddleware implements Middleware {
  readonly id = "audit";
  private clock: Clock;
  private audit: AuditLog;

  constructor(clock: Clock, audit: AuditLog) {
    this.clock = clock;
    this.audit = audit;
  }

  handle(req: string, next: (r: string) => string): string {
    this.audit.record("pipeline", "handle", req);
    return next(req);
  }
}
