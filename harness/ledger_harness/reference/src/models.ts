import type { Money } from "./money.ts";

export interface Tenant {
  id: string;
  name: string;
  plan: string;
}

export interface LineItem {
  sku: string;
  qty: number;
  unit: Money;
}

export interface Invoice {
  id: string;
  tenantId: string;
  items: LineItem[];
  subtotal: Money;
  total: Money;
  issuedAt: number;
}

export interface PricingContext {
  tenant: Tenant;
  items: LineItem[];
  subtotal: Money;
  total: Money;
  notes: string[];
}

export interface ChargeRequest {
  invoiceId: string;
  tenantId: string;
  amount: Money;
  token: string;
}

export interface ChargeResult {
  ok: boolean;
  providerId: string;
  reference: string;
  message: string;
}

export interface Notification {
  tenantId: string;
  subject: string;
  body: string;
}

export interface JournalEntry {
  id: string;
  tenantId: string;
  amount: Money;
  kind: string;
  at: number;
}

export interface AuditRecord {
  actor: string;
  action: string;
  detail: string;
  at: number;
}
