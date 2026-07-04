# HANDOFF — provasign/research (read this first)

Single, self-contained restart point. Everything below is committed on `main`
(run *data* is gitignored, machine-local — see §Assets). Last updated 2026-07-03.

This project has become **two things** that share one body of evidence:

1. **A research paper** (done, arXiv-ready draft): *When does a resolved code
   graph actually help an LLM coding agent?* Answer: **conditionally — the value
   is gated by `capability × blast-radius`, and by tool *altitude*.**
2. **A measured result** (the exciting part): **a FREE local 30B model +
   `change_impact` reaches 0.997 mean recall — identical to Haiku, Sonnet, and
   Opus — at $0/query in 1 agent turn.** Scored against the independent Spoon
   oracle. The gate is cleared; this is no longer a proof-of-concept.

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

**Measured result (not a PoC):** `run_local_gstar.py` calls `~/bin/prism
change-impact` — the Grove graph engine, independent of the Spoon oracle.
Scored against the Spoon oracle: 0.997 mean recall, $0, 1 turn per task.
This is the honest graph-vs-text number: local 30B + Grove = 0.997 vs
Opus+text = 0.952.

**Note:** The original `change_impact.py` PoC was Spoon-powered (tautological).
Do not cite that PoC recall; cite the `run_local_gstar.py` result instead.

**Next to make "competes" concrete:**
- **Mode B (compile / fail-to-pass):** does the completeness win convert to
  task success (a missed site breaks the build)? This is what makes "competes"
  concrete for companies.

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
  `run_local_hitool.py` (local + `change_impact.py` PoC — Spoon-backed, tautological),
  **`run_local_gstar.py` (local + real Grove engine — this is the scored result)**.
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
# Local G* (real engine):      python run_local_gstar.py  --task tasks/<t>.json --model qwen3-coder:30b --workdir ~/gvg-corpus/jackson-databind

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
- **`reparse_all.py` clobbers rescore_java's line→method mapping** — always
  re-run rescore_java for every Java corpus after it (see its docstring; four
  jackson runs were silently zeroed this way on 2026-07-04 and restored).
- **Answer parser is now strict=False** (schema.py): agents emit literal
  newlines inside JSON strings; the strict decoder used to zero the entire
  answer (a 350-site Sonnet T answer scored 0.0 until fixed).
- **Weak-match audit**: agg_jackson.py flags runs whose credited sites are
  >34% symbol-only fallback. Jackson corpus mean is 3.5% (clean); any task
  whose GT shares one generic symbol name (next, get) is scorer-hostile —
  prefer distinctively-named targets.

---

## 7. Open work (prioritized)

> **Status 2026-07-04.** All experiments done. Paper updated. Gate cleared.
> Local 30B measured. Steering extended. External validity partial.

### Done
- ~~Graph-native `change_impact` in Grove/Prism~~ — engine recall 0.993 vs
  oracle (`harness/GROVE-CHANGE-IMPACT.md`).
- ~~G* grid (T/G/G* × 3 tiers × 6 tasks)~~ — tier-invariant 0.997; paper
  rewritten around blast radius × tool altitude (`paper/paper.tex`).
- ~~`prism_change_impact` MCP tool + CLI + G*-first steering templates~~ —
  shipped, binary rebuilt, all init files updated.
- ~~**Local 30B G* on real engine**~~ — **DONE. 0.997 mean recall, $0, 1 turn.**
  `run_local_gstar.py` calls `~/bin/prism change-impact` (Grove, not Spoon PoC).
  Scored against independent oracle. Per-task: 1.000/1.000/1.000/1.000/1.000/0.982.
  Identical to Haiku/Sonnet/Opus G*. Full table in `paper/paper.tex` Table 4.
- ~~Steering prompt expansion~~ — decision tables in all 3 templates now have 5
  rows for change_impact (method rename, interface, type rename, deprecation,
  "find all X"). Pre-task rule added. Committed to prism, binary rebuilt.
- ~~**External validity (partial, Apache Commons Collections)**~~ — 2 tasks
  created and run (`tasks/commons-collections-*.json`). Small-task tie
  replicates (17 GT: T=G*=Local30B=1.000; T needed 61 turns vs G* 27).
  **Large task (142 GT, `MapIterator.next`) FAILED AUDIT — excluded, do not
  cite its 0.585 numbers.** Three defects: (1) ill-posed — MapIterator
  extends java.util.Iterator, so next() overrides a JDK method whose
  signature can't change; (2) oracle GT is a virtual-dispatch closure
  through the external interface (includes callers on plain Iterator
  receivers, e.g. CollectionUtils.addAll), not a must-change set;
  (3) `next` is so generic the scorer's symbol-only fallback dominated
  (55/83 credited sites weak) — T and G* got IDENTICAL scores for
  near-identical answers. Same audit discipline as commons-lang.
  §5.6 + §Threats rewritten in `paper/paper.tex`. Side finding kept: the
  engine's family walk stops at external supertypes (project-local dispatch
  recall 0.32) although the `extends` clause is in project source — engine
  work item, see below.

