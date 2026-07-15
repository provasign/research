# HANDOFF — end-to-end agentic benchmark (does a code graph help a coding agent fix real bugs?)

Working handoff for continuing this benchmark in a fresh session. Point the new
session here. Everything below is committed in `provasign/research`.

---

## The question

For the work a *regular* coding agent does — real, localized bug fixes — does a
code graph help, and is it **Prism (G/G\*)** or **CodeGraph**? Measured
end-to-end: the agent edits a throwaway worktree, and the repo's own test suite
scores it in Docker (`FAIL_TO_PASS` passes, no `PASS_TO_PASS` regression). Tasks
are **post-cutoff 2026 PRs** (contamination-free) with **issue-text prompts** (no
solution leak).

Arms (tool exposure is the ONLY thing that varies):
- **baseline (T)** — grep/read/edit. The control.
- **prism_g** — Prism primitives (search/lookup/references).
- **prism_gstar** — Prism task altitude (`prism_query` first; change_impact etc. only on task shape).
- **codegraph** — CodeGraph `explore`.
- **mason** — local-only: the 30B through Mason (competent harness), Prism baked in.
- **`<arm>_nogrep`** — forced-graph variant: grep stripped so discovery MUST go through the graph.

---

## CURRENT STATE / KEY FINDINGS (2026-07-14, evening — MAJOR CORRECTION)

### 0. SCORING ARTIFACT invalidated every earlier Prism number (FIXED)
`prism index`/`prism mcp` drop `.grove/*.db` (binary) into the worktree;
`_agent_diff` swept them into the agent patch via `git add -A`; `git apply` is
ATOMIC, so the binary stubs made the WHOLE patch unappliable and every
prism-arm cell scored resolved=False regardless of fix quality. CodeGraph was
unaffected (index lives outside the worktree) — the entire "CodeGraph 2/5 vs
Prism 0/5" story was this bug.
- Fix: `TOOL_ARTIFACTS` excludes in `run_e2e._agent_diff` (+ diffs are now
  persisted per cell as `runs/e2e/<cell>.diff`).
- `rescore_polluted.py` stripped artifacts from 26 persisted diffs and
  rescored in Docker: 8 cells FLIPPED to resolved.
- The 4 old diff-less pr3493 g/gstar_nogrep probes were re-run: ALL 4 resolve.
- STILL INVALID (no diffs to rescore): the v1 with-grep pilot prism_g /
  prism_gstar / mason / local cells. Ignore those columns until re-run.

### 1. Source delivery MERGED into prism_query (Prism v0.25-dev, uncommitted)
prism_explore existed briefly, then was merged into prism_query by user
decision (no separate CodeGraph-shaped tool). prism_query now has
delivery="source"|"symbols": source = verbatim line-numbered windows (merged
spans, gap markers) + per-anchor callers/covering-tests summary + edit-ready
steering; symbols = the classic compact list. Default is PHASE-AWARE
(DetectPhase: debug/implement -> source; explore/review/unknown -> symbols);
explicit arg wins. Session sha-pointers on repeat full-file delivery;
edge-verified tests only in source windows. CLI: `prism query --delivery
source|symbols --max-files N`. 15 MCP tools again; steering templates rewritten
query-first; full suite green. The benchmark's gstar arm therefore measures the
new delivery automatically (bench prompts are debug-phase).

Historical: standalone prism_explore_nogrep cells (2/5 haiku, 1/5 sonnet) and
pre-merge prism_gstar_nogrep cells (3/5 haiku, 2/5 sonnet, symbols delivery)
are archived in runs/e2e-archive-pre-merge/. Note symbols delivery outscored
source delivery at n=1 trial — the 3-trial run decides.

### 2. Clean forced-graph grid (1 trial/cell, CORRECTED scoring; gstar/explore
### cells now archived pending the uniform v0.25 3-trial re-run)
| model | baseline | prism_g_ng | prism_gstar_ng* | prism_explore_ng* | codegraph_ng |
|---|---|---|---|---|---|
| haiku  | 0/5 | 2/5 | **3/5** | 2/5 | 2/5 |
| sonnet | 0/5 | 2/5 | 2/5 | 1/5 | 2/5 |
(* archived arms: gstar measured v0.24 symbols delivery, explore the standalone tool)

- Every graph arm beats baseline (0/5). "Does a code graph help?" -> yes on
  this pilot, for BOTH graphs.
