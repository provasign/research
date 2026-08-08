import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock, SteppingClock } from "../src/clock.ts";
import { asEntry, cls, clsUnder, POLICY_DIR } from "./_support.ts";

const JOURNAL = "../src/ledger/journal.ts";

async function Journal(): Promise<any> {
  return cls(JOURNAL, "Journal");
}

/* ------------------------------------------------------------- the journal */

test("[t04_journal] post numbers entries je-1, je-2, je-3", async () => {
  const J = await Journal();
  const j = new J(new FixedClock(0), []);
  assert.equal(j.post("t-1", 100, "payment").id, "je-1");
  assert.equal(j.post("t-1", 100, "payment").id, "je-2");
  assert.equal(j.post("t-2", 100, "payment").id, "je-3");
});

test("[t04_journal] post returns the entry it stored", async () => {
  const J = await Journal();
  const j = new J(new FixedClock(1234), []);
  const entry = j.post("t-1", 2500, "payment");
  assert.deepEqual(asEntry(entry), {
    id: "je-1",
    tenantId: "t-1",
    amount: 2500,
    kind: "payment",
    at: 1234,
  });
  assert.deepEqual(j.entries().map(asEntry), [asEntry(entry)]);
});

test("[t04_journal] post stamps the entry with the clock", async () => {
  const J = await Journal();
  const j = new J(new SteppingClock(500, 100), []);
  j.post("t-1", 1, "payment");
  j.post("t-1", 1, "payment");
  assert.deepEqual(
    j.entries().map((e: any) => e.at),
    [500, 600],
  );
});

test("[t04_journal] entries starts empty", async () => {
  const J = await Journal();
  assert.deepEqual(new J(new FixedClock(0), []).entries(), []);
});

test("[t04_journal] entries preserves insertion order", async () => {
  const J = await Journal();
  const j = new J(new FixedClock(0), []);
  j.post("t-1", 1, "a");
  j.post("t-2", 2, "b");
  j.post("t-1", 3, "c");
  assert.deepEqual(
    j.entries().map((e: any) => e.kind),
    ["a", "b", "c"],
  );
});

test("[t04_journal] entries returns a copy", async () => {
  const J = await Journal();
  const j = new J(new FixedClock(0), []);
  j.post("t-1", 1, "a");
  const first = j.entries();
  const second = j.entries();
  assert.notEqual(first, second);
  first.push({ id: "x", tenantId: "x", amount: 0, kind: "x", at: 0 });
  assert.equal(j.entries().length, 1);
});

test("[t04_journal] balance sums only that tenant's amounts", async () => {
  const J = await Journal();
  const j = new J(new FixedClock(0), []);
  j.post("t-1", 1000, "payment");
  j.post("t-2", 9999, "payment");
  j.post("t-1", 250, "payment");
  assert.equal(j.balance("t-1"), 1250);
  assert.equal(j.balance("t-2"), 9999);
});

test("[t04_journal] balance of an unknown tenant is zero", async () => {
  const J = await Journal();
  assert.equal(new J(new FixedClock(0), []).balance("ghost"), 0);
});

test("[t04_journal] balance reflects the amounts after the policies ran", async () => {
  const J = await Journal();
  const Sign = await clsUnder(POLICY_DIR, "SignPolicy");
  const j = new J(new FixedClock(0), [new Sign()]);
  j.post("t-1", 1000, "payment");
  j.post("t-1", 400, "credit");
  assert.equal(j.balance("t-1"), 600);
});

test("[t04_journal] post folds every policy in order", async () => {
  const J = await Journal();
  const seen: string[] = [];
  const spy = (id: string, f: (a: number) => number): any => ({
    id,
    apply(entry: any) {
      seen.push(id);
      return { ...entry, amount: f(entry.amount) };
    },
  });
  const j = new J(new FixedClock(0), [
    spy("double", (a) => a * 2),
    spy("plus1", (a) => a + 1),
  ]);
  const entry = j.post("t-1", 100, "payment");
  assert.deepEqual(seen, ["double", "plus1"]);
  assert.equal(entry.amount, 201);
});

test("[t04_journal] policy order matters", async () => {
  const J = await Journal();
  const spy = (id: string, f: (a: number) => number): any => ({
    id,
    apply: (entry: any) => ({ ...entry, amount: f(entry.amount) }),
  });
  const j = new J(new FixedClock(0), [
    spy("plus1", (a) => a + 1),
    spy("double", (a) => a * 2),
  ]);
  assert.equal(j.post("t-1", 100, "payment").amount, 202);
});

test("[t04_journal] a policy sees the id and kind the journal assigned", async () => {
  const J = await Journal();
  let seen: any = null;
  const j = new J(new FixedClock(88), [
    {
      id: "spy",
      apply(entry: any) {
        seen = entry;
        return entry;
      },
    },
  ]);
  j.post("t-1", 100, "credit");
  assert.equal(seen.id, "je-1");
  assert.equal(seen.kind, "credit");
  assert.equal(seen.tenantId, "t-1");
  assert.equal(seen.at, 88);
});

