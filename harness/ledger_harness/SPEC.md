# ledger — multi-tenant billing & payments: API SPEC v1

This is the frozen public contract. Other teams code against these exact module
paths, class names, and signatures.

## Ground rules

- **TypeScript, ESM, Node 26.** No build step: source runs directly via Node's
  native type stripping.
- **Relative imports MUST carry the `.ts` extension** (`import { Money } from
  "./money.ts"`). Node requires it; an extensionless import fails at runtime.
- **No third-party runtime dependencies.** `typescript` is available as a
  dev-dependency for `npm run typecheck` only.
- Source lives in `src/`, tests in `test/` (files named `*.test.ts`).
- `npm run typecheck` (`tsc --noEmit`) must pass. `npm test` (`node --test`)
  must pass.
- Everything is synchronous unless a signature says `Promise`.
- No wall-clock, no randomness, no network anywhere in `src/` — all time comes
  from an injected `Clock`, so behaviour is reproducible.

---

## `src/money.ts`

```ts
export type Money = number;                 // US dollars, may be fractional
export function money(dollars: number): Money;
export function add(a: Money, b: Money): Money;
export function sub(a: Money, b: Money): Money;
export function mul(a: Money, factor: number): Money;
export function format(m: Money): string;   // "$1234.50", always 2 decimals
```

`money(x)` returns `x` unchanged. `format` uses a fixed two-decimal
representation with a leading `$` and no thousands separators.

---

## `src/clock.ts`

```ts
export interface Clock { now(): number; }           // epoch milliseconds
export class FixedClock implements Clock {
  constructor(private readonly at: number) {}
  now(): number;                                    // always `at`
}
export class SteppingClock implements Clock {
  constructor(start: number, stepMs: number);
  now(): number;   // returns start, then start+step, then start+2*step, ...
}
```

---

## `src/models.ts`

```ts
export interface Tenant { id: string; name: string; plan: string; }
export interface LineItem { sku: string; qty: number; unit: Money; }
export interface Invoice {
  id: string; tenantId: string; items: LineItem[];
  subtotal: Money; total: Money; issuedAt: number;
}
export interface PricingContext {
  tenant: Tenant; items: LineItem[]; subtotal: Money; total: Money;
  notes: string[];
}
export interface ChargeRequest { invoiceId: string; tenantId: string; amount: Money; token: string; }
export interface ChargeResult { ok: boolean; providerId: string; reference: string; message: string; }
export interface Notification { tenantId: string; subject: string; body: string; }
export interface JournalEntry { id: string; tenantId: string; amount: Money; kind: string; at: number; }
export interface AuditRecord { actor: string; action: string; detail: string; at: number; }
```

---

## `src/audit.ts`

```ts
export class AuditLog {
  constructor(private readonly clock: Clock) {}
  record(actor: string, action: string, detail: string): void;
  entries(): AuditRecord[];       // a COPY, in insertion order
  clear(): void;
}
```

`record` appends `{actor, action, detail, at: clock.now()}`.

---

## `src/pricing.ts` — `PricingRule`

```ts
export interface PricingRule {
  readonly id: string;
  apply(ctx: PricingContext): PricingContext;
}
```

`apply` returns a **new** context; it must not mutate its argument. Each rule
appends exactly one line to `notes` (the text is given below) and adjusts
`total`. `subtotal` is never changed by a rule.

Implement these ten, each in `src/rules/<file>.ts`, each with the given `id`:

