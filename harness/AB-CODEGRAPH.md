# Prism vs CodeGraph — completeness, efficiency, and the agent A/B

2026-07-12 · CodeGraph v1.4.1 · Prism v0.24 (Grove v0.20) · scripts:
[`codegraph_vs_prism.py`](codegraph_vs_prism.py) (engine),
[`efficiency_sweep.py`](efficiency_sweep.py) (speed/tokens),
[`ab_agentic_mcp.py`](ab_agentic_mcp.py) (agent A/B) ·
raw outputs: [`runs/codegraph-engine/`](runs/codegraph-engine/),
[`runs/ab-agentic/`](runs/ab-agentic/).

This is the first entry in an **ongoing program of benchmarking Prism
against other open-source code-context tools** — run for transparency, under
one standing rule set: same independent oracles, same scorer, same corpora,
each tool queried through its strongest surface, its own goals stated
fairly, every raw run published. The purpose is to test the paper's
mechanism (type vs name resolution) on implementations we did not build,
not to rank products.

[CodeGraph](https://github.com/colbymchenry/codegraph) is an open-source
tree-sitter code-graph tool (30+ languages, FTS5 search, one-call `explore`
context). Its headline claims are context-delivery *efficiency* (fewer tool
calls, faster, fewer tokens) — a different, legitimate goal from Prism's
completeness-first design, which is exactly what makes it informative to
measure. This benchmark measures it on the axis this
repository's paper argues governs safe refactors — **change-impact
completeness** — and then tests its own efficiency claims in an agent A/B.
Both engines are scored against the **same independent oracles**
(Spoon / ts-morph / Jedi / Go) with the **same scorer** the paper's agent
arms use (`score.py`). Recall = "list every site a signature change breaks."

## Fairness protocol (read first)

- CodeGraph is queried through **`explore`** — its headline tool, what agents
  actually call via MCP — NOT its weaker `impact`/`callers` CLI (which scored
  0.12 vs explore's 0.75 on the diagnostic task). Reporting the CLI would have
  been a hit piece.
- Every (symbol, file) `explore` surfaces in its blast-radius section PLUS
  every name it ties to the target through call/reference edges is credited;
  symbol-only matches count for recall. This maximises CodeGraph's score.
- Same oracle, same scorer, same target symbol, same corpus pin as Prism.
- The engine comparison has **no model in the loop** — it is the completeness
  ceiling each tool can deliver; an agent built on it cannot exceed it.

## 1 · Engine ceiling — 10 tasks, 4 languages, blast radius 8→310 (no LLM)

| task | lang | sites | Prism | CodeGraph (explore) |
|---|---|---:|---:|---:|
| jackson-jsonnode-get      | java |   8 | 1.00 | 0.75 |
| jackson-settable-set      | java |  22 | 1.00 | 0.27 |
| jackson-writetypeprefix   | java |  38 | 1.00 | 0.82 |
| jackson-serializewithtype | java |  58 | 1.00 | 0.66 |
| jackson-deserialize       | java | 104 | 1.00 | 0.00 |
| jackson-serialize         | java | 108 | 0.98 | 0.56 |
| guava-forwarding-delegate | java | 310 | 1.00 | 0.17 |
| gin-render-impact         | go   |  13 | 1.00 | 1.00 |
| typeorm-driver-escape     | ts   |  37 | 0.95 | 0.73 |
| django-quotename          | py   |  32 | 1.00 | 0.25 |
| **mean** | | | **0.99** | **0.52** |

Per language: java 0.997 / 0.46 (n=7) · go 1.00 / 1.00 (n=1) ·
ts 0.95 / 0.73 (n=1) · py 1.00 / 0.25 (n=1). Prism's mean reproduces the
paper's measured engine ceiling (a sanity check). The gap holds across four
languages and an 8→310-site range.

**The comparison is not rigged — CodeGraph ties where it should.**
gin-render-impact (1.00 vs 1.00) is the control: gin's `Render` interface
uses direct-name dispatch (every implementor has a `Render` method), which
tree-sitter name resolution handles perfectly. The gap appears only where
type resolution is load-bearing — exactly the paper's conditional thesis.

**Where CodeGraph collapses, and why.** deserialize 0.00 / guava 0.17:
overloaded interface methods and wide subtype closures — CodeGraph's name
resolution folds `deserialize(JsonParser,…)` into the *type*
`JsonDeserializer` and never isolates the specific overload's true callers.
A maximally-generous cross-check (any ground-truth symbol anywhere in its
output) caps it at 0.09. django 0.25 / settable-set 0.27: deep type-dispatch
families. The mechanism is the paper's thesis, observed on a named
third-party tool: tree-sitter **name** resolution ≠ compiler-grade **type**
resolution for change-impact completeness.

## 2 · Efficiency — speed and tokens, reported NEXT TO recall, never alone

A cheaper or faster *incomplete* answer is a faster broken build. Same
one-call use case, model-free (`efficiency_sweep.py`); P = Prism,
C = CodeGraph:

| task | recall P/C | wall_ms P/C | out_tokens P/C |
|---|---|---|---|
| jackson-jsonnode-get | 1.00 / 0.75 | 2181 / 664 | 1558 / 5769 |
| jackson-settable-set | 1.00 / 0.27 | 566 / 317 | 2175 / 4359 |
| jackson-serialize    | 0.98 / 0.56 | 561 / 354 | 18154 / 4359 |
| jackson-deserialize  | 1.00 / 0.00 | 558 / 353 | 21850 / 6251 |
| guava-forwarding     | 1.00 / 0.17 | 1336 / 501 | 26214 / 6069 |
| gin-render-impact    | 1.00 / 1.00 | 55 / 132 | 4336 / 3225 |
| **mean** | | **876 / 386** | **12381 / 5005** |

Read honestly:

- **Speed: CodeGraph is ~2× faster on average — by doing less.** Name lookup
  with capped output vs a full type-resolved traversal. On gin, where both
  are complete, Prism is faster (55 vs 132 ms). Prism is slower only on the
  large Java closures — where it is doing the complete work CodeGraph skips.
- **Tokens: partly an artifact of incompleteness.** CodeGraph's lower counts
  on the big tasks (guava 6069 vs 26214) come with recall 0.17 / 0.00 —
  fewer tokens *because* fewer sites found. Prism's larger counts are the
  complete answer (104/108/310 sites). Two caveats: (a) prism returns a
  compact site set, codegraph bundles verbatim source — raw token counts are
  not strictly like-for-like; (b) in the product (mason), Prism's payload
  isolation renders the site list to the *user*, so completeness costs the
  model ~tens of tokens, while explore output goes into the model's context.

## 3 · Agent A/B — the efficiency claims tested WITH an agent

CodeGraph's own headline ("58% fewer tool calls / 64% fewer tokens") is an
agent-total claim, so it needs an agent to test. Same agent (`claude -p`),
same task (jsonnode-get, GT = 8 sites), three arms differing **only** in the
tool available; oracle-scored (`ab_agentic_mcp.py`):

| model | arm | recall | turns | tokens(in) | cost | wall_s |
|---|---|---:|---:|---:|---:|---:|
| Haiku | prism      | 1.00 |  3 |   67k | $0.04 |  25 |
| Haiku | baseline   | 0.75 | 25 |  954k | $0.28 |  96 |
| Haiku | codegraph  | 0.00 | 31 | 1787k | $0.33 | 142 |
| Opus  | prism      | 1.00 |  3 |   60k | $0.14 |  17 |
| Opus  | baseline   | 0.62 | 19 |  376k | $0.90 | 200 |
| Opus  | codegraph  | 1.00 | 23 | 1428k | $2.38 | 523 |

- **Prism is tier-invariant**: recall 1.00, 3 turns, ~60–67k tokens on both
  tiers — the paper's tier-invariance result reproduced as a product-level
  agent A/B.
- **CodeGraph needs the frontier**: 0.00 on Haiku (a weak model cannot
  recover from incomplete context) → 1.00 on Opus, but at 23 turns / 1.43M
  tokens / $2.38 — 8× turns, 24× tokens, 17× cost, 30× wall-time vs Prism at
  equal correctness.
- **The efficiency claim inverts on this task class**: with CodeGraph the
  agent used *more* tokens and turns than the plain-grep baseline (1.43M vs
  376k; 23 vs 19). Incomplete, source-heavy context makes a
  completeness-seeking agent work harder, not less.
- Baseline grep never reaches completeness (0.75 / 0.62), even on Opus.

## 4 · Local tier — the $0 story

Local qwen3-coder:30b via mason (Prism-native), same task, oracle-scored on
what Prism renders to the user (mason's payload isolation puts the complete
set in front of the human, not the model's context):

    prism (local 30B, $0): recall 1.00 (all 8 incl. has/hasNonNull/_at), 23.8 s

## 5 · Tier table — cost of reaching a COMPLETE change-set

| tier | Prism | CodeGraph | baseline (grep) |
|---|---|---|---|
| local 30B ($0)  | **1.00** | (weak tier: see Haiku) | — |
| Haiku (cheap)   | **1.00** (3 turns, 67k tok, $0.04) | 0.00 (31 turns, 1.79M, $0.33) | 0.75 |
| Opus (frontier) | **1.00** (3 turns, 60k tok, $0.14) | 1.00 (23 turns, 1.43M, $2.38) | 0.62 |

The correctness-first verdict: at equal completeness, Prism is ~17× cheaper
and the only arm that stays complete as the model gets cheaper — down to $0.

Note on the missing local CodeGraph arm: no neutral local agent exists to
carry it (`claude -p` is Claude-only; mason is Prism-native; OpenCode and
Continue.dev scored 0–1/9 driving *any* tool from a local model — see
[`AB-LOCAL-CLIS.md`](AB-LOCAL-CLIS.md)). Haiku is the weak-tier proxy:
CodeGraph 0.00.

## Honest scope & caveats

- CodeGraph does **not** claim compiler-grade completeness; its claims are
  context-delivery efficiency, a different and legitimate job, and `explore`
  is a genuinely good one-call context tool (30+ languages, zero setup,
  local). This benchmark measures the one axis that governs safe refactors.
- Where CodeGraph is ahead of Prism today: language breadth beyond Prism's
  supported set, and framework-aware routing hints (dispatch wired through
  frameworks/DI/reflection, where Prism's static type-resolved edges
  deliberately show nothing rather than a guess).
- **Go coverage is n=1 (gin).** The grafana Go tasks target interface methods
  declared in an external SDK (grafana-plugin-sdk-go); scoring them fairly
  requires SDK-inclusive indexing for both engines — deferred.
- Small greppable changes would tie (see the paper). This set is deliberately
  the large/hard regime where completeness is load-bearing.
- Agent A/B is n=1 task per tier — a product-level demonstration that the
  engine gap survives an agent, not a study-grade grid.

## Reproduce

1. **Install both tools.**
   - Prism: `curl -fsSL https://raw.githubusercontent.com/provasign/prism/main/install.sh | bash`
   - CodeGraph v1.4.1: install from https://github.com/colbymchenry/codegraph
     (its installer symlinks `codegraph` into `~/.local/bin`).
2. **Clone the corpora at the pins** in each `tasks/<id>.json` (see the main
   [README](../README.md) corpus table) and repoint the tasks' `workdir`.
3. **Engine comparison** (no LLM, no API keys):

       cd harness
       python3 codegraph_vs_prism.py tasks/jackson-*.json tasks/guava-forwarding-delegate.json \
           tasks/gin-render-impact.json tasks/typeorm-driver-escape.json tasks/django-quotename.json
       # -> runs/codegraph-engine/codegraph-vs-prism.json

4. **Efficiency sweep** (no LLM; expects corpora under `~/gvg-corpus/` —
   edit `CASES` in the script to repoint):

       python3 efficiency_sweep.py

5. **Agent A/B** (needs an authenticated `claude` CLI; ~$4 total):

       python3 ab_agentic_mcp.py --model haiku tasks/jackson-jsonnode-get.json
       python3 ab_agentic_mcp.py --model opus  tasks/jackson-jsonnode-get.json
       # -> runs/ab-agentic/

Scoring is deterministic; the tables above are reproducible from
`runs/codegraph-engine/` and `runs/ab-agentic/` without any LLM.
