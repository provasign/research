# Thesis — code graph for agentic coding (tool-altitude extension, 2026-07-04)

## The arc (what we believed, in order)
1. "Graph improves completeness + calibration on change-impact." — *Go: not
   supported.* Recall tied, calibration tied. (Honest negative, 2026-06-23.)
2. "Then graph is just a token optimization." — *Too weak.* It missed the
   boundary: the Go tasks were almost all small (1–22 sites) and name-greppable.
3. "Graph's value is **bounded to large-blast-radius change-impact**: there it
   improves recall AND consistency at near-equal cost, robustly across model
   tiers." — *Supported (2026-06-27), but incomplete: with primitives the weak
   tier plateaued at 0.833 while the frontier hit 1.000 with the same tools —
   the graph had the answer, the weak model couldn't extract it.*
4. **Current:** "The graph's value is gated twice: **blast radius** decides
   whether it exists; **tool altitude** decides who can collect it. Exposed as
   a single deterministic `change_impact` op, completeness becomes
   tier-invariant (0.997 every tier) and the cheapest model strictly dominates
   frontier text at 1/20th the cost." — *Supported (2026-07-04, Exp 2 on the
   repaired engine).*

## The thesis (what the data supports)
**A resolved code graph is a completeness-and-reliability mechanism for
large-blast-radius change-impact tasks — and its payoff reaches whichever
models the tool's interface altitude permits. Once a signature change touches
~100 sites, text search becomes an unreliable manual graph traversal; so is
driving graph PRIMITIVES (the orchestration burden is itself a frontier skill —
Haiku G plateaus at 0.833). Moving the traversal into the engine
(`change_impact` = declaration + subtype-closure family + resolved callers in
one deterministic call) makes completeness a property of the tool: recall 0.997
tier-invariant, engine-only ceiling 0.993/0.948 vs the independent oracle,
Haiku+op ($0.11/task) strictly better than Opus+text ($2.14/task). Below the
size threshold graph ≈ text at every altitude.**

## Falsifiable sub-claims & verdicts
- **C1 (small-task parity):** recall(G) ≈ recall(T) on ≤~22-site change-impact
  tasks. *[supported — Go 14 tasks; Java jsonnode-get/settable-set tie within
  0.01, despite 18–64× grep ambiguity]*
- **C2 (large-task recall win):** recall(G) > recall(T) on ~100-site tasks, and Δ
  grows with #sites. *[supported — Java deserialize +0.17, serialize +0.24
  (Haiku); serialize +0.13 (Sonnet). Mid-size 38/58 in progress to fill the
  curve]*
- **C3 (capability-conditioned, NOT uniform):** the large-task recall win shrinks
  as the model strengthens and, at the frontier, vanishes on tasks the model can
  fully enumerate but persists on harder ones. *[supported, full 3 tiers —
  serialize Δrecall: +0.24 (Haiku) → +0.13 (Sonnet) → +0.00 (Opus, both T=G=1.0).
  deserialize (harder): +0.17 → +0.17 → +0.04 (Opus G 0.962 vs T 0.923, T dipped
  to 0.71). At the frontier the value becomes reliability + cost, not raw recall.
  Reframes the graph as a CAPABILITY EQUALIZER — the Go 'equalizer' hypothesis
  that failed there (price confound) holds in the large-Java regime]*
- **C4 (consistency / reliability):** Var(recall_G) < Var(recall_T) on large
  tasks (graph removes catastrophic misses). *[supported — Sonnet serialize: G
  0.996±~0 vs T swinging to 0.73. The calibration benefit Go couldn't show]*
- **C5 (cost):** at matched/higher recall, cost(G) is regime-dependent — large
  tasks G/T≈1.07–1.16 ("better answer, ~same price"); mid-size G/T≈0.63–0.77
  (graph 25–37% CHEAPER at tied recall — the Go efficiency result); small tasks
  G/T≈1.24–1.28 (prism overhead tax). *[supported, full Sonnet curve]*
- **C6 (discriminator = blast radius, not ambiguity):** grep-ambiguity does not
  predict the graph's advantage; #change-sites does — more precisely, the count of
  sites reachable only via CALLER edges (callers not named after the target).
  *[supported — the most ambiguous tasks were the smallest; the lone small-task
  win (jsonnode-get) was driven by indirect callers has/hasNonNull/_at that don't
  contain "get", exactly the caller-edge mechanism]*
- **C7 (calibration parity on small tasks):** over-confidence(G) ≈
  over-confidence(T) on small tasks. *[supported — settable-set 5/5 both arms]*
- **C8 (tool altitude — NEW):** at task altitude (one deterministic
  `change_impact` op) completeness is tier-invariant and ≈ the engine ceiling;
  the weak-tier gap that primitives leave (G 0.833 vs 1.000) closes entirely.
  *[supported — Exp 2: G* mean recall 0.997 at Haiku, Sonnet AND Opus with
  per-task values identical across tiers; the one shared miss (serialize 0.982)
  is an engine residual (chained receivers), not a model failure. Haiku G*
  $0.11/task, 2.8 turns vs Opus G $3.06, 21 turns]*
- **C9 (testability — NEW):** a deterministic oracle-scored op exposes engine
  defects that LLM orchestration masks. *[supported — the op's initial recall
  0.05 traced to 5 latent Java resolution bugs (multi-line signatures, generic
  bounds, wildcard imports, same-file shadowing, nested generics), all fixed
  with regression tests → 0.99; Exp 1's G arm had absorbed them as plausible
  mid-range recall]*

## What remains to lock it (see paper §7)
1. **Finish the size curve:** mid-size Java (38/58) + Sonnet `deserialize` full +
   Opus tier (in progress). Confirms C2's curve and C3 at the frontier.
2. **Replicate the large-task regime** on a second framework (Spring/Guava) and
   in a large Go codebase with wide interfaces — to prove the lever is size, not
   "Java."
3. **Mode B (compile / fail-to-pass)** — does the reliability gain (C4) convert to
   task success when a missed site breaks the build?
4. **Determinism:** recall/precision from the oracle scorers (`rescore.py` /
   `rescore_java.py`, line→method normalized); cost from `total_cost_usd`. No LLM
   in the measurement loop.

## Honest framing
This is a **bounded positive**, not a blanket "graphs win." Most everyday edits
are small and the graph is a wash there; its distinctive, defensible value is
making large refactors *reliably complete*. Venue: an empirical SE paper whose
contribution is the boundary + the size-conditioned evaluation methodology, not
"graph beats grep."
