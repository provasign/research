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
| local 30B ($0)  | **1.00** (23.8 s) | (weak tier: see Haiku) | — |
| Haiku (cheap)   | **1.00** · 3 turns · 67k tok · $0.04 | 0.00 · 31 turns · 1.79M · $0.33 | 0.75 |
| Opus (frontier) | **1.00** · 3 turns · 60k tok · $0.14 | 1.00 · 23 turns · 1.43M · $2.38 | 0.62 |

- At equal correctness (Opus row), Prism is **~17× cheaper and ~30× faster**.
- CodeGraph requires a frontier model to become complete; on the cheap tier
  it delivered 0.00 while spending more tokens than grep.
- Prism is the only arm that stays complete as the model gets cheaper —
  down to a free local 30B.

## 4 · Local models can do agentic coding — with the right tool

- Local qwen3-coder:30b + Prism (via mason): recall **1.00** on the
  diagnostic change-impact task, $0, 23.8 s
  ([`harness/runs/ab-agentic/`](harness/runs/ab-agentic/)).
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

## 6 · Where each result comes from

| claim | source | raw data |
|---|---|---|
| With/without-Prism agent grid | paper §Results I–II | `harness/runs/<task>/<model>/` |
| Engine ceiling 0.993/0.948 | paper §"engine ceiling" | `harness/engine_ceiling.py` output |
| Prism 0.99 vs CodeGraph 0.52 | `harness/AB-CODEGRAPH.md` §1 | `harness/runs/codegraph-engine/` |
| Efficiency sweep | `harness/AB-CODEGRAPH.md` §2 | `harness/efficiency_sweep.py` |
| Agent A/B incl. CodeGraph | `harness/AB-CODEGRAPH.md` §3 | `harness/runs/ab-agentic/` |
| Local-tier result | `harness/AB-CODEGRAPH.md` §4 | `harness/runs/ab-agentic/jsonnode.local-30b.prism.json` |
| Local CLIs (OpenCode/Continue) | `harness/AB-LOCAL-CLIS.md` | `harness/runs/` |
| Contamination measurement | `harness/SWEBENCH-AB-RESULTS.md` | `harness/runs/swebench-20/` |
