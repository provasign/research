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

## 6. Next steps (for the paper)

1. **Write Results** from §2 + PILOT.md (data is ready).
2. (Optional, camera-ready) refresh the stale/short cells in §3 for uniformity.
3. **Causal ablation (H7):** dispatch-fix ON/OFF — point `PRISM_BIN` at a
   pre-fix grove build to show graph *quality* causes the outcome.
4. **Scale** for significance: more tasks + a *valid* adversarial design
   (interface-impl-**enumeration**, not concrete-caller).
5. Token accounting (`run.py` cost uses final-turn `usage`; `total_cost_usd` is
   cumulative and fine for cost-per-outcome).

## 7. Aside: Headroom (chopratejas/headroom) audit

Tested its "60–95% fewer tokens, same answers" claim (`~/hr-venv`, notes in
chat): compression is **real but ~34–58% on realistic data** (90%+ needs their
synthetic near-duplicate generators); on the structured (SmartCrusher) path
"same answers" **held** (Claude recovered 30/30 items at 58% compression — it's
lossless structural compression). Their accuracy benchmarks are weak (keyword-
substring proxy, no-op academic prompts, no completeness test). Untested risk:
CCR (replace-with-summary + retrieve) and the Kompress ML path — lossy by design,
where "same answers" would actually break. Not part of our paper; a useful foil.
