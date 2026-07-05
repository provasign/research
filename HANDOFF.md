# HANDOFF — provasign/research (read this first)

Single, self-contained restart point. Last updated 2026-07-05.

**Research:** done — 4 languages (Go/Java/TypeScript/Python), paper arXiv-ready
(`paper/paper.tex`; 3 TODOs: affiliation, citation check, artifact URL confirm).
**Product:** released — grove v0.15.0, prism v0.17.1, fuse v0.13.3; homebrew-shale
tap current; steering streamlined to three layers (task ops / reads / query).
Sibling ops (missing_implementations, untested_surface, dead_code) shipped in
grove v0.15.0 / prism v0.17.0.

---

## Open work

**1. arXiv polish (before submission)**
- Add author names and affiliation — the only structural TODO left in `paper/paper.tex`
- Verify the 12 citations (all marked `TODO` in the .tex — best-effort from memory, must be checked)
- Confirm artifact URLs in the Artifact section still resolve (four release tags: astkit v0.4.17, grove v0.14.1, prism v0.16.1, research v1.0.0)

**2. Mode B — compile / fail-to-pass**
§5.5 has a derived metric (expected compile failures from missed sites) but actual
compilation was never run. This is what makes "competes with commercial" concrete for
companies — a missed change site breaks the build. Setup: `run_local_gstar.py` result
set → apply edits → compile and report pass/fail.

**3. GPT/Codex tier**
Cross-family data point for the paper. `harness/java-oracle/CODEX.md` has the
setup. Adds a row to Table 4 (T vs G* at a fixed task, across model families).

**4. `rename_plan` (4th sibling op)**
`change_impact` + new name applied to each site as a structured edit plan. First
"do" operation (not just "find"). Explicitly deferred pending Mode B validation —
if the completeness win converts to task success, the rename_plan edit-production
architecture follows the same pattern.

---

## Repo map

| Path | What it is |
|---|---|
| `paper/paper.tex` | arXiv-ready LaTeX (compiles with `tectonic paper.tex`) |
| `THESIS.md` | Falsifiable sub-claims C1–C7 + verdicts |
| `harness/README.md` | Arms (T/G/G*), scoring, relay rationale |
| `harness/LOCAL-TIER-FINDINGS.md` | Local-model arc + change_impact result |
| `harness/java-oracle/README.md` | Spoon oracle + task generation |
| `harness/java-oracle/CODEX.md` | GPT/Codex tier setup |
| `LOCAL-MODEL-SETUP.md` | Daily-coding setup (Ollama → editors) |
| `harness/schema.py` | Types + answer parser |
| `harness/score.py` | Oracle scorer |
| `harness/arms.py` | T/G/G*/V prompts, language-aware |
| `harness/run_local_gstar.py` | **The scored result** — local 30B + real Grove engine |
| `harness/rescore_java.py` | Mandatory post-processing for all Java runs |
| `harness/agg_jackson.py` | Aggregate recall/tokens/cost across all runs |
| `harness/tasks/jackson-*.json` | 6 size-graded tasks (GT from Spoon oracle) |
| `harness/runs/` | Run data (gitignored; source of all numbers) |

---

## Environment (machine-local)

- **Corpus:** `~/gvg-corpus/jackson-databind` @ tag `jackson-databind-2.18.8` (`0b422144`), Prism-indexed
- **Local models (Ollama):** `qwen3-coder:30b`, `qwen2.5-coder:14b`, `qwen2.5-coder:1.5b-base`
- **Binaries:** `~/bin/prism` (v0.17.1), `~/bin/grove` (v0.15.0); `codex` CLI; JDK 26 via Homebrew; `tectonic`

---

## How to run

```bash
cd harness && source java-oracle/env.sh    # JDK for the oracle

# Claude tier:  python run.py       --task tasks/<t>.json --arms T G --trials 5 --model sonnet --workdir ~/gvg-corpus/jackson-databind
# GPT tier:     python run_codex.py --task tasks/<t>.json --arms T G --trials 5 --model gpt-5-codex --workdir ~/gvg-corpus/jackson-databind
# Local G*:     python run_local_gstar.py  --task tasks/<t>.json --model qwen3-coder:30b --workdir ~/gvg-corpus/jackson-databind

# ALWAYS after Java runs:  for t in tasks/jackson-*.json; do python rescore_java.py --task $t; done
# Aggregate:               python agg_jackson.py
```

Regenerate a task: `python java-oracle/make_java_task.py --id <id> --display 'Class.method' --target 'FQN#method(params)'`

---

## Validity guardrails

- **`rescore_java.py` is mandatory.** Prism reports `file:line`; the name-based scorer silently penalizes the graph arm without it. Run before any Java aggregation.
- **The `change_impact.py` PoC recall is tautological** (Spoon == GT). Never cite it as graph-vs-text. Cite `run_local_gstar.py` instead (0.997 mean recall, Grove engine, independent oracle).
- **Bare-name Java GT is invalid** — Java GT must be type-resolved (Spoon). Targets that are `static` methods are greppable controls, not adversarial.
- **mapiterator-next failed audit — excluded.** Do not cite its 0.585 numbers. §5.6 + §Threats document why.
- **`reparse_all.py` clobbers rescore_java's line→method mapping** — always re-run rescore_java for every Java corpus after it.
- **Answer parser is strict=False** (`schema.py`) — agents emit literal newlines inside JSON; the strict decoder zeroed whole answers.
- **Usage/rate caps** pause the runners (they wait + resume). Long grids: `sudo pmset -a disablesleep 1`.
