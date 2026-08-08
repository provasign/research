import { test } from "node:test";
import assert from "node:assert/strict";

import { money, add, sub, mul, format } from "../src/money.ts";

/* money() converts dollars to integer minor units (t08). */

test("[t08_minor_units] money(12.34) is 1234 cents", () => {
  assert.equal(money(12.34), 1234);
});

test("[t08_minor_units] money(0) is 0", () => {
  assert.equal(money(0), 0);
});

test("[t08_minor_units] money(1) is 100", () => {
  assert.equal(money(1), 100);
});

test("[t08_minor_units] money is negative-safe", () => {
  assert.equal(money(-5.5), -550);
});

test("[t08_minor_units] money rounds to a whole cent", () => {
  assert.equal(money(1.234), 123);
  assert.equal(money(1.236), 124);
});

test("[t08_minor_units] money always returns an integer", () => {
  for (const d of [0.1, 2.675, 19.999, -3.333, 1234.5678]) {
    assert.ok(Number.isInteger(money(d)), `money(${d}) must be an integer`);
  }
});

test("[t08_minor_units] money of a large dollar figure", () => {
  assert.equal(money(25000), 2500000);
});

/* add / sub are plain integer arithmetic (t01, unchanged by t08). */

test("[t01_core] add sums two amounts", () => {
  assert.equal(add(500, 250), 750);
});

test("[t01_core] add handles negatives", () => {
  assert.equal(add(500, -750), -250);
});

test("[t01_core] add with zero is identity", () => {
  assert.equal(add(1234, 0), 1234);
});

test("[t01_core] sub subtracts", () => {
  assert.equal(sub(1000, 250), 750);
});

test("[t01_core] sub can go negative", () => {
  assert.equal(sub(250, 1000), -750);
});

test("[t01_core] add and sub keep integers integral", () => {
  assert.ok(Number.isInteger(add(3, 4)));
  assert.ok(Number.isInteger(sub(3, 4)));
});

/* mul is Math.round(m * factor) (t08). */

test("[t08_minor_units] mul scales an amount", () => {
  assert.equal(mul(1000, 0.5), 500);
});

test("[t08_minor_units] mul rounds the product to an integer", () => {
  assert.equal(mul(101, 0.5), 51);
  assert.ok(Number.isInteger(mul(333, 0.1)));
});

test("[t08_minor_units] mul uses Math.round semantics on a negative half", () => {
  assert.equal(mul(-105, 0.5), -52);
});

test("[t08_minor_units] mul by 1 is identity", () => {
  assert.equal(mul(12345, 1), 12345);
});

test("[t08_minor_units] mul by 0 is 0", () => {
  assert.equal(mul(12345, 0), 0);
});

test("[t08_minor_units] mul never produces a fractional amount", () => {
  for (const f of [0.07, 0.33, 1.08, 0.915]) {
    assert.ok(Number.isInteger(mul(9999, f)), `mul(9999, ${f}) must be an integer`);
  }
});

/* format renders minor units as dollars (t08). */

test("[t08_minor_units] format(123450) is $1234.50", () => {
  assert.equal(format(123450), "$1234.50");
});

test("[t08_minor_units] format(0) is $0.00", () => {
  assert.equal(format(0), "$0.00");
});

test("[t08_minor_units] format of a sub-dollar amount keeps two decimals", () => {
  assert.equal(format(5), "$0.05");
  assert.equal(format(50), "$0.50");
});

test("[t08_minor_units] format of a whole dollar", () => {
  assert.equal(format(100), "$1.00");
});

test("[t08_minor_units] format of a negative amount", () => {
  // SPEC pins "leading $, always 2 decimals" but never says where the sign
  // goes. Both "$-1234.50" and "-$1234.50" are faithful readings, so accept
  // either — grading a candidate against the reference's arbitrary choice
  // measures conformity to the reference, not to the contract.
  assert.ok(
    ["$-1234.50", "-$1234.50"].includes(format(-123450)),
    `format(-123450) was ${JSON.stringify(format(-123450))}`,
  );
});

test("[t08_minor_units] format uses no thousands separator", () => {
  assert.equal(format(123456789), "$1234567.89");
  assert.ok(!format(123456789).includes(","));
});