- pr3493: ALL prism arms + codegraph resolve it, both models.
- pr3504: only prism_gstar/haiku resolves (codegraph fails it everywhere).
- pr3534: everything except sonnet+explore resolves. Autopsy: explore steered
  sonnet to flush in MaybeStripAnsi.write (_termui_impl.py, one layer deep);
  gstar fixed at the gold site (echo_via_pager loop). Ranking nuance, n=1.
- pr3653 / pr3678: unresolved by every arm so far.

### 2b. pr3504 is a MISMATCHED task, not a graph-capability signal
Every arm (baseline/CodeGraph/Prism, with or without grep) converges toward
0-line diffs on pr3504 across trials -- not because agents can't find the
code, but because the task's problem_statement describes the WRONG fix:
- Issue text says "escape newline characters in help text" + "added test
  `test_fish_multiline_help_complete`".
- The actual gold patch is a wire-FORMAT redesign: the fish completion
  delimiter changes from newline-separated (`plain\na\n_\n`) to
  comma-separated (`plain,a\n`), the embedded fish shell script is rewritten
  to match, and the "_" no-help sentinel is removed.
- test_patch DELETES test_fish_multiline_help_complete (the test the issue
  text claims was added) -- the real FAIL_TO_PASS oracle is 3 pre-existing
  parametrized cases whose expected strings were swapped to the new format.
No context tool can discover "redesign this wire format" from "escape
newlines" -- that's a task-mining defect (build_task.py's issue-text
problem_statement underdescribes this particular PR's actual diff), not a
baseline-vs-graph finding. RECOMMEND: exclude pr3504 from headline resolve
rates, or footnote it explicitly. Worth an audit pass over other mined tasks
for the same issue-text/gold-patch mismatch pattern.

### 2c. pr3653 is ALSO mismatched (confirmed via `gh pr view`) -- SYSTEMATIC miner bug
Root cause found, not speculative. Real GitHub PR bodies:
- PR #3653 (this task's own diff/tests): title "Strip ANSI from `confirm()`
  and `prompt()`", body "This is a regression introduced by #2969 in Click
  8.4.0. This PR closes #3572."
- PR #2969 (a DIFFERENT, earlier PR, merely referenced inside #3653's body):
  title "Fix readline backspace/line-wrapping on linux", body "...fixes
  #2968...".
- The task's `problem_statement` is PR #2969's body, VERBATIM -- not #3653's.
The miner followed the cross-reference (#3653 mentions #2969 as the PR that
caused the regression it fixes) and attached #2969's issue text to #3653's
diff/tests instead of #3653's own body. Agents are told to fix backspace/
line-wrapping; the oracle actually checks ANSI-stripping in prompt/confirm --
unrelated code. Explains the clean 0/12 sweep across every arm.

pr3678 CHECKED CLEAN by contrast: `gh pr view 3678` and `gh issue view 2819`
both match the task's problem_statement and CHANGES.md citation
(`{issue}2819 {pr}3678`) exactly -- legitimately mined, just a hard localized
fix (parameter-name-collision warnings across core.py). Its 0/16-so-far looks
like real difficulty, not contamination.

**2 of 5 pilot tasks (pr3504, pr3653) are now confirmed miner defects, same
root cause pattern: wrong linked issue/PR text attached to the graded diff.**
This is systematic, not a pilot-set fluke -- likely `mine_2026_tasks.py` or
`build_task.py` walks a cross-referenced issue/PR instead of the mined PR's
own body/linked-issue when the PR text mentions another PR number (e.g. "regression
introduced by #N", "see #N"). FIX BEFORE SCALING to django or any larger set:
audit/patch the issue-text extraction to prefer "fixes #N"/"closes #N" from
the PR's OWN body over any other PR/issue number mentioned in prose, and
verify against `gh pr view <pr>` for every mined task before use.

**Recommend: drop pr3504 and pr3653 from headline resolve rates entirely**
(2 of 5 tasks = 40% of the pilot set contaminated). The valid comparison set
is now pr3493, pr3534 (both discriminate the arms) and pr3678 (currently 0/N
everywhere, real difficulty, still informative).

### 3. Still true
- n=5 tasks, 1 trial/cell -> directional only. Run --trials 3 (flag now
  exists; t1 keeps unsuffixed names, cache-compatible) before any headline.

## DECISION 2026-07-14 late: source delivery KEPT; mason integrated

3-trial grid COMPLETE. Trusted tasks only (pr3493/pr3534/pr3678; the two
contaminated tasks excluded): baseline 7/18 (39%), codegraph_nogrep 11/18,
prism_g_nogrep 11/18, **prism_gstar_nogrep 12/18 (67%, best arm)**. Graph
clearly beats grep-baseline at n=3 trials on both models. Source delivery
cost zero wins anywhere and cut turns ~30-40% on the hard task (pr3678:
71 -> 42/44/60 turns). Decision (user): KEEP the delivery, with steering.

Mason integration (uncommitted, mason repo):
- formatCodeContext handles the source-delivery response (pre-rendered
  "content" passes through; symbols list unchanged).
- code_context tool description + system prompt teach the discipline:
  windows ARE reads (never read_file the same files again), and "prefer
  fixing at the anchor the failing behavior names, not a deeper helper
  that merely looks related" (encodes the one measured failure mode:
  sonnet/pr3534 fixed MaybeStripAnsi.write instead of echo_via_pager).
