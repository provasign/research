# ROADMAP — two paths off one build

Companion to `HANDOFF.md`. The research result (paired T/G/V study, Spoon oracle,
157 runs) is **done and committed** — that stays. What follows is what comes
*after*, and it splits cleanly into **two paths that share one prerequisite.**

---

## 0. The shared prerequisite (the fork point)

Everything below depends on **build #1 from `HANDOFF.md` §7**:

> **A type-resolved `change_impact` living *inside* Grove/Prism — independent of
> the Spoon eval oracle.**

Why it gates both paths:
- Today's PoC `change_impact.py` is **Spoon-powered** — the same engine that
  produces our ground truth. Its recall-1.0 is **tautological**. It cannot appear
  in a paper *or* a product as a real number.
- Prism's `references` is name-based (over-matches); grove `impact` is too coarse.
  Neither resolves types. The build is: **genuine type resolution in the graph**,
  exposed as one high-altitude call:
  `change_impact(Class.method(params)) → declaration + override/impl family + resolved callers`.

Until this exists there is no defensible "graph-native" number and no shippable
tool. **Build it first. Both paths start the day it lands.**

---

## Path A — Research paper, redone on the real engine

The current paper measures graph value via **Prism/Grove primitives** the model
orchestrates over many turns. The redo measures it via the **high-altitude
`change_impact`** tool, and adds the tier the current paper only gestures at: the
**local open-weights model**.

### What changes
1. **New arm / new tool.** Replace (or add alongside) the primitive-orchestration
   graph arm **G** with a **high-altitude arm G\*** driven by graph-native
   `change_impact`. The interesting scientific contrast becomes
   **T vs G (primitives) vs G\* (task-shaped tool)** — i.e. *tool altitude* as an
   explicit independent variable, not a footnote.
2. **New tier.** Add **local `qwen3-coder:30b`** as a first-class model row, not a
   PoC aside. This is what makes the "altitude is a capability equalizer" claim
   land: primitives = 0.0, `change_impact` = enabling.
3. **New runs, independent oracle.** Re-run the size curve (8/22/38/58/104/108
   sites) × {Haiku, Sonnet, Opus, **local-30B**} × {T, G, G\*}, scored by the
   **Spoon oracle** — which is now *independent* of the tool under test (the tool
   resolves types in the graph; the oracle resolves them in Spoon).
4. **Mode B (optional but strong).** Compile / fail-to-pass: does completeness
   convert to task success? Turns "recall" into "the build stays green."

### Revised thesis for the paper
Not just *"a resolved graph helps, gated by capability × blast-radius"* — but:
**"the graph's value is realized through tool *altitude*; a task-shaped operation
lifts a weak/free local model to frontier completeness where primitives leave it
at zero, and makes frontier models cheaper and deterministic."**

### Deliverables
- Redone tables (`paper.md`, `paper/paper.tex`): add G\* column + local-30B row.
- Update `THESIS.md` C1–C7; likely a new sub-claim on altitude as the mechanism.
- Keep the 3 arXiv TODOs (authors, artifact URLs, citation check) — fold into this
  pass rather than doing them twice.

### Path A is "done" when
The head-to-head **local + G\*** vs **commercial + T** is measured by the
independent oracle across the full size curve, and the altitude contrast
(G vs G\*) is a table, not a claim.

---

## Path B — The product (Grove/Prism as a coding-agent substrate)

Bigger than the paper: **more than the engine — the engine *plus its delivery*
into where people actually code** (VS Code, Continue.dev, Claude Code, Codex CLI).
The value proposition steps down the price ladder, and each rung is a distinct,
sellable claim.

### The three rungs (each a real product claim)

**Rung 1 — Premium models, cheaper & deterministic (no quality loss).**
Opus/Sonnet already reach ~1.0 recall on change-impact — but by *hand-simulating*
a traversal over 24–65 turns at real cost/latency/variance. Replace that with **one
deterministic `change_impact` call.**
- Claim: **same coding quality, a fraction of the tokens/latency, and
  deterministic** (no run-to-run variance on the traversal).
- Metric: $/task and turns/task at fixed recall. (We already have the "before":
  ~$5.64/run, 24–39 turns on deserialize for Opus.)

**Rung 2 — Haiku reaches premium quality on the tasks that matter.**
Cheap cloud model + `change_impact` closes the completeness gap that its
imperfect orchestration leaves open (large tasks 0.69 / 0.85 → ~1.0).
- Claim: **premium-tier change-impact completeness at Haiku prices — no
  degradation in coding quality** on the blast-radius tasks where cheap models
  otherwise silently miss sites.
