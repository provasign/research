# Reframed thesis — code graph for agentic coding (2026-06-23)

## What we set out to prove (and could not)
"A resolved code graph makes an LLM coding agent's change-impact answers more
*complete* and better *calibrated* than text search." **Not supported by our
data.** Across 14 tasks / 3 models:
- **Recall is tied** between text (T) and graph (G) everywhere (within ~0.01–0.07).
  Capable agents reach the same completeness via grep+read because most Go call
  sites are name-greppable.
- **Calibration is ~tied in aggregate** (over-confidence T≈43 vs G≈42 across all
  runs). The graph lowers over-confidence on some tasks and *raises* it on others
  (`pr112043`, `querydata`) — it is task-dependent, not a graph property. (An
  earlier "16%→2%" headline was real but specific to the 3 pilot tasks; it does
  not generalize.)

## The reframed thesis (what the data actually supports)
**A resolved code graph is a token-efficiency mechanism for change-impact tasks at
scale: it reaches the *same* completeness as text search at ~10–40% lower token
cost, and the saving grows with the blast radius of the change. On trivial changes
the graph's query overhead makes it *more* expensive; its advantage appears only
once the change is large enough that grep+read would cost real tokens.**

Corollary (TESTED — and it FAILED the isolation): we hoped the graph would let a
cheap model reach strong-model quality (the capability-equalizer / cost-quality
story). Haiku-graph *does* ≈ Opus-text quality at 39–78% lower cost — BUT that is
**confounded by model price, not the graph**. Isolating the graph (same model,
Haiku-T vs Haiku-G) the graph lifts recall on **1 of 10 tasks** (126004, +0.29)
and ~0 on the rest. The cheap model was already ≈ as good as the strong one on
these tasks; the graph is not the lever. **C4 is not supported once isolated.**

## Falsifiable sub-claims
- **C1 (recall parity):** recall(G) ≈ recall(T) on change-impact tasks. *[supported]*
- **C2 (cost saving + scaling):** cost(G) < cost(T) at matched recall for tasks
  above a small-size threshold, and (1 − cost_G/cost_T) increases with #sites.
  *[supported, n small: +11–37% on ≥7-site tasks, −20–25% on 1–2-site tasks]*
- **C3 (calibration is NOT it):** over-confidence(G) ≈ over-confidence(T) in
  aggregate. *[supported — this is a negative result, stated honestly]*
- **C4 (budget-binding, under-tested):** the cost gap widens for weaker models /
  larger tasks. *[only endpoints so far]*

## What proving it requires
1. **Size-graded task set** (~8–12 tasks spanning ~5 → ~150 change-sites), oracle
   GT, so C2's *scaling* is a curve, not two points.
2. **≥2 models** (Haiku + a strong one) to test C4 (does the saving widen for the
   weak model?).
3. **Matched-recall cost**: report cost only where recall(T)≈recall(G) (else we're
   comparing different answers). Report tokens *and* latency (graph is slower —
   prism call overhead; an honest cost has both).
4. **Determinism**: cost from `total_cost_usd`, recall/precision from the oracle
   scorer (`rescore.py`) — no LLM in the measurement loop.

## Honest framing for the paper
This is a **modest efficiency result**, not a capability result: "graph ≈ same
answer, ~10–40% cheaper at scale, no completeness or calibration gain." Tokens are
cheap per task, so the story is *% efficiency that scales* + the cost/quality
corollary (C4) — compelling only if C4 holds (cheap model reaches strong-model
quality cheaper). Honest venue: a short/empirical paper or arXiv note, **not** the
original flagship "graph beats grep on completeness." If C4 fails too, the honest
conclusion is "for agentic Go coding, a code graph is a marginal token optimization."
