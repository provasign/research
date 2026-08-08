import { test } from "node:test";
import assert from "node:assert/strict";

import { Dispatcher } from "../src/notify.ts";
import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { cls, CHANNELS, note, stubChannel } from "./_support.ts";

test("[t10_rename_move] fanout returns the ids of the channels that accepted, in channel order", () => {
  const dispatcher = new Dispatcher([
    stubChannel("one", true),
    stubChannel("two", false),
    stubChannel("three", true),
  ]);
  assert.deepEqual(dispatcher.fanout(note()), ["one", "three"]);
});

test("[t10_rename_move] fanout of an empty dispatcher is empty", () => {
  assert.deepEqual(new Dispatcher([]).fanout(note()), []);
});

test("[t10_rename_move] fanout returns empty when every channel rejects", () => {
  const dispatcher = new Dispatcher([stubChannel("a", false), stubChannel("b", false)]);
  assert.deepEqual(dispatcher.fanout(note()), []);
});

test("[t10_rename_move] fanout hands the same message to every channel", () => {
  const a = stubChannel("a", true);
  const b = stubChannel("b", true);
  const msg = note();
  new Dispatcher([a, b]).fanout(msg);
  assert.deepEqual(a.seen, [msg]);
  assert.deepEqual(b.seen, [msg]);
});

test("[t10_rename_move] fanout preserves construction order, not id order", () => {
  const dispatcher = new Dispatcher([stubChannel("z", true), stubChannel("a", true)]);
  assert.deepEqual(dispatcher.fanout(note()), ["z", "a"]);
});

test("[t03_notify] fanout over the six real channels reflects each one's verdict", async () => {
  const clock = new FixedClock(1);
  const log = new AuditLog(clock);
  const channels: any[] = [];
  for (const c of CHANNELS) {
    const C = await cls(c.spec, c.cls);
    channels.push(new C(clock, log));
  }
  // subject empty -> email rejects; body empty -> slack rejects; the rest accept.
  const delivered = new Dispatcher(channels).fanout({
    tenantId: "t-1",
    subject: "",
    body: "",
  });
  assert.deepEqual(delivered, ["sms", "webhook", "push", "inapp"]);
});

test("[t10_rename_move] Dispatcher.dispatch no longer exists on the instance", () => {
  const dispatcher: any = new Dispatcher([stubChannel("a", true)]);
  assert.equal(dispatcher.dispatch, undefined, "dispatch must not exist — no alias");
});

test("[t10_rename_move] Dispatcher.dispatch no longer exists on the prototype", () => {
  assert.equal(
    Object.prototype.hasOwnProperty.call(Dispatcher.prototype, "dispatch"),
    false,
    "Dispatcher.prototype must not carry a dispatch method",
  );
});

test("[t10_rename_move] fanout is the dispatch method", () => {
  assert.equal(typeof new Dispatcher([]).fanout, "function");
});
