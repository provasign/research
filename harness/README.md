# Phase-0 harness — graph-vs-grep study

Runnable harness for the controlled study in
[`../grove-vs-grep-paper-design.md`](../grove-vs-grep-paper-design.md). It runs
the agent under each tool **arm** (T/G/V) over **Mode-A** tasks (answer the
context question; don't write the patch) and scores the answer against an
**independent**, PR-derived ground truth — never grove against grove (design
§5, §10).

**Status:** Phase 0 complete and smoke-tested end-to-end on gin (see below).
Phase 1 = point it at Grafana. The agent runner is the local `claude` CLI in
headless mode, so no API key is needed.

## Design → code

| Design (§) | File |
|---|---|
| Task = merged PR, pin at parent, change-sites = ground truth (§5) | `schema.py` (`Task`, `Site`), `extract_task.py` |
| Tool arms T / G / V, enforced not just prompted (§4, §10) | `arms.py` |
| Mode-A metrics: recall/precision/F1 + calibration (§6) | `score.py`, `schema.py` (`Scorecard`) |
| Paired run protocol, N trials, cost capture (§7) | `run.py` |
| Scorer correctness | `tests/test_score.py` |

## Quickstart

```sh
cd research/harness

# 0. scorer unit tests (no agent, no network)
python3 tests/test_score.py

# 1. derive a task from a merged PR (ground truth = changed prod functions)
python3 extract_task.py --repo /tmp/eval-corpus/gin --commit d75fcd4 \
    --id gin-4645 --type localization --pr gin#4645 \
    --prompt "<issue symptom text>" --out tasks/gin-4645.json

# 2. run arms over the task and score (writes runs/<id>/)
python3 run.py --task tasks/gin-4645.json --arms T G V --trials 1
```

`run.py` checks the repo out at the pin in a throwaway git **worktree**
(`/tmp/gvg-corpus/<id>`) — the shared eval corpus is never moved. Graph arms
pre-index that worktree with prism so index time isn't charged to the answer.

## The arms (`arms.py`)

- **T** — text only: `rg`/`grep`/`find`/`sed`/`read`. The baseline.
- **G** — graph-primary: the `prism` CLI for traversal; `rg` only to find an
  anchor. (`grep to FIND, prism to TRAVERSE`, per `prism/CLAUDE.md`.)
- **V** — graph-as-verifier: text-first, then confirm completeness with prism
  before asserting `complete: true` (design §4 V arm, H6).

Arms are enforced by `claude --allowedTools` + `--strict-mcp-config`, so the
filesystem `.mcp.json` is ignored and T genuinely cannot reach the graph.
`PRISM_BIN` selects the prism binary (default `~/bin/prism` = released v0.15.0;
set to `/tmp/prism-prim` to exercise the uncommitted `resolve`/`edges`
primitives — see the repo `HANDOFF.md`).

## Scoring (`score.py`)

Per run we record, against the PR ground truth:

- **recall / precision / F1** over change-sites (matched-universe discipline:
  symbol-name + file agreement; a symbol-only match counts but is flagged
  `weak`).
- **over-confidence** = `complete == true AND recall < 1.0` — the confident
  error the paper argues text search produces silently (RQ3, H3).
- **gap-surfacing** = did the answer flag any `unresolved` edge.
- **cost** = wall-clock, `num_turns` (round-trips), token usage, `$` — from the
  `claude` JSON envelope (design §6).

## Phase-0 smoke result (gin PR #4645, 1 trial)

A localization task: "Hijack/CloseNotify panic when the wrapper doesn't
implement the interface; fix gracefully like Flush." Ground truth
(auto-extracted, then human-confirmed): `response_writer.go:Hijack`,
`response_writer.go:CloseNotify`.

| arm | recall | precision | F1 | overconfident | turns |
|---|---|---|---|---|---|
| T | 1.0 | 1.0 | 1.0 | false | 5 |
| G | 1.0 | 1.0 | 1.0 | false | 3 |
| V | 1.0 | 1.0 | 1.0 | false | 4 |

All arms tie at perfect F1 — **exactly H1's prediction**: on localization the
graph is not better search. This validates the harness mechanics; it does *not*
test the thesis. The thesis (H2/H3) lives in **impact / dead-code** tasks on a
large repo with interface dispatch — that's Phase 1.

## Phase 1 — next step (Grafana)

1. **Pick ~10 Grafana issue→PR tasks** across the task-type taxonomy
   (localization, impact/refactor, dead-code, test-coverage, comprehension),
   weighted toward impact/dispatch where the graph should win. Use `gh` (authed)
   to find merged PRs with linked issues touching Go; record each PR's merge SHA.
2. **Clone Grafana once** at each PR's parent commit (or one base + per-task
   worktrees). `extract_task.py --repo <grafana> --commit <merge_sha> ...`
   builds the task; **hand-verify** the auto-extracted change-sites against the
   PR (the extractor is line→enclosing-func; confirm impact tasks include
   caller sites the PR touched).
3. **Independent oracle for impact tasks.** For "find every caller that must
   change", augment ground truth with the go-ssa-vta caller set from
   `grove/eval` (`grove-eval truth --repo <grafana> --commit <parent>`), so
   completeness is scored against the compiler, not grove (design §5).
   `grove-eval` is a nested module: `cd grove/eval && go build -o grove-eval
   ./cmd/grove-eval` first.
4. **Run** `run.py --arms T G V --trials 5`; report median + IQR (design §7).
5. **Ablation (H7):** repeat the G arm with `PRISM_BIN` pointing at a
   dispatch-fix-OFF prism build to show graph *quality* drives the outcome
   (design §8).

### Known gaps to close in Phase 1

- **Tool-trace logging.** We capture `num_turns` but not which tools fired.
  Switch `run.py` to `--output-format stream-json` to log the tool sequence and
  *prove* T never touched the graph and G traversed it (validity, design §10).
- **Grafana indexing cost** is non-trivial; pre-index once per pin and reuse.
- **Mode B** (apply the patch, run affected tests) is out of Phase-0 scope
  (design §5) — add on a subset in Phase 2.
