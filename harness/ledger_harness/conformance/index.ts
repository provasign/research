// Entry point so that BOTH `node --test .conformance/` (which resolves a
// directory to its package.json "main") and `node --test '.conformance/*.test.ts'`
// run the whole suite. Node 26 does not expand a bare directory positional into
// its test files, so without this the directory form would run nothing.
import "./money.test.ts";
import "./clock-audit.test.ts";
import "./rules.test.ts";
import "./trace.test.ts";
import "./engine.test.ts";
import "./providers.test.ts";
import "./provider-audit-charge.test.ts";
import "./provider-audit-refund.test.ts";
import "./registry.test.ts";
import "./channels.test.ts";
import "./describe.test.ts";
import "./dispatcher.test.ts";
import "./middleware.test.ts";
import "./validators.test.ts";
import "./journal.test.ts";
import "./billing.test.ts";
import "./cli.test.ts";
import "./layout.test.ts";
