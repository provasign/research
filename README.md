# When Does a Code Graph Help a Coding Agent?

Companion repository for the paper:

> **When Does a Code Graph Help a Coding Agent? Blast Radius, Model Capability,
> and Tool Altitude in Change-Impact Tasks** — Tapabrata "Topo" Pal, 2026.
> LaTeX source: [`paper/paper.tex`](paper/paper.tex).

This repo contains everything needed to reproduce the study: the evaluation
harness, the task definitions with type-resolved ground truth, the independent
oracles for all four languages, the deterministic scorers, and the complete
scored run logs (every arm × tier × trial cited in the paper).

## The study in one paragraph

We compare three ways of giving an LLM coding agent context for change-impact
tasks ("list every site that must change if this method's signature changes"):
plain text search (**T**), code-graph *primitives* the agent orchestrates
(**G**), and the same graph exposed at *task altitude* — a single deterministic
`change_impact(method)` operation (**G\***). Across four languages (Go, Java,
TypeScript, Python), three commercial model tiers plus a local 30B model, and
tasks spanning 1–310 change-sites, the answer depends on two conditions: the
graph ties text on small greppable tasks; as primitives it helps most where models
are weakest but leaves much of the benefit unrealized (orchestration is itself
a frontier skill); at task altitude completeness becomes **tier-invariant** —
every tier, including the free local model, lands on the engine's ceiling.

## Repository map

| Path | Contents |
|---|---|
| `paper/paper.tex` | The paper (builds with `tectonic paper.tex`) |
| `harness/` | Arms runner, scorers, aggregators — see [`harness/README.md`](harness/README.md) |
| `harness/tasks/*.json` | Task definitions incl. oracle-derived ground truth (self-contained; oracles are only needed to *regenerate* GT) |
| `harness/runs/` | **All scored run logs** — `runs/<task>/<model>/<Arm>.t<n>.json` + full agent transcripts |
| `harness/java-oracle/` | Spoon type-resolution oracle (Java GT) |
| `harness/ts-oracle/` | ts-morph oracle (TypeScript GT) |
| `harness/py-oracle/` | Jedi oracle (Python GT) |
| `THESIS.md` | The claim arc — what we believed, in order, including the reversals |
| `HANDOFF.md`, `ROADMAP.md` | Working research notes, kept for transparency |
| `LOCAL-MODEL-SETUP.md` | Ollama setup for the local-30B tier |

## The arms

Arm enforcement is structural, not prompted: `claude --allowedTools` with a
recorded per-run `tool_trace`; violating runs are flagged and excluded.

- **T** — text only: `rg`/`grep`/`find`/`read`.
- **G** — graph primitives (`prism` symbol lookup, references, typed edges)
  plus `rg` for anchor discovery.
- **G\*** — one task-level call: `prism change-impact 'Type.method(Params)'`.
  No text-search tool in the allowlist — the paper's relay-discipline result
  (§ Guava) is *why*.
- **V** — text-primary with graph verification (Experiment 1 only).

## Run-log layout

```
harness/runs/<task-id>/<model>/<Arm>.t<trial>.json          scored result
harness/runs/<task-id>/<model>/<Arm>.t<trial>.transcript.txt agent transcript
```

Models: `haiku`, `sonnet`, `opus`, `qwen3-coder-30b-gstar` (local tier), plus
exploratory `gpt-5.5` runs (via `run_codex.py`) not cited in the paper. Scores
(recall/precision/F1, calibration, turns, tokens, $) are embedded in each JSON;
all Java numbers in the paper are **post `rescore_java.py` normalization**
(line→enclosing-method), which is mandatory before aggregation.

**Included but excluded from the paper** (kept for transparency):
`commons-collections-mapiterator-next` failed an outcome-blind audit (the
target overrides `java.util.Iterator.next`, making the refactor ill-posed) —
its numbers must not be cited. The early `commons-*` (commons-lang) tasks used
bare-name ground truth, later shown invalid; they were replaced by the Spoon
type-resolution oracle.

## Reproducing the study

### 1. Prerequisites

| Component | Version used | Source |
|---|---|---|
| Grove (graph engine, `change-impact` op) | v0.14.1 | https://github.com/provasign/grove/releases/tag/v0.14.1 |
| Prism (agent-facing CLI/MCP) | v0.16.1 | https://github.com/provasign/prism/releases/tag/v0.16.1 |
| astkit (parser layer; grove dependency) | v0.4.17 | https://github.com/provasign/astkit/releases/tag/v0.4.17 |
| `claude` CLI | any recent | agent runner for the commercial tiers |
| Python 3.11+ | — | harness/scorers (stdlib only) |
| JDK 17+ + Maven | JDK 26 | Java oracle only (`java-oracle/README.md`) |
| Node 18+ | — | TypeScript oracle only |
| `jedi` (pip) | — | Python oracle only |
| Ollama + `qwen3-coder:30b` | — | local tier only (`LOCAL-MODEL-SETUP.md`) |

### 2. Corpora

Clone each subject at the pinned commit (the authoritative pin for every task
is the `pin` field of its `harness/tasks/<id>.json`):

| Corpus | Upstream | Pin (main tasks) |
|---|---|---|
| jackson-databind | https://github.com/FasterXML/jackson-databind | `0b422144` (2.18.8) |
| Guava | https://github.com/google/guava | `f06690fa` |
| Grafana | https://github.com/grafana/grafana | `b6fdc12f` |
| gin | https://github.com/gin-gonic/gin | per-task |
| TypeORM | https://github.com/typeorm/typeorm | `3d55188c` |
| Django | https://github.com/django/django | `318a316a` |
| commons-collections | https://github.com/apache/commons-collections | `4db43277` |

Task JSONs carry absolute `workdir`/`repo` paths from the original machine —
repoint them at your clones (or pass `--workdir` to `run.py`).

### 3. Pipeline

```sh
cd harness

# scorer unit tests — no agent, no network
python3 tests/test_score.py

# engine ceiling: score the raw change-impact op against the oracle, no LLM.
# Run this FIRST — G* arms can only be interpreted against it.
python3 engine_ceiling.py tasks/jackson-serialize.json

# run arms (commercial tiers; claude CLI must be authenticated)
python3 run.py --task tasks/jackson-serialize.json \
    --arms T Gstar --trials 3 --model haiku

# local tier (Ollama)
python3 run_local_gstar.py --task tasks/django-quotename.json

# Java ONLY — mandatory before any aggregation:
# normalizes file:line answers to enclosing methods (a name-based scorer
# silently zeroes correct graph-arm answers; see paper §"A scoring pitfall")
python3 rescore_java.py

# aggregate recall + cost per task × model × arm
python3 agg_jackson.py
```

Everything downstream of the agent (scoring, normalization, aggregation) is
deterministic — the paper's tables are reproducible from `harness/runs/`
**without any LLM**.

## Related repositories

The tools under test (all open source; Apache-2.0 / MIT):

- **Grove** — persistent code graph; hosts the `change_impact` engine operation: https://github.com/provasign/grove
- **Prism** — agent context delivery (CLI + MCP), exposes `prism_change_impact`: https://github.com/provasign/prism
- **astkit** — multi-language Tree-sitter parsing layer: https://github.com/provasign/astkit

## Citation

```bibtex
@misc{pal2026codegraph,
  title  = {When Does a Code Graph Help a Coding Agent? Blast Radius, Model
            Capability, and Tool Altitude in Change-Impact Tasks},
  author = {Pal, Tapabrata},
  year   = {2026},
  note   = {Preprint. Artifacts: https://github.com/provasign/research}
}
```

## License

MIT — see [LICENSE](LICENSE).