- mason suite green; ~/bin/mason rebuilt (local prism via go.work).
- Live probe running: pr3493 x mason x qwen3-coder:30b with the new
  delivery -> runs/e2e/pallets__click__pr3493.local.mason.probe-v025.json
  (pilot mason was 0/5, all 10-min timeouts; windows may fix that).

## LOCAL-MODEL BREAKTHROUGH 2026-07-14 night: first mason/local resolve

Three-probe arc on pr3493 x mason x qwen3-coder:30b (pilot was 0/5, all
10-min timeouts):
1. symbols delivery: right area, restructured the branch, p2p regression. 0/1.
2. source delivery (forced via mutationIntent): wrote the EXACT gold
   one-liner on its FIRST edit (line number cited from the windows) — then
   verified from /tmp + /myproject (paths outside the worktree / copied from
   the issue traceback), imports missed the repo, concluded the fix was
   broken, rewrote it into an over-engineered version, timed out. 0/1.
3. source delivery + verification-hygiene steering (system prompt: verify
   from repo root with repo code on the import path; trust the REPORTED case
   + project tests over self-invented cases; delete scratch files):
   **resolved=True** — gold one-line fix, f2p_ok, p2p_ok. Hit the 600s cap
   during cleanup (leftover test_fix.py scratch file, harmless).

Chain validated end-to-end: graph + edit-ready source delivery + discipline
steering lets a local 30B fix a real post-cutoff bug the pilot said it
couldn't. n=1 — worth a 5-task mason re-run for the paper.

Mason changes (uncommitted): delivery forced from USER task intent
(mutationIntent), not the model's sub-phrasing (measured: 30B phrases
context calls as "analyze/understand" -> explore phase -> wrong delivery);
verification-hygiene + scratch-cleanup working-style rules; harness
TOOL_ARTIFACTS += .shale.

## IMMEDIATE NEXT STEP

1. **3-trial grid is RUNNING** (launched 2026-07-14 evening):
   `run_e2e.py ... --arms baseline,codegraph_nogrep,prism_g_nogrep,prism_gstar_nogrep --trials 3`
   gstar t1 runs fresh on merged v0.25 delivery. Then `python3 aggregate_e2e.py`.
2. **Re-run the invalidated v1 with-grep pilot prism cells** (delete their
   runs/e2e jsons first) if the with-grep comparison still matters.
3. Commit prism (query source delivery) + research (harness fixes, rescore,
   arms, results).

## MINER FIXED 2026-07-14 night (post-release)

build_task.problem_statement rewritten: (1) GitHub's authoritative
closingIssuesReferences first; (2) only keyword-linked "fixes/closes #N"
numbers from the PR text, never bare cross-references; (3) every candidate
verified to be a real issue via the pull_request marker in the issues API —
`gh issue view <pr-number>` SUCCEEDS on PRs (GitHub models PRs as issues),
which was the root cause.

Audit of the 5 pilot tasks with the fixed extractor:
- pr3493, pr3678: unchanged (were correct).
- pr3653: now carries real issue #3572 (ANSI codes not stripped from
  click.confirm) — matches the gold patch. VALID going forward.
- pr3504: now carries real issue #3043 (multi-line help broken in fish) —
  symptom-level, so the wire-format-redesign gold patch is now fairly
  reachable. VALID going forward.
- pr3534: NEW finding — the old statement was the PR title, "Flush stdin
  after writing to a pager", i.e. a SOLUTION LEAK. Corrected to the real
  issue's symptom text. The published 3-trial grid ran pr3534 with the
  leaked statement — the leak hit every arm identically, so the ARM
  comparison stands, but absolute resolve rates on pr3534 are inflated.
  Task files carry a statement_note marking pre-fix cells.

