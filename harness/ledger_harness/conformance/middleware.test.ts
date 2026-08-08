import { test } from "node:test";
import assert from "node:assert/strict";

import { RequestPipeline } from "../src/middleware.ts";
import { FixedClock } from "../src/clock.ts";
import { AuditLog } from "../src/audit.ts";
import { asAudit, clsUnder, MIDDLEWARE_DIR } from "./_support.ts";

const IDENTITY = (r: string): string => r;

/* --------------------------------------------------- one test per middleware */

test("[t03_notify] TrimMiddleware has id trim and trims before calling next", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "TrimMiddleware");
  const m = new C();
  assert.equal(m.id, "trim");
  assert.equal(m.handle("  hi  ", IDENTITY), "hi");
});

test("[t03_notify] TrimMiddleware passes the trimmed value downstream", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "TrimMiddleware");
  let seen = "";
  new C().handle("\t padded \n", (r: string) => {
    seen = r;
    return r;
  });
  assert.equal(seen, "padded");
});

test("[t03_notify] UpperMiddleware has id upper and uppercases the RESULT of next", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "UpperMiddleware");
  const m = new C();
  assert.equal(m.id, "upper");
  assert.equal(m.handle("ab", (r: string) => r + "cd"), "ABCD");
});

test("[t03_notify] UpperMiddleware does not uppercase what it passes downstream", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "UpperMiddleware");
  let seen = "";
  new C().handle("quiet", (r: string) => {
    seen = r;
    return r;
  });
  assert.equal(seen, "quiet");
});

test("[t03_notify] PrefixMiddleware has id prefix and prefixes the result of next", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "PrefixMiddleware");
  const m = new C(">> ");
  assert.equal(m.id, "prefix");
  assert.equal(m.handle("body", (r: string) => r + "!"), ">> body!");
});

test("[t03_notify] AuditMiddleware has id audit and records the request", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "AuditMiddleware");
  const clock = new FixedClock(55);
  const log = new AuditLog(clock);
  const m = new C(clock, log);
  assert.equal(m.id, "audit");
  m.handle("payload", IDENTITY);
  assert.deepEqual(log.entries().map(asAudit), [
    { actor: "pipeline", action: "handle", detail: "payload", at: 55 },
  ]);
});

test("[t03_notify] AuditMiddleware records before it calls next", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "AuditMiddleware");
  const clock = new FixedClock(1);
  const log = new AuditLog(clock);
  let lengthWhenNextRan = -1;
  new C(clock, log).handle("x", (r: string) => {
    lengthWhenNextRan = log.entries().length;
    return r;
  });
  assert.equal(lengthWhenNextRan, 1);
});

test("[t03_notify] AuditMiddleware returns whatever next returned", async () => {
  const C = await clsUnder(MIDDLEWARE_DIR, "AuditMiddleware");
  const clock = new FixedClock(1);
  const m = new C(clock, new AuditLog(clock));
  assert.equal(m.handle("x", () => "downstream"), "downstream");
});

/* --------------------------------------------------------------- pipeline */

test("[t03_notify] RequestPipeline with no middleware returns the request unchanged", () => {
  assert.equal(new RequestPipeline([]).run("  hi  "), "  hi  ");
});

test("[t03_notify] RequestPipeline runs the first middleware outermost", async () => {
  const Upper = await clsUnder(MIDDLEWARE_DIR, "UpperMiddleware");
  const Prefix = await clsUnder(MIDDLEWARE_DIR, "PrefixMiddleware");
  // upper outermost: it uppercases the prefixed result.
  assert.equal(new RequestPipeline([new Upper(), new Prefix("ab ")]).run("cd"), "AB CD");
  // prefix outermost: the prefix survives in its original case.
  assert.equal(new RequestPipeline([new Prefix("ab "), new Upper()]).run("cd"), "ab CD");
});

test("[t03_notify] RequestPipeline threads the request through trim then the rest", async () => {
  const Trim = await clsUnder(MIDDLEWARE_DIR, "TrimMiddleware");
  const Prefix = await clsUnder(MIDDLEWARE_DIR, "PrefixMiddleware");
  assert.equal(new RequestPipeline([new Trim(), new Prefix("[")]).run("  x  "), "[x");
});

test("[t03_notify] RequestPipeline nests in declaration order", () => {
  const order: string[] = [];
  const spy = (id: string): any => ({
    id,
    handle(req: string, next: (r: string) => string) {
      order.push(`enter-${id}`);
      const out = next(req);
      order.push(`exit-${id}`);
      return out;
    },
  });
  new RequestPipeline([spy("a"), spy("b"), spy("c")]).run("x");
  assert.deepEqual(order, [
    "enter-a",
    "enter-b",
    "enter-c",
    "exit-c",
    "exit-b",
    "exit-a",
  ]);
});

test("[t03_notify] RequestPipeline returns the innermost value when nothing transforms it", () => {
  const passthrough = (id: string): any => ({
    id,
    handle: (req: string, next: (r: string) => string) => next(req),
  });
  assert.equal(new RequestPipeline([passthrough("a"), passthrough("b")]).run("v"), "v");
});

test("[t03_notify] the audit middleware sees the request as the outer middleware left it", async () => {
  const Trim = await clsUnder(MIDDLEWARE_DIR, "TrimMiddleware");
  const Audit = await clsUnder(MIDDLEWARE_DIR, "AuditMiddleware");
  const clock = new FixedClock(9);
  const log = new AuditLog(clock);
  new RequestPipeline([new Trim(), new Audit(clock, log)]).run("  hello  ");
  assert.deepEqual(
    log.entries().map((e) => e.detail),
    ["hello"],
  );
});
