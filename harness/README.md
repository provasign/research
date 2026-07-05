# Evaluation harness

Runs an LLM agent under enforced tool **arms** over **Mode-A** change-impact
tasks ("list every site that must change; don't write the patch") and scores
the answers against independent, type-resolved ground truth — never grove
against grove. See the [repo README](../README.md) for the study overview and
the full reproduction pipeline; this file is the operational reference.

## Files

| File | Role |
|---|---|
| `schema.py` | `Task`, `Site`, `Scorecard` dataclasses; task/run JSON I/O |
| `arms.py` | Arm definitions: allowlists + per-arm guidance (T / G / G\* / V) |
| `run.py` | Runner for the commercial tiers (`claude` CLI, headless, `--output-format stream-json`) |
| `run_codex.py` | Same protocol through the Codex CLI (GPT models) |
| `run_local_gstar.py` | G\* arm on a local model via Ollama, backed by the real Grove engine |
| `score.py` | Mode-A scorer: recall/precision/F1, calibration, weak-match audit |
| `rescore_java.py` | **Mandatory for Java**: normalizes `file:line` answers to enclosing methods before aggregation |
| `rescore.py` / `reparse_all.py` | Re-score / re-parse existing runs after scorer changes |
| `engine_ceiling.py` | Scores the raw `change-impact` engine output against the oracle — no LLM |
| `agg_jackson.py` | Aggregates recall + cost per task × model × arm (auto-discovers model dirs) |
| `mode_b_analysis.py` | Derived compile-failure metric (paper §5.5) |
| `extract_task.py` | Derives a task from a merged PR (Go tasks, Experiment 1) |
| `java-oracle/` | Spoon oracle — builds Java GT (own [README](java-oracle/README.md)) |
| `ts-oracle/` | ts-morph oracle — TypeScript GT ([README](ts-oracle/README.md)) |
| `py-oracle/` | Jedi oracle — Python GT ([README](py-oracle/README.md)) |
| `tasks/*.json` | Task definitions **with GT embedded** — self-contained for scoring |
| `runs/` | All scored runs + transcripts (released; layout in repo README) |
| `tests/` | Scorer + codex-runner unit tests (`python3 tests/test_score.py`) |

## Arms (`arms.py`)

Enforced via `claude --allowedTools` + `--strict-mcp-config` (the filesystem
`.mcp.json` is ignored): T genuinely cannot reach the graph, and G\* genuinely
cannot reach text search. Each run records its `tool_trace`; runs that violate
the arm boundary (a G run that never touched the graph, a G\* run that never
called `change-impact`) are flagged `violation` and excluded.

- **T** — `rg`/`grep`/`find`/`read` only.
- **G** — `prism` primitives (lookup, references, edges) + `rg` for anchors.
- **Gstar** — `prism change-impact` + `prism search` only. **No `rg`.** The
  Sonnet relay-failure result (paper, Guava/Django) is why: with a text-search
  escape hatch present, one tier re-derived the engine's answer and degraded
  precision; removing the tool restored tier-invariance. A steering rule alone
  did not.
- **V** — text-first, graph verification before asserting completeness
  (Experiment 1 only).

`PRISM_BIN` selects the prism binary (default `~/bin/prism`).

## Scoring (`score.py`)

Against the task's ground truth, per run:

- **recall / precision / F1** over change-sites. Matching requires
  symbol + file agreement; a symbol-only match is credited but flagged `weak`,
  and the aggregator prints a **weak-match audit** when a run's credited sites
  are predominantly weak (those recalls are unreliable — the Java fix is
  `rescore_java.py`).
- **over-confidence** — `complete == true` while recall < 1.0.
- **cost** — wall-clock, turns, tokens, $ from the CLI's JSON envelope.

Test files are neutral: sites under test paths are neither GT nor false
positives.

### Java pitfall (do not skip)

Graph arms answer `File.java:114` (authoritative file:line from prism); a
name-based scorer scores that 0 and silently under-credits the graph arm —
we measured a correct 148-site answer scored 0.0. `rescore_java.py` maps line
numbers to their innermost enclosing method via a Spoon line-index
(`java-oracle/*-lineindex.json`) and re-writes the scorecards. **Always run it
after any Java re-parse or re-score** — `reparse_all.py` clobbers its output.

## Engine ceiling (`engine_ceiling.py`)

```sh
python3 engine_ceiling.py tasks/<id>.json
```

Runs `prism change-impact` on the task target and scores the raw output — no
LLM in the loop. This is the completeness ceiling for the G\* arm; G\* agent
runs can only be interpreted against it (a G\* agent cannot beat the engine,
and every tier in the study lands exactly on it). Run it first, and re-run it
after any engine upgrade.

Two gotchas when regenerating indexes:

- After **any** engine change that affects edge building: `rm -rf .grove` in
  the corpus and reindex from scratch — delta indexing keeps stale edges.
- The ceiling is per-language and per-engine-version; the paper reports the
  ceiling next to every G\* cell.

## Runner notes

- `run.py --task tasks/<id>.json --arms T Gstar --trials 3 --model haiku`
  (models: `haiku` / `sonnet` / `opus`; `--workdir` overrides the task's
  baked-in corpus path).
- Graph arms get the corpus pre-indexed so index time isn't charged to the
  answer; text arms are unaffected.
- Transient API failures are retried and recorded as `status:error`, never
  scored 0. Timeouts SIGKILL the process group.
- `run_codex.py` mirrors the protocol for GPT models (usage/cost parsing,
  usage-cap handling); its runs land in the same `runs/` layout and are
  auto-discovered by the aggregator.
