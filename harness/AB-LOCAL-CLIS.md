# A/B: can a LOCAL model actually do agentic coding? (mason vs OpenCode vs Continue, same weights)

2026-07-12 · harness `ab_local_clis.py` · runs archived in `runs/ab-local-clis/`
(per-cell JSONs, run log, and the exact provider configs used for each CLI).

## Question

The paper says completeness on graph-shaped work becomes tier-invariant when
the graph is exposed at task altitude — and the local-tier arc showed WHY weak
models fail with generic tooling (the orchestration wall and the invocation
wall). This A/B asks the product-level version of that question: **given the
same open-weights model, can today's local-capable coding CLIs actually
complete agentic coding tasks end-to-end?**

## Design

Same local model (`ollama qwen3-coder:30b`), same natural-language prompts,
fresh gin scratch tree per cell, **oracles executed by the harness after the
agent exits** — agent claims are never trusted. 3 trials per cell. Products
as-shipped in their stock non-interactive modes:

| arm | product | invocation |
|---|---|---|
| mason-30b | mason v0.23.0 (prism graph harness baked in) | `mason --yes --model ollama:qwen3-coder:30b` |
| opencode-30b | OpenCode 1.17.18, ollama via its documented openai-compatible provider config | `opencode run -m ollama/qwen3-coder:30b` |
| continue-30b | Continue CLI 1.5.47, ollama provider config | `cn --auto -p` |

Tasks and oracles are identical to `AB-MASON-CLAUDE.md` (2026-07-11): rename
(interface renamed + `go build ./...` green), feature (method declared +
tested + build + targeted tests green), comprehend (names the closed-set
implementor). Ollama 0.31.1, one shared M-series laptop, sequential runs.

## Result (oracle passes, 3 trials per cell)

| task | mason + 30B | OpenCode + 30B | Continue + 30B |
|---|---|---|---|
| rename | 2/3 † | 0/3 | 0/3 |
| feature | 3/3 | 0/3 | 0/3 |
| comprehend | 3/3 | 0/3 | 1/3 |
| **total** | **8/9** | **0/9** | **1/9** |

† one rename pass hit the 15-minute kill with the tree already renamed and
building (the agent had finished the work but had not exited); counted as a
pass on the oracle, disclosed as a DNF on wall-clock. See "mason's own
finding" below — the rename cells also ran far slower than the 2026-07-11
v0.3.1 result and one trial failed outright.

## Failure modes (from the transcripts — this is the mechanism, not noise)

- **OpenCode 0/9 — the invocation wall, verbatim.** In every failing run the
  model either hallucinated a nonexistent `explore` tool, or emitted its
  tool calls in Qwen's XML dialect (`<function=…> <parameter=…>`) as plain
  text, which OpenCode does not parse. Nothing executed; the model then asked
  the *user* what to do ("Could you please provide more details…") and the
  run ended in seconds. This is precisely the failure the paper's local-tier
  arc documents — and why mason ships a Qwen-XML tool-call parser and a
  refusal guard that bounces "ask the user" answers back at the model.
- **Continue 1/9 — off-task drift.** Headless runs frequently answered about
  unrelated parts of the codebase (WebSocket hijacking, test explanations) or
  stopped right after announcing a plan, without executing tools. The one
  pass was comprehend (a read-only question).
- **mason 8/9** with the same weights: the invocation wall is closed by the
  forced graph route + XML-dialect parsing, the orchestration wall by
  task-altitude ops (`rename_plan`/`apply_rename_plan`), and give-up answers
  by the refusal/honesty guards.

## mason's own finding (disclosed, not folded in)

The rename cells regressed vs the 2026-07-11 run of mason v0.3.1 (49.3s clean
pass): v0.23.0 took 583s/900s(DNF)/405s(FAIL — the model concluded "no code
modifications were necessary"). The oracle A/B surfaced a real product
regression introduced somewhere in v0.4→v0.23 — fourth instance of the
pattern this repo keeps finding: **agents absorb harness defects invisibly;
oracle-scored runs surface them as failures you can root-cause.** The
diagnosis and fix are tracked in the mason repo; this doc reports the
pre-fix numbers and will link the post-fix rerun rather than replacing them.

## Caveats (read before quoting)

- n=3 per cell, one machine, wall times on a shared laptop. Directional.
- Small-scope gin tasks. The paper predicts parity on small greppable tasks
  for *context delivery*; what this A/B measures is end-to-end **agentic
  completion** — tool invocation, traversal, apply, verify — where the
  harness, not the context, is the bottleneck for local models.
- Products-as-shipped with their documented local-model configs (archived in
  `runs/ab-local-clis/`). If either product has a better-supported local
  setup, we will happily rerun — the harness is idempotent and takes ~1h.
- OpenCode and Continue are excellent products with frontier/API models; this
  measures ONLY the stock local-model path with one 30B. It is a statement
  about harness design for weak models, not product quality overall.

## Repro

```sh
cd harness
python3 ab_local_clis.py --trials 3       # full grid (skips completed cells)
python3 ab_local_clis.py rename:mason-30b # one cell
```
