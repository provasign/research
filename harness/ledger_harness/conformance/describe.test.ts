// t09: NotificationChannel gains a required describe(); Dispatcher gains
// descriptions(). One test per channel implementation.
import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { Dispatcher } from "../src/notify.ts";
import { cls, CHANNELS, stubChannel } from "./_support.ts";

function build(C: any): any {
  const clock = new FixedClock(1);
  return new C(clock, new AuditLog(clock));
}

for (const c of CHANNELS) {
  test(`[t09_describe] ${c.cls}.describe() returns "${c.id} channel"`, async () => {
    const C = await cls(c.spec, c.cls);
    assert.equal(build(C).describe(), `${c.id} channel`);
  });
}

test("[t09_describe] Dispatcher.descriptions returns one description per channel, in channel order", () => {
  const dispatcher = new Dispatcher([
    stubChannel("one", true),
    stubChannel("two", false),
    stubChannel("three", true),
  ]);
  assert.deepEqual(dispatcher.descriptions(), [
    "one channel",
    "two channel",
    "three channel",
  ]);
});

test("[t09_describe] Dispatcher.descriptions follows construction order, not id order", () => {
  const dispatcher = new Dispatcher([
    stubChannel("zeta", true),
    stubChannel("alpha", false),
  ]);
  assert.deepEqual(dispatcher.descriptions(), ["zeta channel", "alpha channel"]);
});

test("[t09_describe] Dispatcher.descriptions includes channels that reject messages", () => {
  const dispatcher = new Dispatcher([stubChannel("a", false), stubChannel("b", false)]);
  assert.deepEqual(dispatcher.descriptions(), ["a channel", "b channel"]);
});

test("[t09_describe] an empty Dispatcher has no descriptions", () => {
  assert.deepEqual(new Dispatcher([]).descriptions(), []);
});
