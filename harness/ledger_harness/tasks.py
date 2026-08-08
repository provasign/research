"""The ledger development session: 13 turns building a mid-size TS service.

Design note — why the task mix is split the way it is.

The tickr study tied because the baseline never failed. In a TYPED language the
trap is worse: for a signature change the compiler already does what
change_impact does, for free. A missed call site is a build error, the agent
runs `npm run typecheck`, fixes it, and both arms converge on correct. A
benchmark made only of signature changes measures nothing but cost.

So the turns deliberately split into two kinds:

  COMPILER-CAUGHT (t6, t9, t10) — tsc flags every miss. Expect a correctness
    tie; what is measurable here is the COST of getting there, and that is
    where name collisions bite: `apply` lives on PricingRule AND LedgerPolicy,
    `validate` on PaymentProvider AND NotificationChannel AND Validator,
    `handle` on Middleware. Grep for the method name returns noise; a
    type-resolved query returns the family.

  SILENT (t7, t8) — the change compiles clean and the existing tests still
    pass, so nothing tells the agent it missed a site. Completeness has to be
    established by analysis. This is the only regime where a code graph can
    show a CORRECTNESS effect rather than a speed one, and it is the reason
    this benchmark exists.

Both arms get byte-identical prompts. Nothing here names a tool.
"""
from __future__ import annotations

from pathlib import Path

SPEC = (Path(__file__).parent / "SPEC.md").read_text()

TAIL = """

When you are done with this work item:
  1. `npm run typecheck` must pass,
  2. `npm test` must pass,
  3. stop.

Do not create git commits. Do not add third-party runtime dependencies.
Remember: relative imports need the `.ts` extension."""

