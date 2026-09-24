# Handoff: prism state and direction, 2026-09-22

Supersedes every earlier handoff (prism/HANDOFF.md, prism/docs/harness-handover-2026-09-13.md,
research/docs/HANDOFF-2026-09-22.md — all deleted). Everything below is graded; do not
upgrade a "single-run" or "estimate" to a pattern without the rerun.

## TL;DR

- **The win is resolve rate, not tokens.** guard-fix-run (50 tasks, sonnet, `baseline` vs
  `prism_init`): native 31/50 (62%), prism 36/50 (72%); tokens 1.062x (0.932x excluding 3
  wide-blast-radius outliers). Adoption 49/50. Same direction repeated in residency-ab (13)
  and guard-hook-ab (13). Moderate sample, three runs, consistent shape.
- **Where the tokens go: turns, not bytes.** In the prism arm, 95.5% of spend is
  `cache_read` — the accumulated context re-billed every turn (~51K tokens/turn, ~27
  turns/session). All fresh tool output combined is ~1% of spend. **Cost of a delivered
  byte = bytes × turns remaining; cost of one avoidable turn ≈ 50K tokens (~6% of the run
  per turn per session).** Every payload-trimming arc that measured as "wash" was pulling
  the additive lever. Design for fewer round trips, not smaller responses.
- **Released:** prism v0.81.0 (`prism init --read-guard` / `--no-read-guard`),
  prism v0.81.1 + grove v0.58.3 (`prism doctor` reports Grove's per-language capability
  manifest under `languages`), a test-only fix for a pipe deadlock in `captureStdout`/
  `capture` that hung windows-latest. Tap at v0.81.1.
- **Released v0.82.0 (2026-09-23, tap refreshed):** search's exact-term full-body
  threshold raise (cd26e452; 50-task A/B: resolve 31→33, tokens flat) and `verify`'s
  new informational `testCoverage` field for body-only changes (fff21dd8, 675ddd93 CLI
  rendering, a9231954 skips `<top-level>` pseudo-symbols). Gate: `go test ./...` +
  `ci_invariants.py` all held.
- **H3 A/B RUNNING (launched 2026-09-23 21:41, `harness/results/h3-ab/pass{1,2,3}/`):**
  control = main binary (`/tmp/prism-h3-control`, has the field, steering unchanged —
  verify "never a required closing step"); treatment = branch `h3-verify-steering`
  (`/tmp/prism-h3-treatment`, prism commit fb864107): steering mandates one
  `verify({})` and a `testCoverage` read before declaring a change finished, with
  instructions for a "no verified test caller" warning and for the "already fixed"
  conclusion. Bed = the 19 movable tasks only (12 always-fail + 7 flip; the 30
  always-pass tasks cannot move), 3 passes per arm. **Probe (click pr3678, treatment):
  the agent called verify at the end for the first time on a hard-core task, saw the
  warning on `Command.get_help_option_names`, ran one more search, then stopped —
  still failed. Adoption moved; behavior only nudged.** The branch is NOT merged; merge
  only if the run shows more hard-core tasks resolving than the 45–46/50 noise allows.
- **Where the failures actually are (H1, 12 hard-core tasks, all 4 cells each):** none
  are retrieval misses — the two "wrong file" agents had the gold file in their first
  search result and edited elsewhere; the rest are unfinished or subtly wrong edits at
  the right place, confirmed by a test run that could not have caught the gap. Every
  one stops the moment some check passes. `change_impact` was called 0 times in all of
  them (real adoption gap; on the two traced it would not have closed the gap).
- **Next step, not started:** the actual test of H3 — steer the agent to read
  `verify`'s `testCoverage` before declaring done, rerun the 50-task bed (paired, ≥3
  passes per arm; single passes cannot resolve <5 tasks). Nothing built tonight has
  yet been shown to move a hard-core failure.
