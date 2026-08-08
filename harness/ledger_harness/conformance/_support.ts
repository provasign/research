// Shared helpers for the hidden conformance suite.
//
// Rules of engagement: this suite may only touch the PUBLIC contract — the
// module paths, class names and members named by SPEC.md and the five deltas
// (t06, t07, t08, t09, t10). It never inspects private state, never assumes
// how a constructor stores its arguments, and never assumes a file layout
// beyond the paths the contract actually names.
//
// SPEC names concrete file names for the rules, the providers and the
// channels, so those are imported by path. It does NOT name file names for
// the middleware, the validators or the ledger policies (only the directory),
// so those are discovered by scanning the directory the contract names.

import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

/* ------------------------------------------------------------------ *
 * dynamic loading
 * ------------------------------------------------------------------ */

/** Import a module by a specifier relative to this file, or throw a clear error. */
export async function mod(spec: string): Promise<Record<string, unknown>> {
  try {
    return (await import(spec)) as Record<string, unknown>;
  } catch (err) {
    throw new Error(`could not import ${spec}: ${(err as Error).message}`);
  }
}

/** Import one exported class by module specifier + export name. */
export async function cls(spec: string, name: string): Promise<any> {
  const m = await mod(spec);
  const c = m[name];
  if (typeof c !== "function") {
    throw new Error(`${spec} does not export a class named ${name}`);
  }
  return c;
}

const dirCache = new Map<string, Map<string, unknown>>();

/** Every export of every .ts module found under a directory (recursively). */
export async function exportsUnder(dir: string): Promise<Map<string, unknown>> {
  const cached = dirCache.get(dir);
  if (cached !== undefined) return cached;

  const found = new Map<string, unknown>();
  const walk = async (rel: string): Promise<void> => {
    const abs = join(import.meta.dirname, rel);
    if (!existsSync(abs)) return;
    for (const ent of readdirSync(abs, { withFileTypes: true })) {
      if (ent.isDirectory()) {
        await walk(`${rel}/${ent.name}`);
        continue;
      }
      if (!ent.name.endsWith(".ts") || ent.name.endsWith(".d.ts")) continue;
      try {
        const m = (await import(`${rel}/${ent.name}`)) as Record<string, unknown>;
        for (const [k, v] of Object.entries(m)) {
          if (!found.has(k)) found.set(k, v);
        }
      } catch {
        /* a module that will not load simply contributes nothing */
      }
    }
  };
  await walk(dir);
  dirCache.set(dir, found);
  return found;
}

/**
 * A class exported from somewhere under a contract-named directory. SPEC names
 * the directory for these families but not the individual file names, so the
 * directory is scanned; a sibling barrel module is accepted as a fallback.
 */
export async function clsUnder(dir: string, name: string): Promise<any> {
  const c = (await exportsUnder(dir)).get(name);
  if (typeof c === "function") return c;
  for (const fallback of [`${dir}.ts`, `${dir}/index.ts`]) {
    try {
      const m = (await import(fallback)) as Record<string, unknown>;
      if (typeof m[name] === "function") return m[name];
    } catch {
      /* fallback module does not exist */
    }
  }
  throw new Error(`no class ${name} exported under ${dir}/`);
}

export const POLICY_DIR = "../src/ledger/policies";
export const VALIDATOR_DIR = "../src/validators";
export const MIDDLEWARE_DIR = "../src/middleware";

export function repoPath(rel: string): string {
  return join(import.meta.dirname, rel);
}

/* ------------------------------------------------------------------ *
 * shape normalisation
 *
 * The contract declares AuditRecord / JournalEntry / trace steps by their
 * fields, not by a class. Strict deep equality compares prototypes, so record
 * shapes are projected onto plain objects before comparison — an
 * implementation that returns class instances with the right fields is still
 * conformant.
 * ------------------------------------------------------------------ */

export function pick(o: any, keys: string[]): any {
  const out: any = {};
  for (const k of keys) out[k] = o[k];
  return out;
}

export const asAudit = (e: any): any => pick(e, ["actor", "action", "detail", "at"]);
export const asStep = (s: any): any => pick(s, ["ruleId", "before", "after"]);
export const asEntry = (e: any): any =>
  pick(e, ["id", "tenantId", "amount", "kind", "at"]);

/* ------------------------------------------------------------------ *
 * fixtures
 * ------------------------------------------------------------------ */

export const TENANT = { id: "t-1", name: "Acme", plan: "pro" };
export const ENTERPRISE = { id: "t-2", name: "Globex", plan: "enterprise" };

/** Build a PricingContext (a public interface) for direct rule exercise. */
export function makeCtx(over: Record<string, unknown> = {}): any {
  const base: any = {
    tenant: TENANT,
    items: [{ sku: "seat", qty: 1, unit: 10000 }],
    subtotal: 10000,
    total: 10000,
    notes: [],
  };
  return { ...base, ...over };
}

