import type { Money } from "./money.ts";
import type { ChargeRequest, ChargeResult } from "./models.ts";

export interface PaymentProvider {
  readonly id: string;
  charge(req: ChargeRequest): ChargeResult;
  refund(reference: string, amount: Money): ChargeResult;
  validate(req: ChargeRequest): boolean;
}

export class ProviderRegistry {
  private providers: PaymentProvider[];

  constructor(providers: PaymentProvider[]) {
    this.providers = providers;
  }

  get(id: string): PaymentProvider | undefined {
    return this.providers.find((p) => p.id === id);
  }

  ids(): string[] {
    return this.providers.map((p) => p.id).sort();
  }

  charge(id: string, req: ChargeRequest): ChargeResult {
    const provider = this.get(id);
    if (provider === undefined) {
      return { ok: false, providerId: id, reference: "", message: "no such provider" };
    }
    return provider.charge(req);
  }
}