### 7.A — The gate
**CLEARED.** The honest headline: `qwen3-coder:30b + prism change-impact =
0.997 recall at $0/query vs Opus+text = 0.952 at $2.14/query.`

### 7.B — Research completion (after 7.A)

**2. Mode B (compile / fail-to-pass)** — §5.5 has derived metric (expected
compile failures); actual compilation not yet run.

**3. External validity — DONE (third corpus: Guava)**
- Small-task tie confirmed in commons-collections ✓ (17 GT, all arms 1.0;
  T 61 turns vs G* 27 — efficiency gap persists at equal recall)
- mapiterator-next failed audit — excluded (see Done). Guard added.
- **guava-forwarding-delegate: 310 GT sites** (ForwardingObject#delegate,
  guava-owned root, passes guard). Engine ceiling 0.997/1.000. Results:
  | arm | rec | prec | turns | wall | $ |
  |---|---|---|---|---|---|
  | Haiku G* | 0.997 | 1.000 | 4 | 102s | 0.18 |
  | Local30B G* | 0.997 | 1.000 | 1 | 224s | 0 |
  | Sonnet T | 0.997 | 1.000 | 55 | 811s | 3.85 |
  | Sonnet G* | 0.961 | 0.909 | 25 | 314s | 1.75 |
  | Haiku T | TIMEOUT at 20min (excluded); 40-min retry pending |
- **Findings:** (1) G* ceiling delivery replicates in corpus 3 at 3× the
  largest jackson blast radius. (2) Sonnet T TIES recall here — delegate()
  is name-unique/greppable, so the task is text-enumerable despite 310
  sites; refines the boundary variable: it's text-enumerability, not raw
  site count. Economics still invert ($3.85/55turns vs $0/1turn). (3) NEW
  mechanism datum: Sonnet G* (0.961) UNDERPERFORMS Haiku/local G* (0.997) —
  it re-processed the engine output through grep/awk/python and corrupted
  the relay; the scaffolded/minimal arms relayed losslessly. At task
  altitude, extra model initiative is negative capability — ship the relay
  scaffold, not just the tool.

**3c. Cross-language + tier completion (2026-07-04 PM)**
- **Guava full tier table:** Opus T 0.997/$5.46/516s; Opus G* 0.997/$0.66/119s;
  Fable G* 0.997/$1.40/155s (touched ONLY prism). Relay fidelity is
  behavioral, not a capability gradient — only Sonnet's trial re-derived.
  Relay rule shipped in all steering templates + MCP tool description.
- **Go (grafana bigblast, 93 GT):** engine fix (Go receiver methods attach
  cross-file within package) → ceiling 1.000/1.000. Haiku G* 1.000 (5 turns,
  $0.10), Local30B G* 1.000 (1 turn, $0) vs historical Haiku T 0.817±var /
  G 0.826. Variance collapse total. querydata/checkhealth tasks root in the
  external plugin-sdk interface (Go structural typing, no implements clause)
  — Go analog of the excluded Java task; method-set matching = engine v2.
- **TypeScript (TypeORM Driver.escape, 37 GT):** NEW ts-morph oracle
  (`harness/ts-oracle/oracle.mjs`, compiler-resolved GT + lineindex mode).
  Engine fix: subtype-closure rooting when interface members aren't indexed
  symbols (also fixed Go interface queries: DB.WithTransactionalDbSession).
  Engine ceiling LOW: 0.540/0.645 — family resolution works (11/12
  implements-clause drivers) but callers bind through interface-typed FIELDS
  (this.driver.escape) and the TS call resolver doesn't track field types.
  Local30B G* = 0.5405/0.6452 = EXACTLY the ceiling — lossless relay of an
  imperfect engine, cleanest tool-property demonstration in the study.
  TS field-type tracking = top engine roadmap item.
- Paper §5.6 + new §5.7 (cross-language) updated with all cells.

**3b. Engine work landed (grove/prism, committed)**
- Contract-boundary detection in change_impact: `externalSupers`,
  `overridesExternal` ("Iterator#next"), `completeness: closed|project-local`
  + explicit warning in MCP output. The excluded mapiterator task now
  self-reports its invalidity.