/** A frozen context: any in-place mutation by a rule throws in strict mode. */
export function frozenCtx(over: Record<string, unknown> = {}): any {
  const c = makeCtx(over);
  Object.freeze(c.notes);
  Object.freeze(c.items);
  return Object.freeze(c);
}

export function req(over: Record<string, unknown> = {}): any {
  return {
    invoiceId: "inv-1",
    tenantId: "t-1",
    amount: 20000,
    token: "tok_ok",
    ...over,
  };
}

export function note(over: Record<string, unknown> = {}): any {
  return { tenantId: "t-1", subject: "Hello", body: "world", ...over };
}

/* ------------------------------------------------------------------ *
 * per-implementation tables (drive one test per implementation)
 * ------------------------------------------------------------------ */

export interface RuleSpec {
  cls: string;
  spec: string;
  id: string;
  note: string;
  /** ctor args, in cents where the argument is an amount */
  args: unknown[];
  /** a context in which the rule provably moves the total */
  moving: () => any;
  /** the total this rule must produce from `moving()` */
  movingTo: number;
  /** a context in which the rule provably leaves the total alone, if any */
  still?: () => any;
}

export const RULES: RuleSpec[] = [
  {
    cls: "FlatDiscountRule",
    spec: "../src/rules/flat-discount.ts",
    id: "flat-discount",
    note: "flat discount",
    args: [2500],
    moving: () => makeCtx({ total: 10000 }),
    movingTo: 7500,
  },
  {
    cls: "PercentDiscountRule",
    spec: "../src/rules/percent-discount.ts",
    id: "percent-discount",
    note: "percent discount",
    args: [0.25],
    moving: () => makeCtx({ total: 10000 }),
    movingTo: 7500,
  },
  {
    cls: "VolumeDiscountRule",
    spec: "../src/rules/volume-discount.ts",
    id: "volume-discount",
    note: "volume discount",
    args: [10, 0.5],
    moving: () =>
      makeCtx({ total: 10000, items: [{ sku: "a", qty: 10, unit: 1000 }] }),
    movingTo: 5000,
    still: () =>
      makeCtx({ total: 10000, items: [{ sku: "a", qty: 9, unit: 1000 }] }),
  },
  {
    cls: "TieredPricingRule",
    spec: "../src/rules/tiered.ts",
    id: "tiered",
    note: "tiered pricing",
    args: [],
    moving: () => makeCtx({ subtotal: 100000, total: 100000 }),
    movingTo: 90000,
    still: () => makeCtx({ subtotal: 49999, total: 49999 }),
  },
  {
    cls: "MinimumChargeRule",
    spec: "../src/rules/minimum-charge.ts",
    id: "minimum-charge",
    note: "minimum charge",
    args: [5000],
    moving: () => makeCtx({ total: 100 }),
    movingTo: 5000,
    still: () => makeCtx({ total: 9000 }),
  },
  {
    cls: "SurchargeRule",
    spec: "../src/rules/surcharge.ts",
    id: "surcharge",
    note: "surcharge",
    args: [750],
    moving: () => makeCtx({ total: 10000 }),
    movingTo: 10750,
  },
  {
    cls: "RoundingRule",
    spec: "../src/rules/rounding.ts",
    id: "rounding",
    note: "rounding",
    args: [],
    moving: () => makeCtx({ total: 10000.4 }),
    movingTo: 10000,
    still: () => makeCtx({ total: 10000 }),
  },
  {
    cls: "PlanCreditRule",
    spec: "../src/rules/plan-credit.ts",
    id: "plan-credit",
    note: "plan credit",
    args: [1500],
    moving: () => makeCtx({ tenant: ENTERPRISE, total: 10000 }),
    movingTo: 8500,
    still: () => makeCtx({ tenant: TENANT, total: 10000 }),
  },
  {
    cls: "TaxRule",
    spec: "../src/rules/tax.ts",
    id: "tax",
    note: "tax",
    args: [0.1],
    moving: () => makeCtx({ total: 10000 }),
    movingTo: 11000,
  },
  {
    cls: "CapRule",
    spec: "../src/rules/cap.ts",
    id: "cap",
    note: "cap",
    args: [9000],
    moving: () => makeCtx({ total: 10000 }),
    movingTo: 9000,
    still: () => makeCtx({ total: 8000 }),
  },
];

export interface ProviderSpec {
  cls: string;
  spec: string;
  id: string;
  ref: string;
  /** a request this provider accepts */
  good: () => any;
  /** a request this provider rejects (undefined for ManualProvider) */
  bad?: () => any;
  /** the boundary value that must still be accepted, and the turn that pins it */
  turn: string;
}

