import { test } from "node:test";
import assert from "node:assert/strict";

import { main } from "../src/cli.ts";

test("[t05_billing] main([]) returns 0", () => {
  assert.equal(main([]), 0);
});

test("[t05_billing] main tolerates extra argv entries", () => {
  assert.equal(main(["--verbose", "x"]), 0);
});

test("[t05_billing] main is repeatable", () => {
  assert.equal(main([]), 0);
  assert.equal(main([]), 0);
});
