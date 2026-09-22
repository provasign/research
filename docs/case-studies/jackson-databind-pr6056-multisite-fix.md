# Case study: prism finds the real fix, native ships a plausible wrong one

**Task:** `FasterXML/jackson-databind` PR #6056 (post-cutoff, contamination-safe — merged after the model's training cutoff). Paired run, model=sonnet, arms=`baseline` (native grep/read) vs `prism_init` (real product setup: `prism init` + `prism index`, resident compact tool, no custom prompt engineering). 2026-09-21, `harness/results/guard-fix-run/`.

## The bug

`@JsonUnwrapped` properties bypass Jackson's `@JsonView` filtering during deserialization — a property that should be hidden under a given view leaks through anyway, because `UnwrappedPropertyHandler.processUnwrapped` never checks the active view before deserializing an unwrapped property. The correct fix threads an `activeView` parameter into `processUnwrapped` and updates **7 call sites** across `BeanDeserializer.java` and `BuilderBasedDeserializer.java` to pass it through.

The held-out regression test (`UnwrappedViewBypass6060Test`, 2 assertions) does not exist in the repository the agent sees — it ships with the fix's own test patch and is applied only at scoring time. Neither arm can see it while working. This is deliberate: it's what makes the result trustworthy rather than the agent pattern-matching a known answer.

## What native did

6 Greps, 1 Read, 1 Edit, 3 Bash calls. It read `UnwrappedPropertyHandler.java`, added an internal `visibleInView` check directly inside `processUnwrapped` — a self-contained, one-file change, no signature change, no call-site updates. It searched for a related test, found an *existing* one (`UnwrappedWithView1559Test` — not the held-out test), ran it, and it passed.

**It stopped there, confident.** Nothing told it the fix was incomplete. No error, no red test — because the test that would have caught the gap didn't exist yet in its view of the world.

Scored: `resolved=False`. The real fix needed the view threaded through all 7 callers; native's fix only worked in the one path it happened to check.

## What prism did

3 `mcp__prism__prism` calls up front (`search` for the handler and its call sites, then `search` for `visibleInView` usage), 1 `Read`, then — critically — **`change_impact` on `UnwrappedPropertyHandler.processUnwrapped`**. That's the operation that exists specifically to answer "what does changing this method's signature actually affect," and it surfaced all 7 real call sites in one call, not by grepping and hoping the pattern matched everything.

From there: added the `activeView` parameter, then 9 `Edit` calls methodically updating every one of the 7 call sites across both files (confirmed against the transcript: it named each site, worked through `BeanDeserializer.java`'s cases first, then `BuilderBasedDeserializer.java`'s remaining 3, using `replace_all` only once it had confirmed by inspection that both remaining sites shared identical context). Compiled clean, found and ran the existing view/unwrap test packages, all passed.

Scored: `resolved=True`.

## The cost, and why it's not waste

| | tokens | turns | resolved |
|---|---|---|---|
| native | 476,306 | 13 | ❌ |
| prism | 1,724,296 | 28 | ✅ |

3.62x the tokens. On its own, that number looks like exactly the kind of prism-arm blowup this whole investigation has been hunting down and fixing (see `../overnight-run/INVESTIGATION.md` and the read-guard hook in `harness/hooks/`). It isn't. Traced the transcript directly: **zero** guard-hook denials fired — there was no redundant re-reading here to catch. The extra tokens bought 9 real edits across 2 files instead of native's 1, because the task genuinely required 7x the edit surface that native touched. Paying more here is the correct trade, not an inefficiency.

## The actual finding

This is the shape of bug that `change_impact` exists for — a signature change whose correctness depends on enumerating every caller, not on finding *a* plausible edit location. Native's failure mode wasn't carelessness: it made a locally reasonable, testable, passing change. It had no way to discover the gap, because the evidence that would reveal it (the other 6 call sites, and the specific behavior the missing test checks) isn't something grep incidentally surfaces — you have to already know to look for it, which is exactly the blast-radius question `change_impact` answers directly instead of hoping to stumble into.

**What this means for a real (non-benchmark) coding session:** an agent shipping this fix wouldn't crash or visibly fail — it would report success, backed by a real passing test, on a change that's actually incomplete. That's a quieter, more dangerous failure mode than an error message, and it's exactly what PR review and CI regression suites exist to catch. Given the failing test, recovery is a narrow, well-scoped follow-up (this codebase's own `prism_source_esc` arm design — widen only after an observed failure — is built for precisely that moment). Without it, the incomplete fix ships as if it were done.

## Source

- Raw cells: `harness/results/guard-fix-run/results.json` (task `FasterXML__jackson-databind__pr6056`)
- Native transcript: tool sequence and reasoning available via session transcript archaeology (see investigation methodology in `../overnight-run/INVESTIGATION.md`)
- Task definition incl. held-out gold test: `harness/tasks/e2e/FasterXML__jackson-databind__pr6056.json`
