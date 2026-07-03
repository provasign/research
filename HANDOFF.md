# HANDOFF — provasign/research (read this first)

Single, self-contained restart point. Everything below is committed on `main`
(run *data* is gitignored, machine-local — see §Assets). Last updated 2026-07-03.

This project has become **two things** that share one body of evidence:

1. **A research paper** (done, arXiv-ready draft): *When does a resolved code
   graph actually help an LLM coding agent?* Answer: **conditionally — the value
   is gated by `capability × blast-radius`, and by tool *altitude*.**
2. **A product bet** (emerging, the exciting part): **a FREE local open-weights
   model + a graph-backed `change_impact` tool can compete with commercial
   frontier models on change-impact completeness — at zero API cost.** We have a
   proof-of-concept interaction; the scored version is the next build.

---

## 1. The research result (solid, measured, committed)

Controlled paired study. Same task, three arms (**T** text/grep, **G** graph via
Prism/Grove, **V** graph-as-verifier), scored against an **independent** oracle
(Go: `go-ssa-vta`; Java: a **Spoon type-resolution oracle**, `harness/java-oracle/`).
Mode A = "list every site that must change." Subjects: 14 Go tasks + **6
jackson-databind Java tasks** spanning **8/22/38/58/104/108 change-sites**.
Models: **Haiku, Sonnet, Opus** (via Claude Code), n=5/cell, 157 scored runs,
~$265 total.

**Headline (recall, Δ = G−T):**

| sites | Haiku | Sonnet | Opus |
|---|---|---|---|
| 8   | +.00 | +.15 | +.02 |
| 22  | +.01 | +.05 | +.02 |
| 38  |  —   | +.03 | +.00 |
| 58  |  —   | +.01 | +.01 |
| 104 | **+.17** | **+.17** | +.04 |
| 108 | **+.24** | **+.13** | +.00 |

- **Small/greppable tasks → graph ≈ text** at every tier (the Go null holds).
- **Large-blast-radius tasks → graph wins big for weak/mid models** (recall +
  variance collapse: Sonnet serialize T 0.87 swinging to 0.73 vs G 0.996±0), and
  it's a **capability equalizer** — lifts weak models toward frontier completeness.
- **At the frontier the recall gap closes** (Opus text enumerates it), and the
  graph becomes a **cost** lever (cheaper on 4/6 tasks) + a reliability tail-risk
  reducer on hard tasks.
- **Discriminator = blast radius (sites reachable only via caller edges), NOT
  name ambiguity or language.** Go rarely produced large-enough tasks; Java
  framework interfaces do.

Falsifiable sub-claims + verdicts: `THESIS.md` (C1–C7). Full prose: `paper.md`.

---

## 2. The product bet (the new direction) — "free local + graph vs commercial"

### HEADLINE PRINCIPLE (the whole product thesis in one line)
**A deterministic graph traversal must not run inside the stochastic,
token-expensive LLM loop — the graph engine should compute it and hand the agent
the answer.** Grove/Prism today expose *primitives* (`references`, `lookup`,
`query`) the model has to **orchestrate** over many turns (find declaration → find
overrides → find callers → dedup). That orchestration is exactly what is
expensive, unreliable, and capability-gated. The enhancement is to **raise the
tool altitude**: expose task-shaped operations — first and foremost
`change_impact(method) → declaration + override/impl family + resolved callers` —
that do the traversal in the engine. `change_impact` is the clearest instance of a
*class* (all implementors of an interface, full call chains, file blast radius);
primitives stay underneath for drill-down.

**This helps EVERY tier, not just local models** — the value shifts by capability
but never disappears (numbers from our grid):

