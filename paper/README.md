# arXiv submission — `paper.tex`

LaTeX source for the paper *"When Does a Code Graph Help an Agent? Capability- and
Blast-Radius-Bounded Gains for Change-Impact Tasks."* Self-contained: standard
`article` class, standard packages, an embedded `thebibliography` (no external
`.bib`, no bibtex pass needed).

## Build locally
```bash
# Option A: tectonic (single binary, fetches packages on first run)
tectonic paper.tex

# Option B: TeX Live / MacTeX
pdflatex paper.tex && pdflatex paper.tex   # twice, for cleveref refs
```
Run twice so `\cref`/`\Cref` cross-references resolve.

## Submit to arXiv
1. Compile cleanly locally first (above).
2. Upload **`paper.tex` only** (the embedded bibliography means no `.bbl` needed;
   arXiv runs its own TeX Live). If you add figures later, upload them too.
3. Suggested categories: **primary `cs.SE`**, cross-list **`cs.AI`** (and
   optionally `cs.LG`).
4. License: arXiv default (`arXiv.org perpetual, non-exclusive`) or CC-BY 4.0.

## BEFORE you submit — checklist (search the `.tex` for `TODO`)
- [ ] **Authors & affiliation.** `\author{...}` currently has one author and no
      affiliation. Add co-authors / affiliation / ORCID.
- [ ] **Artifact URLs.** The *Artifact availability* section has placeholder URLs
      for Grove, Prism, and the harness. Insert the real repo URLs and, ideally, a
      frozen release tag or a Zenodo DOI for reproducibility.
- [ ] **Verify every citation.** The `thebibliography` entries are best-effort
      from memory and **must be checked** (author lists, years, venues, arXiv IDs)
      against the real papers before submission. A wrong citation is worse than a
      missing one.
- [ ] **Model names.** The paper denotes the three tiers as Small / Mid / Frontier
      (mapped to Haiku / Sonnet / Opus in the run logs). Decide whether to name the
      exact model versions in the camera-ready (recommended for reproducibility).
- [ ] **Numbers cross-check.** All recall/cost figures trace to
      `harness/agg_jackson.py` over `harness/runs/`; regenerate and confirm the
      tables match if any runs are re-scored.

## Provenance of the numbers
Every figure in the paper is produced deterministically (no LLM in the loop) by
`harness/rescore_java.py` + `harness/agg_jackson.py` over the committed run logs.
`THESIS.md` holds the falsifiable sub-claims (C1–C7) and their verdicts.