TURNS = [
    dict(id="t01_core", kind="scaffold", prompt=f"""We are starting `ledger`, a multi-tenant billing and payments service.
Build the first slice in this repository, following the specification exactly.
Other teams are already coding against these names and signatures.

{SPEC}

For THIS work item implement only: `src/money.ts`, `src/clock.ts`,
`src/models.ts`, `src/audit.ts`, `src/pricing.ts` and all ten rules under
`src/rules/`. Add tests in `test/` covering money, both clocks, the audit log,
every one of the ten rules, and the engine's fold order."""),

    dict(id="t02_payments", kind="feature", prompt="""Work item: payments.

Implement `src/payments.ts` (the `PaymentProvider` interface and
`ProviderRegistry`) and all eight providers under `src/providers/`, exactly as
the SPEC describes — including the constructor convention that every provider
takes `(clock, audit)` as its first two parameters.

Add tests covering each provider's `validate` boundary, a successful and a
rejected `charge` for each, `refund`, and the registry's unknown-id path."""),

    dict(id="t03_notify", kind="feature", prompt="""Work item: notifications and the request pipeline.

Implement `src/notify.ts` with the `NotificationChannel` interface, the six
channels under `src/channels/`, and `Dispatcher`. Then implement
`src/middleware.ts` with the `Middleware` interface, `RequestPipeline`, and the
four middleware under `src/middleware/`.

Add tests for every channel's validate boundary, the dispatcher's ordering, and
the pipeline's nesting order (first middleware outermost)."""),

    dict(id="t04_journal", kind="feature", prompt="""Work item: validation and the journal.

Implement `src/validation.ts` with the `Validator<T>` interface and the three
validators under `src/validators/`. Then implement `src/journal.ts` with the
`LedgerPolicy` interface, `Journal`, and the three policies under
`src/policies/`.

Add tests for each validator's messages, the journal's id sequence and balance,
and each policy."""),

    dict(id="t05_billing", kind="feature", prompt="""Work item: tie it together.

Implement `src/billing.ts` (`BillingService`) and `src/cli.ts` (`main`) exactly
as specified. Add tests covering `issue` (pricing applied, audit recorded, id
sequence) and `settle` (both the successful and the rejected charge path,
including what is journalled and dispatched in each case)."""),

    # ---------------------------------------------------- COMPILER-CAUGHT
    dict(id="t06_trace_param", kind="refactor-compiler", prompt="""Work item: pricing is impossible to debug in production — when a total looks
wrong we cannot see which rule moved it.

`PricingRule.apply` gains a **second required parameter**:

```ts
export interface PricingTrace { record(ruleId: string, before: Money, after: Money): void; }

export interface PricingRule {
  readonly id: string;
  apply(ctx: PricingContext, trace: PricingTrace): PricingContext;
}
```

Add to `src/pricing.ts`:

```ts
export class CollectingTrace implements PricingTrace {
  record(ruleId: string, before: Money, after: Money): void;
  steps(): { ruleId: string; before: Money; after: Money }[];   // a COPY, in order
}
```

Every rule must call `trace.record(this.id, ctx.total, result.total)` exactly
once per `apply`, including when it leaves the total unchanged.

`PricingEngine` gains an optional second parameter on `price`:
`price(tenant, items, trace?: PricingTrace)`. When no trace is supplied it uses
a private no-op trace; the returned context is identical either way.

Update every implementation and every call site."""),

    # ---------------------------------------------------- SILENT
    dict(id="t07_provider_audit", kind="refactor-silent", prompt="""Work item from compliance — this is an audit finding, not a feature request.

> We cannot reconstruct who was charged what. Payment operations are not
> reaching the audit log.

Every `PaymentProvider` implementation must write to the audit log it was
constructed with:

- `charge(req)` records `("payment", "charge", "<providerId>:<invoiceId>")`
  before returning — on BOTH the successful and the rejected path.
- `refund(reference, amount)` records `("payment", "refund", "<providerId>:<reference>")`
  before returning.

`<providerId>` is the provider's own `id`. Every one of the eight providers is
in scope; compliance will sample them.

Nothing about the return values changes."""),

    dict(id="t08_minor_units", kind="refactor-silent", prompt="""Work item: we are moving money off floating point. Rounding drift has produced
two customer-visible discrepancies this quarter.

`Money` becomes **integer minor units (cents)** everywhere. The TypeScript type
stays `number`, but the meaning changes and every amount in the system is now an
integer number of cents.

In `src/money.ts`:
- `money(dollars: number): Money` returns `Math.round(dollars * 100)`.
- `add` / `sub` operate on integers unchanged.
- `mul(m, factor)` returns `Math.round(m * factor)` — always an integer.
- `format(m)` renders cents as dollars: `format(123450)` === `"$1234.50"`.

Every threshold, ceiling, floor and comparison expressed in dollars must move to
cents. Specifically, the SPEC's hardcoded numbers become:

- `TieredPricingRule`: subtotal tiers `1000` → `100000` and `500` → `50000`.
- `AchProvider.validate`: rejects amount > `2500000`.
- `WireProvider.validate`: rejects amount < `10000`.
- `GiftCardProvider.validate`: rejects amount > `50000`.
- `RoundingRule` and `RoundPolicy` round to a whole cent — which, in minor
  units, means rounding to a whole integer.

Constructor arguments that are amounts (`FlatDiscountRule.amount`,
`MinimumChargeRule.floorAmount`, `SurchargeRule.amount`, `PlanCreditRule.credit`,
`CapRule.ceiling`, `ClampPolicy.max`) are now cents too — the callers pass cents,
so the rules need no conversion, but any place that BUILDS one of those values
from a dollar figure must go through `money(...)`.

Rates and percentages (`PercentDiscountRule.pct`, `TaxRule.rate`,
`VolumeDiscountRule.pct`) are unitless and do not change.

Sweep the whole repository — source and tests — and make it consistent."""),

    # ---------------------------------------------------- COMPILER-CAUGHT
    dict(id="t09_describe", kind="refactor-compiler", prompt="""Work item: the admin console needs to list delivery channels with a
human-readable description.

`NotificationChannel` gains a **new required member**:

```ts
export interface NotificationChannel {
  readonly id: string;
  send(msg: Notification): boolean;
  validate(msg: Notification): boolean;
  describe(): string;
}
```

`describe()` returns `"<id> channel"` — e.g. the email channel returns
`"email channel"`.

`Dispatcher` gains `descriptions(): string[]`, returning every channel's
`describe()` in channel order.

Every implementation of the interface is in scope."""),

    dict(id="t10_rename_move", kind="refactor-compiler", prompt="""Work item: naming and layout cleanup agreed at the API review.

1. `Dispatcher.dispatch` is renamed to `Dispatcher.fanout`. Same behaviour.
   `dispatch` must no longer exist — no alias.

2. `Journal`, `LedgerPolicy` and the three policies move from `src/journal.ts`
   and `src/policies/` to `src/ledger/journal.ts` and `src/ledger/policies/`.
   After this change `src/journal.ts` and `src/policies/` must be **deleted** —
   not left as re-export shims. Importing `../journal.ts` must fail.

Update every reference in the repository, source and tests alike."""),

    dict(id="t11_tests", kind="tests", prompt="""Work item: the test suite has grown unevenly and we do not know what it misses.

Find the parts of `src/` the current tests do not exercise — whole classes with
no test at all, and untested branches of classes that do have one (every
provider's rejected path, every channel's validate boundary, the registry's
unknown-id path, the pipeline's ordering, each policy, the trace's behaviour
when a rule leaves the total unchanged, and `format` on negative and zero
amounts).

Write the tests that close those gaps. Keep the existing tests. Finish by
reporting which parts had no coverage before this work item and which of them
you have now covered."""),

    dict(id="t12_bug", kind="bugfix", prompt="""Bug report from the billing team — P1.

> Enterprise tenants on large invoices are being charged too little, and the
> pricing trace does not explain it. Reproduction: a tenant on the `enterprise`
> plan with a subtotal over the top tier, priced through a rule list that
> contains both a percent discount and a cap, comes out BELOW the cap even when
> the cap should have raised it — and `CapRule` reports no step in the trace.

Two defects are described here. Find them, fix them, and add regression tests
that would have caught each.

Note `CapRule`'s specified behaviour: it lowers a total that exceeds the ceiling
and leaves any other total untouched — it never raises a total. Part of your job
is deciding which half of that report is a real defect and which is a
misunderstanding, and saying so."""),

    dict(id="t13_cleanup", kind="cleanup", prompt="""Work item: pre-1.0 cleanup pass.

Go through `src/` and remove code nothing reaches any more — functions, classes,
modules and imports left behind by the renames, the module move, and the
refactors of the last few work items. Do not remove anything that is part of the
specified public API, and do not remove anything the tests or the CLI still use.

Then confirm the whole thing is healthy: typecheck clean, tests green, CLI runs.
Report what you removed and why it was unreachable."""),
]

TURN_IDS = [t["id"] for t in TURNS]
COMPILER_TURNS = [t["id"] for t in TURNS if t["kind"] == "refactor-compiler"]
SILENT_TURNS = [t["id"] for t in TURNS if t["kind"] == "refactor-silent"]