- Metric: Haiku + G\* recall vs Opus + T recall, at the Haiku price point.

**Rung 3 — Free local model + new Grove/Prism = a genuinely free good-coding
option.** The dramatic one. Local `qwen3-coder:30b` on primitives = 0.0 (can't
orchestrate, can't reliably emit tool calls). On `change_impact` with an
impact-routing scaffold = complete change-sets.
- Claim: **a free, open-weights, on-device model + free Grove/Prism does
  change-impact-complete coding at $0/query** — competitive with commercial
  frontier models on this axis.
- Metric: the honest head-to-head from Path A, but framed as a product ("free
  option that doesn't miss sites"), plus Mode B (the build stays green).

### The delivery layer (this is the "more than prism/grove" part)
The engine is worthless to a developer until it's in the loop where they code.
Product work beyond the algorithm:
- **Editor / agent integration.** `change_impact` surfaced through:
  - **VS Code** — as an extension or via the existing MCP bridge.
  - **Continue.dev** — as a context provider / tool (open-source agent, natural
    fit for the free-local story).
  - **Claude Code / Codex CLI** — as an MCP tool (already the harness path;
    productize it).
  - **Local model runtime** — Ollama + the impact-routing scaffold that *forces*
    the high-altitude call (weak models won't choose it unprompted).
- **The "free stack" story, end to end:** Ollama (free model) + Grove/Prism (free
  engine) + Continue.dev / VS Code (free editor) → a $0 coding agent that doesn't
  miss change sites. That is the headline demo.
- **Packaging:** what's the install? One command that indexes a repo and registers
  `change_impact` with the user's editor/agent of choice.

### Open product questions to resolve early
- **Scaffold vs model choice:** how much of Rung 3 depends on the impact-routing
  scaffold vs the raw model? What breaks on a repo the scaffold wasn't tuned for?
- **Language coverage:** the engine is Java-first today (Spoon-shaped). Product
  needs Go (we have corpora) + at least one more. What's the type-resolution
  story per language inside Grove?
- **Beyond change-impact:** `change_impact` is the first high-altitude op. What's
  the next one (call-chain, file blast radius, all-implementors)? The product is
  the *class* of task-shaped tools, not one call.
- **Continuous / "continue dev":** keeping the graph fresh as the dev edits
  (incremental re-index, drift). Prism already has drift signals — wire them into
  the editor loop.

### Path B is "shippable" when
A developer can `install → open their repo in VS Code (or Continue.dev) → get
change-impact-complete edits from a free local model`, and we can show all three
rungs (premium cheaper, Haiku no-degrade, local free) as numbers on their own repo.

---

## How the two paths relate

```
                 build #1: graph-native change_impact
                 (type resolution in Grove/Prism,
                  independent of the Spoon oracle)
                          /                 \
                         /                   \
              PATH A: paper redo        PATH B: product
              - add G* altitude arm     - Rung 1 premium: cheaper+deterministic
              - add local-30B tier      - Rung 2 haiku: no-degrade at low cost
              - independent-oracle       - Rung 3 free local: $0 good coding
                head-to-head            - delivery: VS Code / Continue.dev /
              - Mode B (optional)         Claude Code / Ollama scaffold
```

- **Shared:** the engine, the size-curve tasks, the Spoon oracle (as *scorer* for
  A, as *validation* for B), the local-tier scaffold.
- **A produces the credibility** (peer-reviewable, independent-oracle numbers) that
  **B sells** (the same numbers, framed as product claims on a user's own repo).
- **Do the engine once.** Then A and B run in parallel — A is measurement +
  writing, B is integration + packaging.

---

## Suggested sequence

1. **Engine (build #1)** — graph-native `change_impact`. *Blocks both paths.*
2. **Path A runs** — re-grid on the real engine, independent oracle, local tier.
   Cheap to do right after the engine; produces the numbers B needs anyway.
3. **Path B rung 1 + delivery MVP** — wrap `change_impact` as an MCP tool in
   Claude Code / VS Code; show premium-cheaper on a real repo. (Fastest product
   proof; reuses the harness path.)
4. **Path A writing + arXiv polish** — tables, THESIS, the 3 TODOs.
5. **Path B rungs 2–3 + free-stack demo** — Haiku no-degrade, then the Ollama +
   Continue.dev + Grove $0 stack. The headline.
6. **External validity (paper §7.3) + Mode B** — 2nd framework / Go, compile-based
   success. Strengthens both A (external validity) and B (task success, not just
   recall).
