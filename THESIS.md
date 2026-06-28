# Thesis — code graph for agentic coding (bounded-positive reframe, 2026-06-27)

## The arc (what we believed, in order)
1. "Graph improves completeness + calibration on change-impact." — *Go: not
   supported.* Recall tied, calibration tied. (Honest negative, 2026-06-23.)
2. "Then graph is just a token optimization." — *Too weak.* It missed the
   boundary: the Go tasks were almost all small (1–22 sites) and name-greppable.
3. **Current:** "Graph's value is **bounded to large-blast-radius change-impact**:
   there it improves recall AND consistency at near-equal cost, robustly across
   model tiers. On small/greppable tasks it ties. The discriminator is
   #change-sites, not name ambiguity or language." — *Supported by Go (small,
   tie) + Java jackson-databind (size curve 8→108; win at scale).*

## The thesis (what the data supports)
**A resolved code graph is a completeness-and-reliability mechanism for
large-blast-radius change-impact tasks. Once a signature change touches ~100
sites, text search (grep+read) becomes an unreliable manual graph traversal — good
on average but stochastically incomplete — while the graph enumerates the
override family and resolved callers in one authoritative pass: higher mean
recall AND collapsed variance, at near-equal token/USD cost. Below that size
threshold (most Go tasks, everyday edits) graph ≈ text. The lever is blast radius,
not greppability — name-ambiguous targets did NOT favor the graph; small ones
tied regardless of ambiguity.**

## Falsifiable sub-claims & verdicts
- **C1 (small-task parity):** recall(G) ≈ recall(T) on ≤~22-site change-impact
  tasks. *[supported — Go 14 tasks; Java jsonnode-get/settable-set tie within
  0.01, despite 18–64× grep ambiguity]*
- **C2 (large-task recall win):** recall(G) > recall(T) on ~100-site tasks, and Δ
  grows with #sites. *[supported — Java deserialize +0.17, serialize +0.24
  (Haiku); serialize +0.13 (Sonnet). Mid-size 38/58 in progress to fill the
  curve]*
- **C3 (cross-tier robustness):** the large-task win persists for a stronger
  model. *[supported so far — Sonnet serialize T 0.865 vs G 0.996; deserialize
  partial agrees. Opus pending]*
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