| class | file | id | effect on `total` | note appended |
|---|---|---|---|---|
| `FlatDiscountRule` | `flat-discount.ts` | `flat-discount` | `sub(total, amount)` (ctor arg `amount: Money`) | `flat discount` |
| `PercentDiscountRule` | `percent-discount.ts` | `percent-discount` | `mul(total, 1 - pct)` (ctor `pct: number`) | `percent discount` |
| `VolumeDiscountRule` | `volume-discount.ts` | `volume-discount` | if total item qty >= `threshold`, `mul(total, 1 - pct)` else unchanged (ctor `threshold: number, pct: number`) | `volume discount` |
| `TieredPricingRule` | `tiered.ts` | `tiered` | `mul(total, factor)` where factor is `0.9` if subtotal >= 1000, `0.95` if >= 500, else `1` | `tiered pricing` |
| `MinimumChargeRule` | `minimum-charge.ts` | `minimum-charge` | `total < floorAmount ? floorAmount : total` (ctor `floorAmount: Money`) | `minimum charge` |
| `SurchargeRule` | `surcharge.ts` | `surcharge` | `add(total, amount)` (ctor `amount: Money`) | `surcharge` |
| `RoundingRule` | `rounding.ts` | `rounding` | round to nearest cent, half away from zero | `rounding` |
| `PlanCreditRule` | `plan-credit.ts` | `plan-credit` | if `tenant.plan === "enterprise"`, `sub(total, credit)` else unchanged (ctor `credit: Money`) | `plan credit` |
| `TaxRule` | `tax.ts` | `tax` | `add(total, mul(total, rate))` (ctor `rate: number`) | `tax` |
| `CapRule` | `cap.ts` | `cap` | `total > ceiling ? ceiling : total` (ctor `ceiling: Money`) | `cap` |

```ts
// src/pricing.ts
export class PricingEngine {
  constructor(private readonly rules: PricingRule[]) {}
  price(tenant: Tenant, items: LineItem[]): PricingContext;
}
```

`price` builds the initial context with `subtotal` = `total` = sum of
`qty * unit` over items and `notes: []`, then folds every rule in order.

---

## `src/payments.ts` — `PaymentProvider`

```ts
export interface PaymentProvider {
  readonly id: string;
  charge(req: ChargeRequest): ChargeResult;
  refund(reference: string, amount: Money): ChargeResult;
  validate(req: ChargeRequest): boolean;
}
```

Implement these eight in `src/providers/<file>.ts`. Every provider takes
`(clock: Clock, audit: AuditLog)` as its **first two constructor parameters**,
in that order.

| class | file | id | `validate` returns false when | reference format |
|---|---|---|---|---|
| `CardProvider` | `card.ts` | `card` | `token` does not start with `tok_` | `card-<invoiceId>` |
| `AchProvider` | `ach.ts` | `ach` | `amount` > 25000 | `ach-<invoiceId>` |
| `WireProvider` | `wire.ts` | `wire` | `amount` < 100 | `wire-<invoiceId>` |
| `WalletProvider` | `wallet.ts` | `wallet` | `token` is empty | `wallet-<invoiceId>` |
| `GiftCardProvider` | `giftcard.ts` | `giftcard` | `amount` > 500 | `gift-<invoiceId>` |
| `CreditProvider` | `credit.ts` | `credit` | `tenantId` is empty | `credit-<invoiceId>` |
| `InvoiceProvider` | `invoice-provider.ts` | `invoice` | `amount` <= 0 | `inv-<invoiceId>` |
| `ManualProvider` | `manual.ts` | `manual` | never (always true) | `man-<invoiceId>` |

`charge` returns `{ok: false, providerId: id, reference: "", message: "invalid
request"}` when `validate` is false; otherwise `{ok: true, providerId: id,
reference: <format above>, message: "ok"}`. `refund` returns `{ok: true,
providerId: id, reference, message: "refunded"}`.

```ts
export class ProviderRegistry {
  constructor(providers: PaymentProvider[]) {}
  get(id: string): PaymentProvider | undefined;
  ids(): string[];            // sorted ascending
  charge(id: string, req: ChargeRequest): ChargeResult;  // unknown id -> ok:false, message "no such provider"
}
```

---

## `src/notify.ts` — `NotificationChannel`

```ts
export interface NotificationChannel {
  readonly id: string;
  send(msg: Notification): boolean;
  validate(msg: Notification): boolean;
}
```

Implement six in `src/channels/<file>.ts`, each constructed with
`(clock: Clock, audit: AuditLog)` first:

| class | file | id | `validate` false when |
|---|---|---|---|
| `EmailChannel` | `email.ts` | `email` | `subject` is empty |
| `SmsChannel` | `sms.ts` | `sms` | `body.length` > 160 |
| `WebhookChannel` | `webhook.ts` | `webhook` | `tenantId` is empty |
| `SlackChannel` | `slack.ts` | `slack` | `body` is empty |
| `PushChannel` | `push.ts` | `push` | `subject.length` > 64 |
| `InAppChannel` | `inapp.ts` | `inapp` | never |

`send` returns `validate(msg)`.

```ts
export class Dispatcher {
  constructor(private readonly channels: NotificationChannel[]) {}
  dispatch(msg: Notification): string[];   // ids of channels that returned true, in channel order
}
```

---

## `src/middleware.ts`

```ts
export interface Middleware {
  readonly id: string;
  handle(req: string, next: (r: string) => string): string;
}
export class RequestPipeline {
  constructor(private readonly middleware: Middleware[]) {}
  run(req: string): string;    // first middleware outermost
}
```

Implement in `src/middleware/<file>.ts`: `TrimMiddleware` (`trim`, trims then
calls next), `UpperMiddleware` (`upper`, uppercases the RESULT of next),
`PrefixMiddleware` (`prefix`, ctor `p: string`, prefixes the result of next),
`AuditMiddleware` (`audit`, ctor `(clock, audit)`, records
`("pipeline","handle",req)` then calls next).

---

## `src/validation.ts`

```ts
export interface Validator<T> { readonly id: string; validate(value: T): string[]; }
```

Returns a list of human-readable problems; empty means valid. Implement in
`src/validators/<file>.ts`: `InvoiceValidator` (`invoice`: `id` empty →
`"missing id"`; `items` empty → `"no items"`), `TenantValidator` (`tenant`:
`id` empty → `"missing id"`; `plan` not one of `free|pro|enterprise` →
`"bad plan"`), `LineItemValidator` (`line-item`: `qty` <= 0 → `"bad qty"`;
`unit` < 0 → `"bad unit"`).

---

## `src/journal.ts` — `LedgerPolicy`

```ts
export interface LedgerPolicy { readonly id: string; apply(entry: JournalEntry): JournalEntry; }
export class Journal {
  constructor(private readonly clock: Clock, private readonly policies: LedgerPolicy[]) {}
  post(tenantId: string, amount: Money, kind: string): JournalEntry;
  entries(): JournalEntry[];                  // a COPY, insertion order
  balance(tenantId: string): Money;           // sum of that tenant's amounts
}
```

`post` builds `{id: "je-" + (count+1), tenantId, amount, kind, at: clock.now()}`
then folds every policy over it, stores and returns the result.

Implement in `src/policies/<file>.ts`: `SignPolicy` (`sign`: if `kind` is
`"credit"`, negate `amount`), `RoundPolicy` (`round`: round `amount` to the
nearest cent), `ClampPolicy` (`clamp`, ctor `max: Money`: clamp `|amount|` to
`max`, keeping sign).

---

## `src/billing.ts`

```ts
export class BillingService {
  constructor(
    private readonly clock: Clock,
    private readonly audit: AuditLog,
    private readonly pricing: PricingEngine,
    private readonly providers: ProviderRegistry,
    private readonly dispatcher: Dispatcher,
    private readonly journal: Journal,
  ) {}
  issue(tenant: Tenant, items: LineItem[]): Invoice;
  settle(invoice: Invoice, providerId: string, token: string): ChargeResult;
}
```

- `issue` prices the items, builds `{id: "inv-" + (issuedCount+1), tenantId,
  items, subtotal, total, issuedAt: clock.now()}`, records
  `("billing","issue",invoice.id)` on the audit log, and returns it.
- `settle` charges through the registry; on success posts a journal entry
  (`kind: "payment"`, amount = invoice total) and dispatches a notification with
  subject `"Payment received"` and body the invoice id. It records
  `("billing","settle",invoice.id)` either way, and returns the charge result.

---

## `src/cli.ts`

```ts
export function main(argv: string[]): number;
```

Wires a default set of everything, runs one issue+settle, prints a summary,
returns `0`.