- External-rooted queries: `Iterator.next` (type not indexed) returns the
  project-local implementation closure (162 sites on commons-collections)
  instead of erroring — the well-posed migration/deprecation query.
- 5 new tests; jackson ceiling regression clean (engine_ceiling.py:
  1.0/1.0/.982/1.0/1.0/1.0). Steering templates teach the completeness field.
- Oracle guard: `overrides_external` in Oracle.java; make_java_task.py
  rejects ill-posed targets (--allow-external-override to bypass).

**4. GPT/Codex tier** (`java-oracle/CODEX.md`) — cross-family point for the paper.

**5. arXiv polish** — authors/affiliation, artifact URLs, verify the 12 citations
in `paper/paper.tex` (all marked TODO; best-effort from memory, must be checked
before submission).

### 7.C — Product roadmap (after 7.A proves the pattern)

The `change_impact` killer use cases are a well-defined set. The pattern that
makes them work: **the agent needs a *complete* set, the set is reachable only
by graph traversal, and missing one item breaks something.** Agents currently do
this with unreliable multi-turn orchestration; we replace it with one
deterministic call. The four validated use cases today:

| Use case | Trigger phrase | Cost of a miss |
|---|---|---|
| Method signature change | rename, add/remove param, change return type | build breaks at every missed call site |
| Interface/base class evolution | add method to interface, change abstract method | every non-compliant implementor fails |
| Type rename/refactor | rename a class, struct, or type alias | every usage of the old name breaks |
| Deprecation + migration | deprecate a symbol, migrate all call sites | incomplete migration ships deprecated code |

**6. Steering prompt improvement (small change, high impact)**
The current steering fires on "signature change." Extend to also catch the
interface and type cases explicitly — these are the same G* trigger but agents
don't always recognize them today:

```
| Changing/renaming a method signature            | prism_change_impact |
| Adding/changing a method on an interface        | prism_change_impact |
| Renaming a class, type, or struct               | prism_change_impact |
| Migrating/deprecating a symbol (find all sites) | prism_change_impact |
```

Also add a pre-task rule: *"Before writing any code on a task that involves
changing an existing symbol's name or signature: call `prism_change_impact`
first to establish the complete change-set — even if the change looks small."*
The `jsonnode-get` result (8 sites, Sonnet text 0.78) is the proof: agents think
they're done when they aren't. The rule removes the assumption.

**7. `dead_code(entry_points)` → complete list of unreachable symbols**
Same pattern as `change_impact`. Agents today: grep for call sites manually,
give up after a few files, miss transitive dead code. With the op: one
deterministic BFS backward from all entry points. Use case: before large
cleanups, library extractions, open-sourcing. Expected economics: identical
to `change_impact` — LLM can't enumerate transitively-unreachable symbols
reliably; the graph can in milliseconds.

**8. `untested_surface(symbol or package)` → all code paths with no test in call chain**
Graph knows who calls what; harness knows which files have tests; intersection
is computable. Use case: "before I refactor this, what do I need to cover?" —
agent writes tests for exactly the returned list. Natural pairing:
`change_impact` → `untested_surface(change_set)` → write tests for those.

**9. `missing_implementations(interface)` → all types claiming to implement the interface but missing methods**
Direct companion to `change_impact` for interface evolution. Use case: add a
method to an interface → `change_impact` finds callers, `missing_implementations`
finds every implementor now broken. Fully deterministic; the compiler knows it,
we should surface it before the compiler does.

**10. `rename_plan(old_symbol, new_name)` → complete change-set with suggested substitutions**
`change_impact` + the new name applied to each site as a structured edit plan.
Agent's job becomes: review and apply, not discover. Crosses into Mode B
territory — the first "do" operation, not just "find."

**Sequencing rule:** items 7–10 all block on 7.A. If the local 30B G* run
confirms the pattern (relay a complete answer from the engine, one call), then
the same architecture works for all of them — build `dead_code` next as the
second proof, then `untested_surface`, then the rest.

---

## 8. One-line status

Research: **done, both experiments** (blast radius × tool altitude). Paper:
**arXiv-ready** (`paper/paper.tex`; 3 TODOs: affiliation, URLs, citation check).
Product: **`change_impact` shipped end-to-end** (engine 0.993, MCP + CLI,
G*-first steering in all init templates). **Gate for everything next: local 30B
G* re-run on the real engine** (item 7.A.1) — that number turns the product
claim from a PoC into a measured fact. After that: Mode B, 2nd framework,
then the sibling ops (`dead_code`, `untested_surface`, `missing_implementations`)
follow the same architecture. Daily local-coding setup: **live**
(`LOCAL-MODEL-SETUP.md`).
