import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock, SteppingClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { asAudit } from "./_support.ts";

/* ---------------------------------------------------------------- clocks */

test("[t01_core] FixedClock returns its instant", () => {
  assert.equal(new FixedClock(1234).now(), 1234);
});

test("[t01_core] FixedClock never advances", () => {
  const c = new FixedClock(999);
  assert.deepEqual([c.now(), c.now(), c.now()], [999, 999, 999]);
});

test("[t01_core] FixedClock supports a zero instant", () => {
  assert.equal(new FixedClock(0).now(), 0);
});

test("[t01_core] SteppingClock starts at start", () => {
  assert.equal(new SteppingClock(100, 5).now(), 100);
});

test("[t01_core] SteppingClock advances by step on each call", () => {
  const c = new SteppingClock(100, 5);
  assert.deepEqual([c.now(), c.now(), c.now(), c.now()], [100, 105, 110, 115]);
});

test("[t01_core] SteppingClock with a zero step is constant", () => {
  const c = new SteppingClock(7, 0);
  assert.deepEqual([c.now(), c.now()], [7, 7]);
});

test("[t01_core] SteppingClock instances are independent", () => {
  const a = new SteppingClock(0, 1);
  const b = new SteppingClock(0, 1);
  a.now();
  a.now();
  assert.equal(b.now(), 0);
});

/* ------------------------------------------------------------- audit log */

test("[t01_core] AuditLog starts empty", () => {
  assert.deepEqual(new AuditLog(new FixedClock(1)).entries(), []);
});

test("[t01_core] AuditLog.record appends actor, action, detail and clock time", () => {
  const log = new AuditLog(new FixedClock(4242));
  log.record("billing", "issue", "inv-1");
  assert.deepEqual(log.entries().map(asAudit), [
    { actor: "billing", action: "issue", detail: "inv-1", at: 4242 },
  ]);
});

test("[t01_core] AuditLog preserves insertion order", () => {
  const log = new AuditLog(new FixedClock(0));
  log.record("a", "1", "x");
  log.record("b", "2", "y");
  log.record("c", "3", "z");
  assert.deepEqual(
    log.entries().map((e) => e.actor),
    ["a", "b", "c"],
  );
});

test("[t01_core] AuditLog stamps each record with the clock's reading", () => {
  const log = new AuditLog(new SteppingClock(1000, 10));
  log.record("a", "1", "x");
  log.record("b", "2", "y");
  assert.deepEqual(
    log.entries().map((e) => e.at),
    [1000, 1010],
  );
});

test("[t01_core] AuditLog.entries returns a copy, not the live array", () => {
  const log = new AuditLog(new FixedClock(0));
  log.record("a", "1", "x");
  const first = log.entries();
  const second = log.entries();
  assert.notEqual(first, second);
  first.push({ actor: "z", action: "z", detail: "z", at: 0 });
  assert.equal(log.entries().length, 1);
});

test("[t01_core] AuditLog.clear empties the log", () => {
  const log = new AuditLog(new FixedClock(0));
  log.record("a", "1", "x");
  log.clear();
  assert.deepEqual(log.entries(), []);
});

test("[t01_core] AuditLog can record again after clear", () => {
  const log = new AuditLog(new FixedClock(3));
  log.record("a", "1", "x");
  log.clear();
  log.record("b", "2", "y");
  assert.deepEqual(log.entries().map(asAudit), [
    { actor: "b", action: "2", detail: "y", at: 3 },
  ]);
});
