import { test } from "node:test";
import assert from "node:assert/strict";

import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { cls, CHANNELS, note } from "./_support.ts";

function build(C: any): any {
  const clock = new FixedClock(1);
  return new C(clock, new AuditLog(clock));
}

for (const c of CHANNELS) {
  test(`[t03_notify] ${c.cls}.validate accepts a valid message`, async () => {
    const C = await cls(c.spec, c.cls);
    assert.equal(build(C).validate(c.good()), true);
  });
}

for (const c of CHANNELS) {
  if (c.bad === undefined) continue;
  const bad = c.bad;
  test(`[t03_notify] ${c.cls}.validate rejects at its boundary`, async () => {
    const C = await cls(c.spec, c.cls);
    assert.equal(build(C).validate(bad()), false);
  });
}

for (const c of CHANNELS) {
  test(`[t03_notify] ${c.cls}.send returns validate's verdict`, async () => {
    const C = await cls(c.spec, c.cls);
    const ch = build(C);
    assert.equal(ch.send(c.good()), true);
    if (c.bad !== undefined) {
      assert.equal(ch.send(c.bad()), false);
    }
  });
}

test("[t03_notify] SmsChannel accepts exactly 160 characters and rejects 161", async () => {
  const C = await cls("../src/channels/sms.ts", "SmsChannel");
  const ch = build(C);
  assert.equal(ch.validate(note({ body: "x".repeat(160) })), true);
  assert.equal(ch.validate(note({ body: "x".repeat(161) })), false);
});

test("[t03_notify] PushChannel accepts exactly 64 characters and rejects 65", async () => {
  const C = await cls("../src/channels/push.ts", "PushChannel");
  const ch = build(C);
  assert.equal(ch.validate(note({ subject: "x".repeat(64) })), true);
  assert.equal(ch.validate(note({ subject: "x".repeat(65) })), false);
});

test("[t03_notify] InAppChannel never rejects", async () => {
  const C = await cls("../src/channels/inapp.ts", "InAppChannel");
  const ch = build(C);
  assert.equal(ch.validate({ tenantId: "", subject: "", body: "" }), true);
  assert.equal(ch.send({ tenantId: "", subject: "", body: "" }), true);
});

test("[t03_notify] EmailChannel ignores body length", async () => {
  const C = await cls("../src/channels/email.ts", "EmailChannel");
  assert.equal(build(C).validate(note({ subject: "s", body: "x".repeat(500) })), true);
});

test("[t03_notify] SlackChannel ignores the subject", async () => {
  const C = await cls("../src/channels/slack.ts", "SlackChannel");
  assert.equal(build(C).validate(note({ subject: "", body: "hi" })), true);
});