| tier | on primitives today | with `change_impact` |
|---|---|---|
| Local 30B | **0.0** (can't orchestrate at all) | **enabling** — 0.0 → complete; the graph is otherwise unusable to it |
| Haiku | large tasks **0.69 / 0.85** (imperfect orchestration) | **raises the ceiling** → ~1.0, far fewer turns |
| Sonnet | good recall but **50–65 turns**, real variance | **kills variance + slashes cost/latency** — one deterministic call |
| Opus | ~1.0 but **24–39 turns, ~$5.64/run** on deserialize | recall ~unchanged; **cost → cents, latency → one call, deterministic** |

So: enabling for weak/local, *correctness+cost* for cheap cloud, *cost+latency+
determinism* for the frontier. No model should hand-simulate a traversal the graph
can answer exactly. This is why the enhancement is a general Grove/Prism win, and
why the "free local competes with commercial" bet is its most dramatic (0 → works)
demonstration, not its only justification.

**Thesis (the bet):** the graph's completeness win is *largest for weak/cheap
models on large changes*. So a **free local model + the right graph tool** should
reach *commercial-frontier completeness* on change-impact — for $0/query. If true,
that reframes Grove/Prism from "a nice context source" to "the thing that lets free
local models compete with GPT/Claude on real repo tasks" — while also making the
commercial models themselves cheaper and more reliable.

**What we've shown (PoC, `harness/LOCAL-TIER-FINDINGS.md`):**
- A local `qwen3-coder:30b` on graph **primitives** (CLI *or* MCP-style tools)
  scores **0.0** on the graph arm — it greps ok but can't (a) orchestrate a
  multi-turn traversal or (b) reliably emit tool calls. **Two walls:
  orchestration + invocation.**
- Exposed as ONE **high-altitude** call — `change_impact(method) → declaration +
  override/impl family + resolved callers` — with an impact-routing scaffold that
  forces the call, the SAME model relayed a **complete change-set (recall 1.0) on
  all 6 tasks, one call each** (precision 0.97–1.0).

**⚠️ VALIDITY — do not overclaim this yet.** The PoC `change_impact.py` is
**Spoon-powered — the same engine that makes our ground truth** — so that 1.0 is
*tautological*. It proves the **interaction** (a weak model faithfully relays a
high-altitude tool in one call) + the **contrast** with primitives (0.0). It is
**NOT** a graph-vs-text score, and it is **NOT** yet "local competes with GPT."

**To turn the bet into a measured claim (the next build):**
1. Build a **real `change_impact` inside Grove/Prism** — type-resolved
   change-impact from the graph itself, *independent* of the Spoon eval oracle.
   (Prism's current `references` is name-based/over-matching; grove `impact` is
   too coarse. This needs genuine type resolution in the graph.)
2. **Head-to-head:** `local-model + Grove.change_impact` vs `commercial-model +
   text` (and vs commercial + Grove), scored by the independent Spoon oracle, on
   the size curve. That's the honest "free local competes with commercial" number.
3. **Mode B (compile / fail-to-pass):** does the completeness win convert to task
   success (a missed site breaks the build)? This is what makes "competes"
   concrete.

---

## 3. Repo map (what each thing is)

**Docs (current):**
- `paper.md` — the paper (working source, full prose, all tables).
- `paper/paper.tex` + `paper/README.md` — arXiv-ready LaTeX (compiles with
  `tectonic paper.tex`; PDF verified). TODOs: authors/affiliation, artifact URLs,
  citation verification (all marked `TODO` in the `.tex`).
- `THESIS.md` — falsifiable sub-claims C1–C7 + verdicts.
- `LOCAL-MODEL-SETUP.md` — stable daily-coding setup (Ollama → VS Code/Codex/
  Claude Code) + the local research tier.
- `harness/LOCAL-TIER-FINDINGS.md` — the local-model arc + `change_impact` PoC.
- `harness/java-oracle/README.md` — the Spoon oracle + task generation.
- `harness/java-oracle/CODEX.md` — how to run the GPT/Codex tier.
- `harness/README.md`, `harness/PILOT.md` — **historical** (Go-era harness +
  pilot data notes); useful provenance, not the current story.

**Harness (`harness/`):**
- `schema.py` (types + robust answer parser), `score.py` (oracle scorer),
  `arms.py` (T/G/V prompts, **language-aware**).
- Runners: `run.py` (Claude/Claude Code), `run_codex.py` (GPT/Codex), `run_local.py`
  (local, raw-CLI, HARD arm gate), `run_local_mcp.py` (local, structured tools),
  `run_local_hitool.py` (local + `change_impact`, the PoC demo).
- `change_impact.py` — the high-altitude tool (resolve `Class.method(params)` →
  precise change-set; Spoon-powered PoC — see validity note).
- `rescore_java.py` — **MANDATORY for all Java runs** (see §Gotchas).
- `agg_jackson.py` — recall + tokens + USD, per task×model×arm; **auto-discovers
  model dirs** (Claude/GPT/local all appear).
- `java-oracle/` — Spoon oracle (`Oracle.java` → `target/oracle.jar`, gitignored),
  `make_java_task.py`, `env.sh` (JDK 26), pilot scripts.
- `tasks/jackson-*.json` — the 6 size-graded tasks (GT from the oracle).
- `runs/` — **gitignored** run data (the source of all numbers).

---

## 4. Assets & environment (machine-local, not in git)

- **Corpus:** `~/gvg-corpus/jackson-databind` @ tag `jackson-databind-2.18.8`
  (`0b422144`), Prism-indexed (`.grove/`). Also Go corpora (grafana/gin) from the
  Go phase. Never put corpora in `/tmp` (gets cleaned).
- **Local models (Ollama, autostart service, global `~/.ollama`):**
  `qwen3-coder:30b` (agentic, 18 GB), `qwen2.5-coder:14b` (chat, 9 GB),
  `qwen2.5-coder:1.5b-base` (autocomplete, 1 GB). Machine: Apple M5 Pro, 24 GB.
- **Binaries:** `~/bin/prism`, `~/bin/grove` (the graph under test); `codex` CLI;
  JDK 26 via Homebrew (`source harness/java-oracle/env.sh`); `tectonic` (LaTeX).
- **Prism/Grove/harness are open-sourced** (URLs go in `paper/paper.tex` artifact
  section — currently placeholders).

---

## 5. How to run

```bash
cd harness && source java-oracle/env.sh        # JDK for the oracle

# Claude tier (Claude Code):   python run.py       --task tasks/<t>.json --arms T G --trials 5 --model sonnet --workdir ~/gvg-corpus/jackson-databind
# GPT tier (Codex):            python run_codex.py --task tasks/<t>.json --arms T G --trials 5 --model gpt-5-codex --workdir ~/gvg-corpus/jackson-databind   (see java-oracle/CODEX.md)
# Local tier (raw CLI):        python run_local.py --task tasks/<t>.json --arms T G --trials 5 --model qwen3-coder:30b --workdir ~/gvg-corpus/jackson-databind
# change_impact PoC:           python run_local_hitool.py --task tasks/<t>.json --model qwen3-coder:30b --workdir ~/gvg-corpus/jackson-databind

# ALWAYS after Java runs:      for t in tasks/jackson-*.json; do python rescore_java.py --task $t; done
# Aggregate everything:        python agg_jackson.py
```
Regenerate a task: `python java-oracle/make_java_task.py --id <id> --display 'Class.method' --target 'FQN#method(params)'`.

---

## 6. Gotchas / validity guardrails (learned the hard way)

- **`rescore_java.py` is mandatory.** Prism reports `file:line`, so graph-arm
  agents answer sites as `File.java:114`; the name-based scorer matches those at
  0, silently penalizing the GRAPH arm. `rescore_java.py` maps line→method (via a
  Spoon line index) before scoring. Run it before ANY Java aggregation.
- **The `change_impact` 1.0 is tautological** (Spoon == GT). See §2. Never cite it
  as a graph-vs-text or "beats commercial" number without an independent oracle.
- **Harness confound across families.** Claude ran under Claude Code, GPT under
  Codex, local under bespoke loops. Cross-family *levels* aren't directly
  comparable; the clean comparison is **T vs G at a fixed (model, task)** (only
  the arm's tool guidance changes). Frame accordingly.
- **Local models: two walls.** Unreliable structured tool-calls (force with
  `tool_choice:"required"`) and can't orchestrate primitives (use high-altitude
  tools). A weak model's `rg 'pat'` with no path + non-tty stdin hangs 60s — fixed
  in `run_local.py` (stdin=/dev/null + auto-append path); watch for it elsewhere.
- **Bare-name Java GT is INVALID** (commons-lang attempt was discarded): a bare
  method name conflates unrelated same-named methods. Java GT must be
  type-resolved (Spoon). Targets that are `static` methods are greppable controls,
  not adversarial.
- **Usage/rate caps** pause the Claude/GPT runners (they wait + resume). Long
  unattended grids: `sudo pmset -a disablesleep 1` (caffeinate doesn't survive
  lid-close). `runs/` is gitignored — data lives only on this machine.

---

## 7. Open work (prioritized)

1. **Product build (the bet):** type-resolved `change_impact` *inside Grove/Prism*
   (independent of the Spoon oracle) → head-to-head **local+graph vs commercial**,
   scored by the independent oracle. This is the "free local competes with
   commercial" result. (§2.)
2. **Mode B** (compile / fail-to-pass) — does completeness convert to task success.
3. **External validity:** replicate the large-task regime on a 2nd framework
   (Spring/Guava) + a large Go codebase with wide interfaces (proves lever = size,
   not "Java").
4. **Finish the GPT/Codex tier** (`java-oracle/CODEX.md`) — smoke-test one cell to
   tune the event-trace parser, then the grid; gives a cross-family point.
5. **arXiv polish:** authors/affiliation, artifact URLs, verify the 12 citations
   in `paper/paper.tex` (best-effort from memory — must be checked).

---

## 8. One-line status

Research result: **done and committed.** Paper: **arXiv-ready draft** (3 TODOs).
Product bet: **PoC in hand, honestly caveated; the measured version is build #1
above.** Daily local-coding setup: **live** (`LOCAL-MODEL-SETUP.md`).
