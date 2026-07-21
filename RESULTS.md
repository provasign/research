# Results — the numbers, in one place

Every number below is oracle-scored and reproducible from the run logs in
this repository without an LLM. Sources: the paper
([`paper/paper.tex`](paper/paper.tex)), the CodeGraph comparison
([`harness/AB-CODEGRAPH.md`](harness/AB-CODEGRAPH.md)), and the
negative-result reports linked in §5.

Arms shorthand: **T** = text search only (rg/grep/read) — *the "without
Prism" agent*. **G** = graph primitives the agent orchestrates. **G\*** =
Prism at task altitude (one `change-impact` call) — *the "with Prism"
agent*.

## 1 · With Prism vs without Prism — the agent benchmark

Change-impact tasks ("list every site this signature change breaks"),
jackson-databind, 8→108 sites, independent Spoon oracle, enforced tool
allowlists. Mean recall / cost per task / agent turns:

| tier | without Prism (T) | graph primitives (G) | **with Prism (G\*)** |
|---|---|---|---|
| Haiku  | 0.758 · $0.48 · 31 | 0.833 · $0.53 · 41 | **0.997 · $0.11 · 2.8** |
| Sonnet | 0.951 · $2.13 · 45 | 0.978 · $2.20 · 44 | **0.997 · $0.53 · 11.7** |
| Opus   | 0.952 · $2.14 · 22 | 1.000 · $3.06 · 21 | **0.997 · $0.48 · 4.0** |

- **Without Prism, completeness is bought with model capability** (recall
  ladder 0.76→0.95 tracks the price ladder) and never becomes reliable:
  even Opus-on-text dipped to 0.71 on the 104-site task.
- **With Prism, completeness is tier-invariant**: every tier lands on 0.997.
  The cheapest model plus Prism strictly dominates the frontier model on
  text — higher mean, no tail risk, **28× cheaper** ($3.06 → $0.11).
- The engine op alone (no LLM) scores **0.993 recall / 0.948 precision**
  against the oracle — the agent relays the ceiling, it does not create it.
- Cross-language external validity: the same pattern holds on Go,
  TypeScript, and Python tasks, and on a second Java codebase
  (Commons Collections); see the paper §Results II.

## 2 · Cross-tool benchmarking (ongoing) — engine completeness (no LLM)

For transparency we continuously benchmark Prism against other open-source
context tools under one standing rule set (same oracles, same scorer,
strongest surface, goals stated fairly, raw runs published). First entry:
CodeGraph. Both engines, same oracle, same scorer, 10 tasks, 4 languages,
blast radius 8→310 sites. Full table and fairness protocol:
[`harness/AB-CODEGRAPH.md`](harness/AB-CODEGRAPH.md).

| | Prism | CodeGraph (its headline `explore`) |
|---|---:|---:|
| mean recall (n=10) | **0.99** | 0.52 |
| java (n=7) | 0.997 | 0.46 |
| go (n=1) | 1.00 | 1.00 (a genuine tie — the control) |
| ts (n=1) | 0.95 | 0.73 |
| py (n=1) | 1.00 | 0.25 |

Efficiency at the raw-tool level (reported next to recall, never alone):
CodeGraph is ~2× faster on average — by doing less; its lower token counts
on large tasks coincide with recall 0.17/0.00. Where both are complete
(gin), Prism is faster.

## 3 · Prism vs CodeGraph vs grep — the agent A/B (with agent numbers)

Same agent (`claude -p`), same task, arms differ only in the tool; recall to
reach a complete change-set and what it cost:

| tier | Prism | CodeGraph | baseline (grep) |
|---|---|---|---|
| local 30B ($0)  | **1.00** | (weak tier: see Haiku) | — |
| Haiku (cheap)   | **1.00** · 3 turns · 67k tok · $0.04 | 0.00 · 31 turns · 1.79M · $0.33 | 0.75 |
| Opus (frontier) | **1.00** · 3 turns · 60k tok · $0.14 | 1.00 · 23 turns · 1.43M · $2.38 | 0.62 |

- At equal correctness (Opus row), Prism is **~17× cheaper and ~30× faster**.
- CodeGraph requires a frontier model to become complete; on the cheap tier
  it delivered 0.00 while spending more tokens than grep.
- Prism is the only arm that stays complete as the model gets cheaper —
  down to a free local 30B.

## 4 · Local models can do agentic coding — with the right tool

- Local qwen3-coder:30b at task altitude (change_impact): recall **1.00**
  on the diagnostic task (agent-scored, all 8 sites) and **0.997 mean** across
  the 7-task change-impact grid, $0
  ([`harness/runs/*/qwen3-coder-30b-gstar/`](harness/runs/)).
- The same local model driving generic CLIs without task-altitude tooling
  (OpenCode, Continue.dev) scored 0–1/9 on the same task family
  ([`harness/AB-LOCAL-CLIS.md`](harness/AB-LOCAL-CLIS.md)).
- Mechanism: the paper's tier-invariance result — the engine computes the
  traversal, so the model only identifies the target and relays the result.

## 5 · What we do NOT cite, and why (trustability audit)

Numbers we measured, publish, and refuse to use as evidence:

| experiment | headline-looking number | why it is not citable |
|---|---|---|
| SWE-bench Verified A/B ([`harness/SWEBENCH-AB-RESULTS.md`](harness/SWEBENCH-AB-RESULTS.md)) | baseline "resolves" 75% | **Contamination, measured**: 9/20 tasks reproduce the merged human fix with 100% exact added-line overlap ([`harness/contamination_check.py`](harness/contamination_check.py)). Memorization, not tooling — cannot support claims for *or against* Prism. |
| PR-replay mining, Netty ([`harness/PR-REPLAY-FINDINGS.md`](harness/PR-REPLAY-FINDINGS.md)) | recall on "real PRs" | Ground truth from loose PR classification is polluted (top-scoring "task" was an aggregate merge PR); strict gates collapse yield to zero in our sample. No number from this pilot is trustworthy in either direction. |

