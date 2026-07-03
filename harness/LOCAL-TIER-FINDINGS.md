# Local-tier findings: tool *altitude* gates who can use the graph

An investigation arc (2026-07) that started as "add a local open-weights tier" and
turned into a research + product finding about **how** a code graph must be exposed
for a weak model to benefit.

## The arc
1. **qwen2.5-coder:14b — too weak to adapt.** On the raw-CLI agent loop
   (`run_local.py`) it rigidly greps a literal `JsonNode.get(...)` (which never
   appears — Java calls are `someNode.get(0)`), ignores "no matches" feedback, and
   gives up or loops. recall ~0 on both arms. (Also fixed a real harness bug here:
   `rg` with no path + non-tty stdin blocks -> 60s timeout; every search was
   returning `[timeout]`, starving the model. `stdin=/dev/null` + auto-append path.)
2. **qwen3-coder:30b — greps well, can't drive the graph.** Text arm 0.62
   (competitive with cloud text; adaptive `rg`, filters noise, finds the override
   family). But the **graph arm scored 0.0**: told to use prism, it abandons the
   grep it's good at and can't recall the CLI syntax (`prism references JsonNode.get`
   ✗ vs the working `prism references get`), loops, submits empty. *Being told to
   use the graph made it worse.*
3. **MCP-style structured tools don't fix it** (`run_local_mcp.py`). Presenting
   prism as typed function-tools regressed *both* arms to 0.0: qwen3 emits
   structured `tool_calls` unreliably via Ollama, and even when it calls tools it
   explores many turns without **converging** to submit. The wall is multi-turn
   traversal **orchestration**, not surface syntax.
4. **High-altitude `change_impact()` fixes it** (`change_impact.py`,
   `run_local_hitool.py`). Collapse the whole traversal into ONE call: given a
   method, return declaration + override/impl family + resolved callers. The same
   30B then reaches **recall 1.0 on all 6 tasks, each in a single call** — including
   the indirect callers (`has`/`hasNonNull`/`_at`) that grep and primitives miss.

## Two walls, two fixes
- **Orchestration wall** (weak models can't chain a multi-turn traversal) -> the
  high-altitude tool: one call returns the complete set.
- **Invocation wall** (weak models emit tool_calls unreliably) -> an impact-routing
  scaffold that forces the tool on the first turn (`tool_choice:"required"`). Real
  agent frameworks route intents to tools this way.

## Result (qwen3-coder:30b, n=1/cell)
| task (sites) | primitives (CLI/MCP) | change_impact (1 call) |
|---|---|---|
| jsonnode-get (8)   | 0.0 | 1.0 |
| settable-set (22)  | 0.0 | 1.0 |
| writeTypePrefix (38) | — | 1.0 |
| serializeWithType (58) | — | 1.0 |
| deserialize (104)  | 0.0 | 1.0 (prec 0.97) |
| serialize (108)    | 0.0 | 1.0 |

## VALIDITY — do not misread the 1.0
`change_impact` here is **Spoon-powered — the same engine that produces the study's
ground truth** — so scoring its output against that ground truth is tautological
(recall -> 1.0 by construction). What this legitimately shows:
- **The interaction works:** a weak model *consumes a high-altitude tool and relays
  a complete set faithfully in one call* (precision 0.97–1.0 -> it doesn't mangle
  the output). Contrast: the same model on graph primitives scores 0.0.
- It is **NOT** a graph-vs-text measurement. For a scored product claim, this
  resolution must live inside Grove/Prism (a real capability) and be scored against
  an INDEPENDENT oracle. The prototype stands in for that not-yet-built capability.

## Implication (for the paper and for Grove/Prism)
The graph's benefit is gated as much by **tool altitude** as by the graph's
existence. Primitives (references/lookup/query the model must orchestrate) are a
*strong-model luxury*. The win the paper documents is largest for weak/cheap models
on large changes — but they can only realize it if the graph is exposed as a
high-altitude operation (`change_impact`), not as primitives. Product direction:
ship type-resolved change-impact as a first-class Grove/Prism agent tool.

## Repro
```bash
cd harness && source java-oracle/env.sh
python3 change_impact.py --repo ~/gvg-corpus/jackson-databind "JsonNode.get(int)"   # the tool
python3 run_local_hitool.py --task tasks/jackson-serialize.json --model qwen3-coder:30b \
    --workdir ~/gvg-corpus/jackson-databind                                          # the demo
```
