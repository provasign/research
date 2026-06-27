# Graph-vs-Grep study — Handoff

> **CURRENT STATE (2026-06-27) — read this first; the 2026-06-20 sections below
> are historical.**
>
> **The result changed from negative to a bounded positive.** The Go study's
> "graphs don't help" was an artifact of small, name-greppable tasks. Extending to
> **jackson-databind** (Java framework) with a **size-graded task set** (8→108
> change-sites) and a **precise Spoon type-resolution oracle** found the boundary:
>
> - **Small/greppable tasks (≤22 sites): graph ≈ text** (ties — even on the most
>   name-ambiguous targets). The Go null holds here.
> - **Large tasks (~100 sites): graph WINS** — recall +0.13–0.24 AND collapsed
>   variance (Sonnet `serialize`: T 0.865 swinging to 0.73 vs G **0.996 ± ~0**),
>   at near-equal cost (G/T ≈ 1.04). **Robust across Haiku and Sonnet.**
> - **Discriminator = blast radius (#sites), NOT name ambiguity or language.**
>
> Full write-up: `paper.md` (retitled, bounded-positive). Sub-claims+verdicts:
> `THESIS.md`. Java infra + reproduction: `harness/java-oracle/README.md`.
>
> **Infrastructure built (this is the reusable asset):**
> - `harness/java-oracle/` — Spoon change-impact oracle (`Oracle.java`,
>   `--target` for tasks, `--index` for line→method map), `make_java_task.py`
>   task generator, `run_jackson_pilot.sh`. JDK 26 via `env.sh`. Build:
>   `mvn -DskipTests package`. Corpus: `~/gvg-corpus/jackson-databind` @ 2.18.8.
> - `harness/rescore_java.py` — **MANDATORY** for Java runs: prism speaks
>   `file:line`, so graph-arm agents answer in line numbers; this normalizes them
>   to enclosing methods before scoring (else the graph arm is scored ~0). ALWAYS
>   run it before aggregating Java results.
> - `harness/agg_jackson.py` — recall + tokens + USD + running bill, per
>   task×model×arm.
> - `harness/arms.py` — prompt is now language-aware (was hardcoded "Go
>   repository"; Go fill is byte-identical, so the 45 Go runs stay valid).
>
> **In progress / next:**
> 1. Sonnet grid finishing (6 tasks; large ones done, mid/small running). Then
>    rescore_java + agg_jackson for the full size curve. Bill ~$59 at 57 runs;
>    full sonnet grid ~$140; each large sonnet run ~$2–3.
> 2. **Opus** frontier tier — deferred (≈5× sonnet cost); decide after sonnet.
> 3. Haiku is missing the two mid-size tasks (38/58) — run for a complete haiku
>    curve.
> 4. Replicate large-task regime on a 2nd framework + a large Go codebase with
>    wide interfaces (proves the lever is size, not "Java").
> 5. Mode B (compile/fail-to-pass): does the reliability gain convert to success?
> 6. The 3 untracked `commons-*` tasks (isTrue/join/length) are INVALID
>    (bare-name GT pollution + static methods) — delete; do not use. `appenddetail`
>    is at best a greppable control.
>
> **Watch:** arm-purity violations (G arm sometimes skips prism — `run.py` flags
> `violation`, excluded in aggregation). `caffeinate` does NOT survive lid-close;
> use `sudo pmset -a disablesleep 1` for long unattended grids.

---

## Historical handoff (2026-06-20) — the Go pilot, pre-Java

Self-contained resume point for the (then-negative) paper. Pilot data collection
was done and integrity-checked; superseded by the Java extension above.

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
  - **Adversarial tasks: use the PR-derived path, NOT oracle bare-name.**
    *Lesson, 2026-06-21:* `oracle_task.py --target <bareName>` cannot isolate one
    interface — a bare method name (`CheckHealth`, `Set`, `Validate`, `Get`) is
    shared by *unrelated* interfaces, so the GT conflates them (checkhealth pulled
    in the gRPC `HealthServer`, storage, advisor → spurious recall<1 + false
    over-confidence on ALL arms; fixed only by `--exclude`). A real merged PR that
    changes one interface method's signature scopes cleanly to that interface and
    is human-validated — that's how the 3 working adversarials (122750/126004/
    120119) were built. Use `extract_task.py` on interface-signature-change PRs;
    use the VTA oracle to *audit* GT completeness, not to *define* it by name.
  - **Findability, not impl fan-out, is the discriminator.** Ranking targets by
    implementation count repeats the gin-render mistake: uniformly-named handlers
    in dedicated packages (the datasource `QueryData`/`CheckHealth`/`CallResource`
    tasks) are *greppable* — recall=1.0 for every arm/model → **negative controls,
    not adversarial.** The effect needs *name ambiguity* (grep over-matches) +
    *sites buried in large files* (the 122750 `Set`×49 case).
  - **Status of the 3 new oracle tasks (2026-06-21):** `grafana-querydata/
    checkhealth/callresource-impact` are KEPT as **documented greppable controls**
    (checkhealth/callresource recall=1.0 all arms; querydata ~0.90, graph no help).
    `candidate_targets.py` is still useful but rank by ambiguity (distinct receiver
    types per bare name), and every candidate needs source validation before use.
  - The 4 excluded tasks (`*-isenabled`, `*-routeregister-get`, `*-securevalue-get`,
    `*-session-delete`) remain mis-specified concrete-caller (VTA-only) — do not
    revive.
  - 5 trials × 3 models (Haiku/Sonnet/Opus) per task; run via `~/gvg-gapfill.sh`
    (now inherits usage-cap pause). Corpus stays in `~/gvg-corpus` (never /tmp).
    **Always audit GT cleanliness before launching** (rescore saved answers / check
    cross-interface pollution) — re-running is the expensive way to find a bad task.

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