The real-life-PR question ("does Prism help on actual merged changes?")
therefore has **no citable number yet**. The citable path is documented in
the PR-replay report: compiler-as-oracle on verified refactors, or a live
pipeline on fresh PRs that post-date model training cutoffs.


## 7 · 2026-07-20 — the task compiler, the verify gate, and the mason+local headline

All runs oracle-scored on the 9-task bed (Java/Go/TS/Py, 8–310 sites), cached
under `harness/runs/`. Drivers: `harness/ab_unified.py`, `harness/ab_phrasing.py`,
`harness/ab_phrasing2.py`, `harness/verify_bench.py`, `harness/mason_bench.py`.

### Unified `prism(task)` tool, three model tiers (`runs/ab-unified/`, 3 trials/cell)

| model | grep baseline | unified prism | direct change_impact |
|---|---|---|---|
| Haiku  | 0.721 @ 1,592k tok | **0.896 @ 104k** | 0.869 @ 226k |
| Sonnet | 0.877 @ 1,441k | 0.875 @ 279k | 0.955 @ 488k |
| Opus   | 0.958 @ 552k | **0.983 @ 113k** | 0.987 @ 203k |

Cheap tier: capability win (+0.175 recall, 15× fewer tokens). Frontier:
economics win (recall ~ties, 5× fewer tokens). Sonnet wart: occasionally
answers in 1 turn without calling the tool (the measured discretion problem).

### Phrasing sensitivity (`runs/ab-phrasing*/`)

Stripping the target symbol from the task collapses tool-only retrieval
(grafana 0.941 → 0.007 when the agent is FORBIDDEN from rephrasing/grepping).
A GUESSED term for a common name hurts (jackson 0.837 → 0.565). Natural agent
behavior — investigate, form its own task string, pass CONFIRMED terms —
recovers most of it (0.02 → 0.61 on the same vague prompts). Steering now
says: confirmed anchors, never guessed terms.

### Verify at corpus scale (`runs/verify-bench/`, seeded incomplete edits, 3 trials + control × 9 corpora)

Verdicts are **fail-closed 36/36** (28 incomplete, 8 review, 0 false
"complete") — after fixing three fail-open holes the first run exposed
(empty post-edit blast radius; subdir work-roots (guava/guava) path-mismatch;
TS/Go declaration-block member changes never seeded). Site-level catch:
137/420 forgotten files pre-fix. **Base-contract enumeration landed the same
day (prism v0.28.0)**: dependents of the OLD signature recovered via
base-parameter-list family match + their still-resolved callers — catch
**33% → 80%** (prism v0.29.0: + generic-type-variable wildcards + TYPE-only
parameter matching — override families rename params freely). Per task:
django/checkhealth/jsonnode 100%, querydata 94%, guava 93%, serialize 83%,
settable 71%, writetypeprefix 57%, typeorm 0% (declaration-block members —
the one remaining gap, held at review, never a silent pass). **False flags:
ZERO** across all trials and controls — the earlier "false flags" audited to
a bench artifact (basename collisions: grafana has 12 healthcheck.go files;
every audited flagged line was a genuinely untouched site in a NON-updated
same-named file). Raw: `harness/runs/verify-bench/definitive-v0.29.0.log`.
Positioning: trust the verdict AND the site list; declaration-block members
are the disclosed remainder.

### Mason + free local model — the headline (`runs/mason-bench/`, 2 trials/task)

**mason v0.27.0 + qwen3-coder:30b (local, $0): mean recall 0.989, median
1.000, mean input 16k tokens** — above every measured cloud arm (best:
Opus+unified 0.983 @ 113k). Scoring is the narrated engine relay — mason's
payload isolation keeps graph payloads out of the model's context by design,
and the model's own JSON recitation hallucinates paths when asked to retype
the list (measured; that failure is what payload isolation exists to
prevent). Precision 0.48–1.0: the relay includes the full family
(declaringTypes, tests) beyond the oracle's caller set.

## 6 · Where each result comes from

| claim | source | raw data |
|---|---|---|
| With/without-Prism agent grid | paper §Results I–II | `harness/runs/<task>/<model>/` |
| Engine ceiling 0.993/0.948 | paper §"engine ceiling" | `harness/engine_ceiling.py` output |
| Prism 0.99 vs CodeGraph 0.52 | `harness/AB-CODEGRAPH.md` §1 | `harness/runs/codegraph-engine/` |
| Efficiency sweep | `harness/AB-CODEGRAPH.md` §2 | `harness/efficiency_sweep.py` |
| Agent A/B incl. CodeGraph | `harness/AB-CODEGRAPH.md` §3 | `harness/runs/ab-agentic/` |
| Local-tier result (change_impact) | `harness/AB-CODEGRAPH.md` §4 | `harness/runs/*/qwen3-coder-30b-gstar/` |
| Local CLIs (OpenCode/Continue) | `harness/AB-LOCAL-CLIS.md` | `harness/runs/` |
| Contamination measurement | `harness/SWEBENCH-AB-RESULTS.md` | `harness/runs/swebench-20/` |
| Unified-tool 3-tier grid | §7 above | `harness/runs/ab-unified/` |
| Phrasing sensitivity | §7 above | `harness/runs/ab-phrasing/`, `ab-phrasing2/` |
| Verify corpus bench | §7 above | `harness/runs/verify-bench/` |
| Mason+local 0.989 | §7 above | `harness/runs/mason-bench/` |
