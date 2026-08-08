import type { Clock } from "../clock.ts";
import type { AuditLog } from "../audit.ts";
import type { Money } from "../money.ts";
import type { ChargeRequest, ChargeResult } from "../models.ts";
import type { PaymentProvider } from "../payments.ts";

export class CardProvider implements PaymentProvider {
  readonly id = "card";
  private clock: Clock;
  private audit: AuditLog;

  constructor(clock: Clock, audit: AuditLog) {
    this.clock = clock;
    this.audit = audit;
  }

  validate(req: ChargeRequest): boolean {
    return req.token.startsWith("tok_");
  }

  charge(req: ChargeRequest): ChargeResult {
    this.audit.record("payment", "charge", `${this.id}:${req.invoiceId}`);
    if (!this.validate(req)) {
      return { ok: false, providerId: this.id, reference: "", message: "invalid request" };
    }
    return {
      ok: true,
      providerId: this.id,
      reference: `card-${req.invoiceId}`,
      message: "ok",
    };
  }

  refund(reference: string, amount: Money): ChargeResult {
    this.audit.record("payment", "refund", `${this.id}:${reference}`);
    void amount;
    return { ok: true, providerId: this.id, reference, message: "refunded" };
  }
}
