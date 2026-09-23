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
- **Shipped tonight:** prism v0.81.0 (`prism init --read-guard` / `--no-read-guard`),
  prism v0.81.1 + grove v0.58.3 (`prism doctor` reports Grove's per-language capability
  manifest under `languages`), a test-only fix for a pipe deadlock in `captureStdout`/
  `capture` that hung windows-latest. Tap refreshed to v0.81.1.
- **Rejected after measurement (don't reopen without new evidence):** byte cap on
  `search`; delta delivery for extending `read` ranges; per-language budget tiers.

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

1. **Collapse locator→body: prism decides the altitude.** When the located neighborhood is
   small, deliver the enclosing symbol the agent is about to edit instead of ±50 lines around
   the hit. Read would put those bytes in context anyway; the saving is the turn.
   Estimate: ~33 turns ≈ 1.7M tokens ≈ 4%, resolve-neutral by construction. A/B first.
2. **Own the verification turn.** `verify` runs the selected tests for changed symbols
   (grove test-selection, measured tier) and returns completeness + green/red + the failing
   assertion. Collapses edit → bash test → read output → fix. Estimate: one avoided suite turn
   ≈ 2.5M ≈ 6%; the real upside is resolve rate (agents fail by misreading test output).
   Design work + A/B. Not the rejected Prism 2.0 edit-moment hook — no hook, an op.
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
