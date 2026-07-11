# A/B: Claude Code (Sonnet) vs mason (local qwen3-coder:30b)

2026-07-11 · harness: scratchpad `ab_mason_claude.py` · results archived in
`runs/ab-mason-claude/` · mason v0.3.0 → v0.3.1 (see "What the A/B found").

## Design

Two products, same natural-language prompts, fresh gin scratch tree per
(task, arm), **oracles executed by the harness after the agent exits** —
agent claims are never trusted.

- **claude-sonnet**: Claude Code CLI 2.1.201, `-p --model sonnet
  --strict-mcp-config --dangerously-skip-permissions` (no prism/MCP — pure
  baseline product), subscription-billed, cost from `total_cost_usd`.
- **mason-30b**: mason `--yes --model ollama:qwen3-coder:30b` (graph harness
  baked in), $0, tokens from the usage report.

Tasks and oracles:

| task | prompt shape | oracle (harness-run) |
|---|---|---|
| rename | rename `ResponseWriter.Status` → `StatusCode`, update everything, verify | interface+impl renamed AND `go build ./...` green |
| feature | add `IsSuccess() bool` to the interface, implement, unit-test | declared + referenced in tests + build + targeted `go test` green |
| comprehend | which types implement `ResponseWriter`? | names `responseWriter` @ `response_writer.go` (grove closed-set truth) |

## Results

| task | Claude Code + Sonnet | mason + local 30B |
|---|---|---|
| rename | PASS · 59.7s · $0.318 | pre-fix **FAIL** (see below) → post-fix **PASS · 49.3s · $0** |
| feature | PASS · 29.9s · $0.237 | PASS · 82.8s · $0 (84.6k/2.0k tok) |
| comprehend | PASS · 17.3s · $0.144 | PASS · 25.7s · $0 (33.4k/0.8k tok) |
| **total** | **3/3 · 107s · $0.70** | **3/3 · 158s · $0.00** |

Headline: a free local 30B behind mason's graph harness matches Claude Code
+ Sonnet on all three oracles at $0, ~1.5× wall time — and is *faster* than
Sonnet on the graph-shaped task (49.3s vs 59.7s), because the rename is one
engine call + one apply, not an agentic search-and-edit.

## What the A/B found (the pre-fix failure)

First run of rename/mason-30b failed its oracle: the model applied the
rename plan without the ambiguous bucket, `go build` broke on the 21
unapplied caller edits, and the model **hand-fixed callers one by one**
(grep → read → edit) until it exhausted its 30-turn budget (119.8s, 159k
tokens). Root cause was a mason information gap, not model capability: the
"21 AMBIGUOUS edits NOT applied" line rendered to the *user* only, while
the *model's* tool result said just "rename plan applied" — so the model
never knew that one `apply_rename_plan(includeAmbiguous=true)` call would
heal everything (the per-line drift check skips already-applied edits).
Fixed in mason v0.3.1: the tool result now carries applied/skipped/
ambiguous counts plus the recovery instruction. Post-fix rerun passed in
49.3s. The pre-fix result is preserved
(`rename.mason-30b.PREFIX-infogap.json`); the fix and rerun are disclosed
here rather than silently folded in.

Meta-lesson (third instance of the pattern): agents absorb harness/engine
defects invisibly — an oracle-scored A/B surfaces them as failures you can
root-cause. Same mechanism as the paper's "engine defects get absorbed by
LLM arms" finding and the Mode B compile oracle.

## Caveats

- n=1 per cell; wall times on a shared laptop with Ollama; directional,
  not publication-grade.
- The user asked for "Sonnet vs 30B"; a **mason+Sonnet** arm needs an
  ANTHROPIC_API_KEY (`mason login anthropic`) — not available on this
  machine, so the comparison is product-vs-product (Claude Code+Sonnet vs
  mason+30B), which is the Phase 3 framing anyway.
- gin tasks are small; the paper predicts ties on small greppable tasks —
  consistent with feature/comprehend. The rename is the graph-shaped cell
  and showed the differentiation (speed parity at $0 + the one-call apply).