/* ------------------------------------------------------- one test per policy */

test("[t04_journal] SignPolicy has id sign and negates a credit", async () => {
  const C = await clsUnder(POLICY_DIR, "SignPolicy");
  const p = new C();
  assert.equal(p.id, "sign");
  assert.equal(
    p.apply({ id: "je-1", tenantId: "t", amount: 500, kind: "credit", at: 0 }).amount,
    -500,
  );
});

test("[t04_journal] SignPolicy leaves other kinds alone", async () => {
  const C = await clsUnder(POLICY_DIR, "SignPolicy");
  const out = new C().apply({
    id: "je-1",
    tenantId: "t",
    amount: 500,
    kind: "payment",
    at: 0,
  });
  assert.equal(out.amount, 500);
});

test("[t04_journal] SignPolicy does not mutate its argument", async () => {
  const C = await clsUnder(POLICY_DIR, "SignPolicy");
  const entry = Object.freeze({
    id: "je-1",
    tenantId: "t",
    amount: 500,
    kind: "credit",
    at: 0,
  });
  const out = new C().apply(entry);
  assert.equal(entry.amount, 500);
  assert.equal(out.amount, -500);
});

test("[t08_minor_units] RoundPolicy has id round and rounds to a whole minor unit", async () => {
  const C = await clsUnder(POLICY_DIR, "RoundPolicy");
  const p = new C();
  assert.equal(p.id, "round");
  const out = p.apply({ id: "je-1", tenantId: "t", amount: 500.4, kind: "x", at: 0 });
  assert.equal(out.amount, 500);
  assert.ok(Number.isInteger(out.amount));
});

test("[t08_minor_units] RoundPolicy rounds up past the half", async () => {
  const C = await clsUnder(POLICY_DIR, "RoundPolicy");
  const out = new C().apply({ id: "je-1", tenantId: "t", amount: 500.6, kind: "x", at: 0 });
  assert.equal(out.amount, 501);
});

test("[t08_minor_units] RoundPolicy handles negative amounts", async () => {
  const C = await clsUnder(POLICY_DIR, "RoundPolicy");
  const out = new C().apply({ id: "je-1", tenantId: "t", amount: -500.6, kind: "x", at: 0 });
  assert.equal(out.amount, -501);
});

test("[t08_minor_units] RoundPolicy leaves a whole amount alone", async () => {
  const C = await clsUnder(POLICY_DIR, "RoundPolicy");
  const out = new C().apply({ id: "je-1", tenantId: "t", amount: 500, kind: "x", at: 0 });
  assert.equal(out.amount, 500);
});

test("[t04_journal] ClampPolicy has id clamp and leaves an amount within max alone", async () => {
  const C = await clsUnder(POLICY_DIR, "ClampPolicy");
  const p = new C(1000);
  assert.equal(p.id, "clamp");
  assert.equal(
    p.apply({ id: "je-1", tenantId: "t", amount: 999, kind: "x", at: 0 }).amount,
    999,
  );
});

test("[t04_journal] ClampPolicy clamps a positive amount to max", async () => {
  const C = await clsUnder(POLICY_DIR, "ClampPolicy");
  assert.equal(
    new C(1000).apply({ id: "je-1", tenantId: "t", amount: 5000, kind: "x", at: 0 }).amount,
    1000,
  );
});

test("[t04_journal] ClampPolicy clamps a negative amount keeping its sign", async () => {
  const C = await clsUnder(POLICY_DIR, "ClampPolicy");
  assert.equal(
    new C(1000).apply({ id: "je-1", tenantId: "t", amount: -5000, kind: "x", at: 0 }).amount,
    -1000,
  );
});

test("[t04_journal] ClampPolicy leaves an amount exactly at max alone", async () => {
  const C = await clsUnder(POLICY_DIR, "ClampPolicy");
  assert.equal(
    new C(1000).apply({ id: "je-1", tenantId: "t", amount: 1000, kind: "x", at: 0 }).amount,
    1000,
  );
  assert.equal(
    new C(1000).apply({ id: "je-1", tenantId: "t", amount: -1000, kind: "x", at: 0 }).amount,
    -1000,
  );
});

test("[t04_journal] the three policies preserve the other entry fields", async () => {
  const Sign = await clsUnder(POLICY_DIR, "SignPolicy");
  const Round = await clsUnder(POLICY_DIR, "RoundPolicy");
  const Clamp = await clsUnder(POLICY_DIR, "ClampPolicy");
  const entry = { id: "je-7", tenantId: "t-9", amount: 400, kind: "credit", at: 31 };
  for (const p of [new Sign(), new Round(), new Clamp(100000)]) {
    const out = p.apply(entry);
    assert.equal(out.id, "je-7");
    assert.equal(out.tenantId, "t-9");
    assert.equal(out.kind, "credit");
    assert.equal(out.at, 31);
  }
});
