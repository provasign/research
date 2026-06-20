# Graph-vs-Grep study — Handoff (2026-06-20)

Self-contained resume point for the paper. Repo: `provasign/research` (private).
Everything below is committed/pushed. Pilot data collection is **done and
integrity-checked**; the next phase is writing + (optionally) scaling.

---

## 1. The finding (paper thesis)

A resolved code graph's value for agentic coding is **not** token efficiency
(it ties text search there) but **completeness + calibration on change-impact
tasks**: text search is *intermittently and silently incomplete* — it misses
change sites and reports the answer as `complete` anyway — and the graph cuts
that confident-error rate ~7×. Largest for weaker/cheaper models; does not fully
vanish at the frontier. On localization / greppable tasks there is no effect
(honest negative result).

We do **not** claim "graph beats grep" broadly. The defensible, evidence-backed
claim is the completeness/calibration gap on change-impact tasks.

## 2. The proof (headline numbers)

Across the 3 completeness-critical tasks (`grafana-126004` impact,
`grafana-122750` dispatch, `grafana-120119` interface-decl) × 3 models
(Haiku/Sonnet/Opus) × 5 trials = **45 runs/arm**:

| arm | mean recall | incomplete | over-confident |
|---|---|---|---|
| **T** (text) | 0.942 | 7/45 | **7/45 (16%)** |
| **G** (graph) | 0.984 | 1/45 | **1/45 (2%)** |
| **V** (verifier) | 0.980 | 4/45 | **4/45 (9%)** |

`incomplete == over-confident` for every arm: **whenever an arm missed sites it
asserted `complete:true`.** Full per-task/per-model tables + the capability
curve + qualitative findings (interface-declaration blind spot) are in
[`harness/PILOT.md`](harness/PILOT.md) §"DEFINITIVE RESULT".

## 3. DATA INTEGRITY AUDIT (the laptop-close concern) — RESOLVED

Audited all 332 ok runs after a week of interruptions (laptop sleep, `/tmp`
cleanup, model rate limits). **Conclusion: no run was corrupted by laptop
close.** Process freezes either resume cleanly or error out (excluded from
scoring, never scored as 0). What the audit *did* find and how it was handled:

- **1 parser mis-score (fixed).** `120266/haiku/T.t5` answered correctly but the
  old brace-counter parser tripped on `{` in a prose code snippet and recorded
  an empty answer → spurious 0.0. Fixed: `schema.py` now uses `raw_decode`
  (robust). Re-parsed all 332 runs from transcripts → **exactly 1 changed**
  (0.0→1.0). It's a *localization* task outside the headline; **headline
  unchanged.**
- **Infra-errored runs are excluded, not scored 0** — verified (only 1 errored
  run remains in the kept set; rate-limit-wiped cells were backfilled).