export const PROVIDERS: ProviderSpec[] = [
  {
    cls: "CardProvider",
    spec: "../src/providers/card.ts",
    id: "card",
    ref: "card",
    good: () => req({ token: "tok_live" }),
    bad: () => req({ token: "live_tok_" }),
    turn: "t02_payments",
  },
  {
    cls: "AchProvider",
    spec: "../src/providers/ach.ts",
    id: "ach",
    ref: "ach",
    good: () => req({ amount: 2500000 }),
    bad: () => req({ amount: 2500001 }),
    turn: "t08_minor_units",
  },
  {
    cls: "WireProvider",
    spec: "../src/providers/wire.ts",
    id: "wire",
    ref: "wire",
    good: () => req({ amount: 10000 }),
    bad: () => req({ amount: 9999 }),
    turn: "t08_minor_units",
  },
  {
    cls: "WalletProvider",
    spec: "../src/providers/wallet.ts",
    id: "wallet",
    ref: "wallet",
    good: () => req({ token: "w" }),
    bad: () => req({ token: "" }),
    turn: "t02_payments",
  },
  {
    cls: "GiftCardProvider",
    spec: "../src/providers/giftcard.ts",
    id: "giftcard",
    ref: "gift",
    good: () => req({ amount: 50000 }),
    bad: () => req({ amount: 50001 }),
    turn: "t08_minor_units",
  },
  {
    cls: "CreditProvider",
    spec: "../src/providers/credit.ts",
    id: "credit",
    ref: "credit",
    good: () => req({ tenantId: "t-1" }),
    bad: () => req({ tenantId: "" }),
    turn: "t02_payments",
  },
  {
    cls: "InvoiceProvider",
    spec: "../src/providers/invoice-provider.ts",
    id: "invoice",
    ref: "inv",
    good: () => req({ amount: 1 }),
    bad: () => req({ amount: 0 }),
    turn: "t02_payments",
  },
  {
    cls: "ManualProvider",
    spec: "../src/providers/manual.ts",
    id: "manual",
    ref: "man",
    good: () => req(),
    turn: "t02_payments",
  },
];

export interface ChannelSpec {
  cls: string;
  spec: string;
  id: string;
  good: () => any;
  bad?: () => any;
}

export const CHANNELS: ChannelSpec[] = [
  {
    cls: "EmailChannel",
    spec: "../src/channels/email.ts",
    id: "email",
    good: () => note({ subject: "s" }),
    bad: () => note({ subject: "" }),
  },
  {
    cls: "SmsChannel",
    spec: "../src/channels/sms.ts",
    id: "sms",
    good: () => note({ body: "x".repeat(160) }),
    bad: () => note({ body: "x".repeat(161) }),
  },
  {
    cls: "WebhookChannel",
    spec: "../src/channels/webhook.ts",
    id: "webhook",
    good: () => note({ tenantId: "t-1" }),
    bad: () => note({ tenantId: "" }),
  },
  {
    cls: "SlackChannel",
    spec: "../src/channels/slack.ts",
    id: "slack",
    good: () => note({ body: "hi" }),
    bad: () => note({ body: "" }),
  },
  {
    cls: "PushChannel",
    spec: "../src/channels/push.ts",
    id: "push",
    good: () => note({ subject: "x".repeat(64) }),
    bad: () => note({ subject: "x".repeat(65) }),
  },
  {
    cls: "InAppChannel",
    spec: "../src/channels/inapp.ts",
    id: "inapp",
    good: () => note(),
  },
];

/* ------------------------------------------------------------------ *
 * test doubles (structural — the contract is an interface, not a class)
 * ------------------------------------------------------------------ */

export function stubChannel(id: string, accepts: boolean): any {
  const seen: any[] = [];
  return {
    id,
    seen,
    send(msg: any) {
      seen.push(msg);
      return accepts;
    },
    validate() {
      return accepts;
    },
    describe() {
      return `${id} channel`;
    },
  };
}

export function stubRule(id: string, fn: (total: number) => number): any {
  return {
    id,
    apply(ctx: any, trace: any) {
      const out = { ...ctx, total: fn(ctx.total), notes: [...ctx.notes, id] };
      if (trace !== undefined && trace !== null) {
        trace.record(id, ctx.total, out.total);
      }
      return out;
    },
  };
}

export function stubProvider(id: string, ok: boolean): any {
  return {
    id,
    validate() {
      return ok;
    },
    charge(r: any) {
      return ok
        ? { ok: true, providerId: id, reference: `${id}-${r.invoiceId}`, message: "ok" }
        : { ok: false, providerId: id, reference: "", message: "invalid request" };
    },
    refund(reference: string) {
      return { ok: true, providerId: id, reference, message: "refunded" };
    },
  };
}