- **Rejected after measurement (don't reopen without new evidence):** byte cap on
  `search`; delta delivery for extending `read` ranges; per-language budget tiers;
  cost-aware disclosure as its own lever (surface features predict "later edited" at
  break-even only).

## Confirmed this cycle

**Read-guard hook (controlled A/B, 13 tasks, hook-on vs hook-off, byte-identical setup).**
`harness/results/guard-hook-ab/`: hook-on 0.89x tokens (9.29M vs 10.44M), resolve 10/13 both
arms, same three failures. Holds at 0.94x excluding flagged outliers. First non-confounded
measurement; supersedes the earlier "wash" note. Shipped as an opt-in `prism init` flag
(commit 4c46f607): embeds the two hook scripts, writes `.claude/hooks/`, registers
PostToolUse (`mcp__prism__prism`) + PreToolUse (`Read`) entries; uninstall removes only
prism's own entries (tested against a seeded user hook on the same matcher). Opt-in, not
prompted, matching `--deny-builtin-search` precedent (the interactive prompt for that flag
was reverted in v0.52.0 after it skewed two runs). The help text still says
`--deny-builtin-search` is "asked interactively" — that line is stale.

**Redundant reads are rare.** Corpus-wide (1,300 prism-using sessions): 0.5–0.7% of native
Reads overlap ≥70% with an earlier prism delivery, checking read/lookup/search/query windows.
In guard-fix-run's prism arm: 78 Reads, 2 full + 4 partial re-reads, in 6 tasks; 5 of 6
traced to a `search` delivery, which the shipped hook does not track (it tracks read/lookup).
Directional only at this n. When it happens it is expensive per occurrence, which is why a
rare event still produced an 11% aggregate win.

**3–5-call cells cost more because the tasks are harder, not because payloads compound.**
24 cells with session_id: bytes/call flat across call-count buckets (3.6K, 5.5K, 3.0K, 4.0K,
4.8K, 4.0K, 3.8K for 1/3/4/5/6/7/11 calls); call count correlates with session tokens
(r=0.79) — confound confirmed. Replicates in live dogfooding at n=612 (r=0.35; 1–2 calls
80K mean, 3–5 250K, 6–10 1.0M, 11+ 3.37M).

**Byte concentration is legitimate completeness.** Top 10% of calls carry 42–50% of bytes
for search/change_impact/lookup; the biggest are wide-fan-out symbols in benchmark repos
(`Map`, `host_matching`, `JsonUnwrapped`). `query` self-limits at ~8K tokens (score-trimmed,
`selection.go`); `change_impact` has an 8192-byte evidence sub-budget + 40-site relay cap +
wideImpact degradation; `search` has count caps only (25 / 2000 exhaustive), no byte cap.

**Turn anatomy (guard-fix-run, 50 prism-arm sessions).**
- Tool-result bytes: Bash 33% (341 calls), prism:search 27% (61 calls, 6.7KB avg), Read 17%
  (78), prism:lookup 9%, prism:read 6%, prism:query 4% (2 calls, both ~31KB), change_impact
  1% (7 calls), verify <1% (2 calls).
- Bash by category: build/test 145 calls / 353KB (largest), other 45, shell-misc 41, git 37,
  grep/rg 30, ls/find 23, cat/sed 8. Native arm: build/test 169, grep/rg 76, git 53.
- Tool calls before first Edit: prism 6.7/session vs native 8.5 (prism saves ~1.8 pre-edit
  turns); after first Edit: 7.9 vs 7.7. Prism's per-turn footprint is larger (51K vs 44K).
  That pair of facts is where cost parity comes from.
- 96% of prism bytes land before the first edit (652KB vs 26KB) and are then re-billed for
  ~8 build/test turns.
- 33 of 139 prism calls (24%) were followed within two tools by a native Read of a file the
  result had just pointed at (locator→body two-step).
- Footprint by later use: 40% of prism bytes are bodies in files later edited, 39% bodies in
  files never edited, 21% headers/locators. By op: read 93% edited (agent asks for what it
  needs), change_impact 64%, lookup 41% (+49% headers), search 29% edited / 53% never edited,
  query 32% / 62%. Search's never-edited bodies alone are ~30% of the total prism footprint.
  "Never edited" is not "useless" — confirming a caller needs no change is completeness
  work — so treat this as the ceiling of removable weight, not the target.

## Rejected after measurement

- **Byte cap on `search`.** Capping every call at 8KB in guard-fix-run saves 24% of search
  bytes = ~98KB fresh, <1% of the run even compounded. Big search payloads coincided with
  prism wins (4) about as often as losses (3–4) among flagged cells; a cap cannot tell the
  padding from the caller that has the bug. Topo: not in favor of artificial caps. Agreed.
- **Delta delivery for extending `read` ranges.** Infrastructure exists
  (`deliveredRanges`/`deliveredRangeCovered` in `internal/mcp/delivery.go`, binary
  covered/not-covered). Only 9 extend events in 117 ranged reads corpus-wide; plus a
  correctness risk if the agent's earlier copy was compacted away. Low value.
- **Per-language budget tiers.** In guard-fix-run, `query` was called twice (both Java, both
  at the cap, both in pr6019 — a task already retracted once as non-replicating);
  `change_impact` never within 25% of its cap; other languages made zero query/impact calls.
  No data to build a tier on.

## Where prism can be more intelligent (turn objective)

Ranked by cheapness to prove. All impact figures are estimates from the 50-session anatomy.

1. **Collapse locator→body: DONE and measured (2026-09-23, commit cd26e452).**
   `searchevidence.go` only delivered a search hit's full enclosing body when the symbol was
   ≤20 lines; anything bigger got a windowed ±9 lines, even for an exact term match, forcing
   the 33-of-139 locator→body follow-up Reads found earlier. Raised the threshold to
   `compactSearchBodiesLegacy`'s existing 160-line/10000-byte bound (shared constants
   `searchFullBodyMaxLines`/`searchFullBodyMaxBytes` in delivery.go) — only for exact-term
   hits, never fuzzy "related spelling" guesses, and `selected` was already capped upstream
   so a broad search still windows every hit.
   **50-task A/B** (`prism_body_baseline` vs `prism_body_exp`, same binary-swap harness
   pattern as the read-guard hook, guard-fix-run's manifest,
   `harness/results/search-body-ab/`): resolved 31/50 → 33/50, tokens 0.998x overall
   (~1.02x excluding the 4 largest per-task ratio outliers each direction — essentially
   flat, not a token-savings win). 4 resolve mismatches: 3 improvements
   (jackson-databind pr6019, pr6061; jansson pr731) vs 1 regression (click pr3471).
   **Caveat: one of the three improvements (pr6019) is the exact task already flagged
   elsewhere in this doc as non-replicating on a single run** ("Rejected after
   measurement" section) — treat the net resolve gain as directionally positive
   (flat-cost, safe-by-construction change that can only add information) rather than a
   confirmed +2-task result; would want a rerun before citing the number externally.
   **Theory check (`ab_theory_check.py`, both arms' transcripts by session_id):**
   - The mechanism fired: search windows 96→34, full bodies 108→153, locator→body
     follow-up Reads 31→20 (−35%), native Reads 81→68. API turns 1,327→1,268 (−4.4%).
     Per-task turn delta vs token delta: r = 0.97 — cost is turns, confirmed hard.
   - Why tokens still came out flat: (a) the mechanism removed 11 follow-up Reads across 50
     sessions = 0.2 turns/session, not the 0.66 estimated (20 follow-up Reads remain even
     after a full body — agents re-read past the symbol or read files delivered as
     locators); (b) bigger bodies added +60KB of search bytes, so context re-billed per
     turn rose 48,990→50,511 (+3.1%), eating the turn saving; (c) Bash calls rose 308→340
     (+32 turns) from ordinary agent variance. The 15 tasks where the change did not fire
     moved 210→205 turns — that is the noise floor, and the biggest per-task swings
     (pr6076 +49 turns, pr6039 −70) are agent behavior, not the mechanism.
   - Verdict: the theory's structure holds (turns drive cost); the sizing of this
     intervention was ~3x too optimistic, and I left out the footprint term I had
     derived myself (a bigger first delivery is re-billed on every later turn). Apply
     cost = bytes × remaining-turns to BOTH sides of any future change. Keep the change
     (flat cost, resolve directionally up, safe by construction); do not cite a token
     saving for it. Anything under ~±4% needs paired reruns, not one pass of 50.
2. **Own the verification turn — estimated from transcripts
   (`harness/analysis/token-survey/verify_estimate*.py`).** 142 build/test-ish Bash turns in
   the prism arm (2.9/session): 57% targeted test, 25% full/broad suite, 18% toolchain
   wrangling (venv, pip install, mvn flags, git stash), 1% compile-only. 95 of them run
   back-to-back with no edit in between (81 immediately consecutive: build→test,
   targeted→full, flag tweaks, env setup→test); 6 are literal same-command reruns. Host
   truncated 19/145 outputs. The fix loop is NOT where turns go: strict failing runs 19, only
   1 followed by an edit — "structured failure shortens the fix loop" is unsupported.
   The turn estimate is the chains: ≤95 collapsible turns ≈ 1.9/session × ~50K ≈ 4.75M ≈
   11.6% of the run as an upper bound if one `verify` call absorbs env setup + compile +
   selected tests; ~6% is the realistic planning number. Test-output bytes are minor (358KB,
   ~0.8% re-billed). **The resolve-rate signal is the sharper one:** FAILED tasks ran tests
   13/14 times and saw green (4 strict failures in 51 runs) — they pass the wrong tests.
   Resolved tasks ran the oracle test module 17/36 (47%), FAILED 4/14 (29%); FAILED ran a
   broad suite 8/14 vs 13/36. Test selection by changed-symbol coverage ("the tests covering
   what you changed are X, Y — you ran only X") is the mechanism, and it is a `verify` op,
   not the rejected Prism 2.0 edit-moment hook. Needs an A/B; the n here is 14 failures.
3. **Cost-aware disclosure (footprint) — measured, negative as a standalone lever.**
   Predictor test on the 180 search bodies in the 50 sessions
   (`harness/analysis/token-survey/disclosure_predictor.py`): later-edited base rate 43%.
   Rank does not predict (ranks 1–4 all 39–51% edited). Only two features separate:
   test-file bodies (0/25 edited — partly a benchmark artifact, the task tail forbids test
   edits) and bodies not containing the search term (2/20 edited). The safe rule (demote
   test-file or term-absent bodies) is 95% correct but frees only 32KB ≈ 0.4% of the run;
   every broader rule sits at 59–63% correctness, i.e. break-even against the ~50K cost of a
   wrong demotion. Surface features cannot tell the body the agent will edit from the one
   it will only read; the agent's own request is the signal (`read` bodies: 93% edited).
   Keep disclosure as the guardrail for #1 (don't over-deliver when collapsing
   locator→body), not as its own project.

## Resolve-rate reliability on this 50-task bed (2026-09-23, `resolve_reliability.py`)

Three prism_init-config runs of the same 50 tasks (guard-fix-run prism arm, search-body-ab
baseline, search-body-ab exp) plus one native arm:
- **Test-retest agreement is 45–46/50** between any two prism runs — 4–5 tasks flip per
  pass with no relevant change. That is the noise floor for resolve: a single n=50 A/B
  cannot see anything smaller than ~5 tasks.
- **30 tasks always pass, 13 always fail, 7 flip.** 12 of the 13 always-fail tasks also
  fail native — they fail in all four cells. The benchmark's movable range for a context
  tool is therefore the 7 flaky tasks (+ psf/requests pr7315, native-only pass); the
  62%→72% headline is mostly "prism wins the flaky ones more often," not "prism solves
  tasks native cannot."
- Implication: resolve-rate work on this bed has two options — (a) paired reruns (≥3 per
  arm) to average out the 7 flippers, or (b) study the 12 hard-core failures directly
  (diff vs gold patch; each has 4 transcripts) to learn what kind of failure they are,
  since no retrieval change has moved any of them.

## H1 result: what kind of failure are the 12 hard-core tasks? (2026-09-23, `h1_failure_classify.py`)

Compared each hard-core task's agent diff (`prism_body_exp`, most recent run) against
the gold patch's files and hunk ranges (±3 line slack).

| bucket | n | tasks |
|---|---|---|
| Right file + region, hunks match closely, still failed | 3 | jansson pr740 (173-187 vs agent 173-186 — nearly identical), commons-lang pr1655, gin pr4805 |
| Right file + region, but clearly incomplete (missing whole gold hunks) | 5 | commons-lang pr1703 (missed 1 of 2 hunks), gin pr4535 (gold hunk is 71 lines, agent's is 6), click pr3473 (gold spans 6 hunks/~150 lines across the file, agent touched 2 small ones near the end, missed the rest entirely), click pr3678 (missed 3 of 4 hunks), jackson pr6076 (agent's range is a narrower subset of gold's 4 hunks, plus touched an extra file gold didn't) |
| Wrong file entirely | 2 | jackson pr6018 (agent edited `UnwrappingBeanPropertyWriter.java`, gold touches `BeanSerializerBase.java`+`StdConvertingSerializer.java`), jackson pr6044 (agent edited `StdTypeResolverBuilder.java`, gold touches `TypeResolverProvider.java`) |
| No edit at all | 2 | jackson pr6052, click pr3504 — agent produced an empty diff |

**10 of 12 found the right file.** Only 2 are retrieval-attributable (wrong file). The
dominant failure mode (5, arguably 8 including the close-match group) is an incomplete or
subtly-wrong fix at the RIGHT location — the agent stopped before covering the gold
patch's full extent, or edited the right lines with the wrong content. This is the same
shape as last night's finding (failed tasks pass the wrong/insufficient tests and stop
confident) — an agent that ran only part of the relevant test coverage would not notice
an incomplete fix. **Conclusion: H3 (verify runs the tests that cover what changed) is
the higher-leverage path on this bed, not more retrieval work — retrieval already gets
the agent to the right file 10/12 times; the fix quality and the check on it are what's
missing.**

**Follow-up on the 4 "different" cases (transcript tails, `/tmp/tail_look.py` pattern) —
they are NOT a different failure mode, they are the same one:**
- **jackson pr6018 and pr6044 (the two "wrong file" cases) are not retrieval misses —
  checked against the raw tool_use trace, not inferred from the final diff.** In both
  sessions the agent's FIRST `search` call returned the gold file by name in the results
  (`BeanSerializerBase.java` for pr6018, `TypeResolverProvider.java` for pr6044). The
  agent had the correct location in front of it on turn one and edited a different,
  plausible-looking file instead, then ran a narrow or full test command (pr6044 ran
  the full 6925-test suite, all green) and wrote a confident summary. Retrieval
  succeeded; the agent didn't act on what it was given. Same stop-on-insufficient-check
  mechanism as the incomplete-fix bucket, with an extra layer: the check passed AND the
  right answer was already visible and unused.
  **Open gap, not yet closed:** `change_impact` was called ZERO times across all 10 of
  the incomplete-fix/close-match/wrong-file sessions (checked via tool_use trace) — only
  locate-and-fetch ops (`search`/`lookup`) were ever used. Retroactively ran
  `change_impact` for two of the five incomplete-fix cases to see whether it would have
  surfaced what was missed: **commons-lang pr1703 — no, the missed hunk is inside the
  SAME method as the covered one (an unfinished edit, not a missed call site);
  click pr3473 — unclear, the missed site is a new-feature-threading gap between two
  unrelated classes (`Argument.__init__` and `Command`'s help renderer) that
  `change_impact`'s existing-call-edge model wouldn't obviously connect.** Zero adoption
  of the completeness op is real and worth watching once `verify` exists, but on the two
  cases actually traced, it does not look like the fix — these remain completeness-of-
  the-agent's-own-edit problems, which is what `verify`/H3 already targets.
- **jackson pr6052 and click pr3504 (the two "empty diff" cases) are the agent
  concluding "already fixed," not giving up.** Both explicitly reasoned that the
  repo already contains the fix and ran (targeted or full) tests to confirm before
  stopping. **pr3504 additionally surfaced a real, distinct, reproducible bug in the
  agent's own verification hygiene**, in its own words: "My earlier failures were from
  accidentally testing against a separately pip-installed click package rather than
  this repo's source; once run against the repo's `src/`, everything passes cleanly" —
  it tested the wrong install, got a false pass, and stood down. That is not a context
  problem prism can fix by delivering more/better code; it is "verify against the
  checkout, not whatever `pip`/`site-packages` resolves to," a one-line class of
  steering or a `verify` precondition, independent of H3's test-selection design.

**Revised bottom line: all 12 hard-core failures share one mechanism — the agent stops
as soon as SOME check it ran passes, and that check was never guaranteed to be the one
that would have caught the actual gap** (wrong test scope, hidden regression test not
yet present, or the wrong installed package entirely). Retrieval quality is not
distinguishing solved from unsolved tasks on this bed at all.

**The installed-vs-checkout fix (2026-09-23, commit 95bad27b, harness):** added one
instruction to the shared `TASK_TAIL` in `run_e2e.py` (applies to every arm, not
prism-specific — this was never a prism problem) telling the agent to confirm its test
run exercises the edited checkout and to install editable/local if it builds an
isolated environment. **Smoke-tested by rerunning the one known-affected task
(click pr3504) and reading the transcript, not by resolve rate:** the agent now
explicitly runs `pip install -e .` and prints `click.__file__` to confirm it resolves
to the checkout (`.../e2e-run-.../src/click/__init__.py`, not site-packages) before
testing. The installed-vs-checkout confusion is confirmed gone by direct evidence.
**The task still fails** — with verification now correct, the agent concludes "already
fixed" against a checkout that (per the gold patch) is not, which is the general H3
failure mode, not this fix's target. Treat this as done and validated for its narrow
purpose; it does not move resolve rate on this bed since only one known task had this
specific bug, and the deeper problem underneath it is H3's, not solved by this.

**H3 is now the only path forward on this bed** — retrieval and the installed-vs-checkout
guard have both been checked and are not where the remaining failures live.

## H3, first slice: `verify` reports test coverage for body-only changes (2026-09-23, prism commit fff21dd8)

`verify`'s existing pipeline only ever produces a seed (missed-caller check) from a
signature change, rename, removal, or interface/type member extraction — a pure body
edit, the shape of an ordinary bug fix, was invisible to it entirely, which is exactly
why every one of the 12 hard-core failures (all body-only changes) sailed through
"complete" with zero missed sites. Added a new, non-gating pass: for every changed
function/method/constructor regardless of contract status, look up its callers via the
same `ChangeImpactScoped` call `change_impact` already uses, and report which are
verified test callers under a new `testCoverage` field. No verified caller → an explicit
warning instead of silently passing. Deliberately never touches `verdict`/`gateFailure`
— this signal hasn't earned gating trust the way the existing seed pipeline has.

Validated two ways: a new unit test (`TestToolVerify_TestCoverageForBodyOnlyChange`,
two functions, one with a real test caller, one without, checks both the JSON and text
renderer) and a real-world check against `commons-lang pr1703`'s actual agent diff —
correctly reported 22 covering test call sites for the half-fixed function, confirming
(not just asserting) that this specific failure is a within-function completeness gap,
not a missing-coverage one, exactly matching the earlier transcript analysis. No false
positive on the one real case checked. `go test ./...` green throughout.

**Known gap, not yet fixed:** the CLI's plain-text `prism verify` output (`cmdVerify` in
`internal/cli`, a separate renderer from the MCP path's `renderVerifyAsText`) does not
yet surface `testCoverage` — confirmed via `--format json`, which does carry it. Lower
priority since agents consume the MCP tool, not the CLI text path, but worth a follow-up
fix so a human running `prism verify` from the terminal sees the same signal.

**Not yet done, and this is the part that actually tests H3's thesis:** the new field
exists and is correct, but nothing yet tells the agent to USE it before declaring a fix
verified, and nothing has re-run the 12-task bed with steering that says so. That A/B —
does surfacing "no verified test caller" change agent behavior on the actual failure
set — is the real test of whether this closes any of the 12, and hasn't been run.

## Methodology notes (keep)

- guard-fix-run predates `session_id`; its 100 transcripts were recovered by mtime window
  (2026-09-21 16:48–21:09, exactly 100 files) and paired native/prism in order. Validated:
  49/50 native-vs-prism token direction matches. Summing transcript `usage` fields gives
  ~1.7x the harness's recorded totals (structure is right, absolute numbers are not — use
  harness totals for cost, transcripts for shares).
- residency-ab and guard-hook-ab onward have `session_id`; find transcripts with
  `find ~/.claude/projects -iname "<session_id>.jsonl"`.
- `turns` in results.json does not correlate with work; count assistant messages instead.
- Gold patch before any causal story. Single-run findings are hypotheses.
- Analysis scripts for everything above: `harness/analysis/token-survey/`.

## Artifacts

`harness/results/guard-fix-run/` (50-task set), `guard-hook-ab/` (hook A/B),
`residency-ab/` (resident vs deferred), `harness/runners/run_overnight.py`
(`--native-arm/--prism-arm/--manifest/--out-dir/--model`), `harness/runners/ab_endtoend_arms.py`
(`prism_init`, `prism_init_deferred`, `prism_init_no_guard`), `harness/hooks/` (harness copy of
the read-guard scripts; the shipped copy is `prism/internal/cli/assets/`).