- **Minor gaps to optionally refresh for camera-ready uniformity** (finding holds
  without them — values are consistent):
  - `grafana-124935/sonnet/G` — 4 ok trials (1 short).
  - **Stale** (pre-rebuild 06-16/17/18, ran on the old `/tmp` corpus, valid but
    not from the persistent corpus): `grafana-122750/sonnet`,
    `grafana-120119/sonnet` (both headline; consistent with the finding),
    `gin-render-impact/opus` + `/haiku` (negative control, all 1.0).
  - Refresh command (paced, won't trip rate limits):
    ```
    cd research/harness
    python3 run.py --task tasks/grafana-122750.json --arms T G V --trials 5 \
      --workdir ~/gvg-corpus/wt-122750 --model sonnet --pace 30
    # repeat for grafana-120119 (wt-120119, sonnet) and grafana-124935 (wt-124935, sonnet)
    ```

To re-verify integrity anytime: re-run the audit logic (count ok/err per cell,
flag <5 ok, 0.0 outliers, and mtimes < rebuild) — or just
`python3 reparse_all.py` (deterministic, no API).

## 4. Where everything lives

- **Harness:** `research/harness/` — `schema.py` (types+parser), `score.py`
  (Mode-A scorer, test-neutral), `run.py` (arms runner: `--model`, `--workdir`,
  `--pace`, retry+exclude, tool-trace), `arms.py` (T/G/V, enforced),
  `extract_task.py` (PR→task), `oracle_task.py` + `oracle_candidates.py`
  (go-ssa-vta tasks), `rescore.py`/`reparse_all.py` (offline re-score).
- **Tasks:** `research/harness/tasks/*.json` (committed; portable — paths come
  from `--workdir`).
- **Run data:** `research/harness/runs/<task>/[<model>/]` (gitignored; the
  source of the numbers). Aggregate with the snippets in PILOT.md.
- **Corpus (NOT in git, machine-local):** `~/gvg-corpus/` — persistent gin +
  Grafana worktrees. go-ssa-vta truth: `/tmp/grafana-truth.jsonl` (regenerate
  with `grove-eval truth --repo ~/gvg-corpus/wt-122750 --out ...` if cleaned).

## 5. Infra lessons (hard-won — read before re-running)

- **Corpus MUST be persistent** (`~/gvg-corpus`), never `/tmp` (gets cleaned;
  cost us a week of confusion). Grafana's old `/tmp` clone `.git` corrupted; the
  persistent one was re-cloned with `--filter=blob:none` + per-commit fetch.
- **Pace + caffeinate or rate limits wipe whole task×model cells.** Use
  `run.py --pace 30` and wrap in `caffeinate -dimsu`. `~/gvg-gapfill.sh` is the
  resumable self-healing runner (reruns cells with <14 ok, loops with sleeps).
- **`caffeinate` does not survive lid-close** — keep lid open/plugged, or
  `sudo pmset -a disablesleep 1`.
- **Excluded tasks:** concrete-caller oracle tasks (`secureValueClient.Get`,
  `*-isenabled`, `*-session-delete`, `*-routeregister-get`) are **mis-specified**
  — their callers reach the method via an interface (e.g. k8s `client.Get`), so
  ground truth is VTA-only and unanswerable by any structural tool (grep *or*
  graph). They'd measure "VTA vs everyone," not graph-vs-grep. Their run data is
  in `runs/` but is NOT part of the finding.

## 6. Flagship-paper campaign (the plan — target ACM TOSEM, not a workshop note)

Decision (2026-06-20): we are going for a **flagship journal paper**, which means
all four workstreams below, not just Results-from-pilot. `paper.md` already holds
the draft with §5 Results written from the pilot; everything here feeds the
camera-ready. **Infra prerequisite DONE:** `run.py` now pauses-and-resumes on the
plan usage cap (daily ~5h + weekly) and backs off on transient rate limits, so
the long unattended campaign survives both limits (see §5, `_wait_for_usage_reset`).

**Workstream order** (W1 is the long pole and gates W2; W3/W4 run in parallel once
the corpus + ablation binary exist):

- **W1 — Scale Go tasks (non-negotiable; 3 tasks won't pass review).**
  Target ~15–30 completeness-critical Go tasks. **Guardrails (hard-won, do not
  relitigate):**
  - Prefer the **compiler-grade oracle** path (`grove-eval truth` → `oracle_task.py`)
    over PR-diff for impact tasks — PR-diff *breaks on codegen* (mockery churn) and
    can't see distributed dispatch.
  - The **valid adversarial = interface-impl-ENUMERATION** (find all implementors /
    the declaring interface), **NOT concrete-caller**. The 4 excluded tasks
    (`*-isenabled`, `*-routeregister-get`, `*-securevalue-get`, `*-session-delete`)
    are mis-specified: callers reach the method via a k8s interface → VTA-only,
    unanswerable by grep *or* graph, so they'd measure "VTA vs everyone."
  - Span the taxonomy: keep localization + `gin-render` as negative controls;
    grow the impact/dispatch/interface-decl set (where the effect lives).
  - 5 trials × 3 models (Haiku/Sonnet/Opus) per task; run via `~/gvg-gapfill.sh`
    (now inherits usage-cap pause). Corpus stays in `~/gvg-corpus` (never /tmp).

- **W2 — Significance stats (needs W1's N).** Paired non-parametric per RQ
  (Wilcoxon signed-rank), Holm correction across comparisons, Cliff's δ effect
  sizes; a mixed-effects model with task/project as random effects. Add a
  `stats.py` that reads `runs/` and emits the tables + p-values. Report
  median+IQR and the **tail** metrics (min recall, over-confidence rate), not
  means.

- **W3 — H7 causal ablation (turns correlation into causation).** Build a
  **pre-dispatch-fix grove** (pre-v0.13.0, the 45-way `Get` fanout) and a Prism
  bound to it; point `PRISM_BIN` at it and re-run the headline tasks G-arm
  ON vs OFF. If recall/over-confidence move with graph precision, graph *quality*
  (not presence) drives the outcome — the rare causal claim that elevates the paper.

- **W4 — Second & third language (Go-only → multi-language).** Java =
  **Jackson-databind** (medium-accuracy graph → graceful-degradation / H5 story),
  TS = **NestJS** (second high-accuracy point). Each needs its compiler-grade
  oracle wired (javac/WALA or Soot; ts-compiler-api) and tasks curated under the
  same guardrails. Biggest *work*, do once the Go story is locked.

- **W5 — Polish (camera-ready).** Mode-B end-to-end patch subset (apply + run
  affected tests); cumulative token accounting (sum per-turn `usage`, not the
  final-turn value); refresh the stale/short cells in §3 for uniformity.

**Immediate next action:** W1 curation — survey Grafana for interface targets with
real implementor fan-out + hand-written impls (no mock churn), turn the best into
oracle tasks, expand `tasks/`. Then launch a paced+caffeinated gap-fill pass.

## 7. Aside: Headroom (chopratejas/headroom) audit

Tested its "60–95% fewer tokens, same answers" claim (`~/hr-venv`, notes in
chat): compression is **real but ~34–58% on realistic data** (90%+ needs their
synthetic near-duplicate generators); on the structured (SmartCrusher) path
"same answers" **held** (Claude recovered 30/30 items at 58% compression — it's
lossless structural compression). Their accuracy benchmarks are weak (keyword-
substring proxy, no-op academic prompts, no completeness test). Untested risk:
CCR (replace-with-summary + retrieve) and the Kompress ML path — lossy by design,
where "same answers" would actually break. Not part of our paper; a useful foil.