Consequence for the next run: all 5 tasks are now clean; re-running the
grid on corrected statements is the paper-grade version (expect pr3534 to
get harder for everyone, pr3504/pr3653 to become winnable).

## FILE MAP (all in research/harness/)

| file | role |
|---|---|
| `mine_2026_tasks.py <repo> --scan N` | find post-cutoff 2026 PR candidates (bug/feature, source+test churn) |
| `build_task.py <repo> <pr>` | PR → SWE-bench task (base, gold, test_patch, **issue-text** problem_statement) |
| `docker_eval.py <task.json>` | validate (derive FAIL_TO_PASS) / `--score <diff>` (score an agent diff) in Docker |
| `build_pilot_set.py <repo> --scan N --max K` | mine→build→validate a repo's tasks → `manifest.<repo>.json` |
| `ab_endtoend_arms.py` | the arm definitions (allowlists + steering); `_nogrep` variants built here |
| `run_e2e.py <manifest> --models .. --arms ..` | cell runner (cloud via claude -p, local via run_local_agent, mason). Cell-cached/resumable. `E2E_WAIT_ON_LIMIT=1` sleeps+retries on rate-limit |
| `run_local_agent.py` | neutral local ReAct loop over ollama; `_nogrep` arm support; saves tool trace |
| `aggregate_e2e.py` | reads runs/e2e/*.json → RESULTS-E2E.md (resolve-rate grid) |
| `run_overnight.sh` | sequential orchestrator (mason→haiku→sonnet→local), aggregates each stage |
| `BENCHMARK-ENDTOEND-DESIGN.md` | the design rationale + honest expected-result framing |
| `tasks-e2e/*.json` | validated tasks (have `fail_to_pass`); `manifest.pilot.json` = the 5 click tasks |
| `runs/e2e/*.json` | scored cells: `<task>.<model>.<arm>.json` (+ `*.mason.transcript.txt`) |
| `../RESULTS-E2E.md` | the narrative results write-up |

## PILOT TASK SET (5 validated click 2026 bugs)
`manifest.pilot.json`: pr3493 (empty-bytes echo TypeError), pr3504 (fish
completion multiline help), pr3534 (pager stdin flush), pr3653 (readline
backspace/wrap), pr3678 (help param resolution). Each has a discriminating
FAIL_TO_PASS. click is the pilot repo (pure-Python, pytest, fast). django was
mined too (21 candidates) as the next SCALE repo.

---

## ENVIRONMENT / PREREQUISITES (verify at session start)

- **Docker daemon MUST be running** (`docker ps`). It's a GUI app: `open -a Docker`, wait ~10s. Needed for validate + score only.
- **ollama** up with `qwen3-coder:30b` (`curl -s localhost:11434/api/tags`) — for mason/local arms. Local model does native OpenAI tool-calling via `/v1`.
- **CLIs on PATH**: `prism` (~/bin/prism), `codegraph` (~/.local/bin/codegraph, v1.4.1), `claude` (2.1.x), `gh` (authed as tabladrum).
- **No ANTHROPIC_API_KEY** → Sonnet/Haiku run via `claude -p` (subscription). Cloud arms therefore can hit the subscription rate limit; `E2E_WAIT_ON_LIMIT=1` handles it (sleep 20min + retry).
- Corpora clone under `~/gvg-corpus/e2e-2026/` (blobless clones).

---

## KNOWN CAVEATS / GOTCHAS

- **n=5 pilot, 1 trial/cell** — everything so far is directional, not significant. Add trials before any headline.
- **mason-local 0/5 = timeouts**, not incapability — all hit the 10-min wall-clock cap (`_run_mason` in run_e2e), bloated diffs. Bump cap or accept as budget-bounded.
- **local neutral loop is weak** (paper-predicted) and its stage crashed once on a tool-arg bug — NOW FIXED (base tools + ctx lambdas default their args).
- **Fairness rule**: compare like-with-like. codegraph WITH grep vs prism WITHOUT grep is NOT fair (that mistake was caught). Use `_nogrep` for ALL graph arms, keep grep only for baseline.
- **CodeGraph > Prism on pr3493 is about localized context-delivery**, CodeGraph's stated strength — not Prism's change-impact thesis. Frame honestly; don't over-generalize from n=1.
- Cell files are the cache: to re-run a cell, delete its `runs/e2e/<task>.<model>.<arm>.json`.

## RECENT COMMITS (git log, provasign/research)
forced-graph nogrep arms; pilot results + grep confound; Docker verifier;
cell runner; task miner; issue-text problem_statement (no leak); arm steering.
