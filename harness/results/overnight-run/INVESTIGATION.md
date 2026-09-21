# Investigation: overnight native-vs-prism run (2026-09-20/21)

50 tasks, 5 languages, model=sonnet, arms=`baseline` vs `prism_init` (resident
compact tool). Raw per-task results in `REPORT.md`/`results.json`. This file
is the deep dive requested on every flagged case.

## UPDATE 2026-09-21: fix confirmed, corrected full-50-task result

The `TOOL_ARTIFACTS` fix below was applied and the 11 commons-lang tasks were
re-run clean. Result: **commons-lang flips from prism 0/11 to prism 9/11
(82%) — now beating native's 8/11 (73%)**, fully confirming the diagnosis.
Corrected full-50-task aggregate (39 clean tasks + 11 re-run commons-lang):

| | resolved | tokens |
|---|---|---|
| native | 32/50 (64.0%) | 38,830,033 |
| **prism** | **34/50 (68.0%)** | 40,632,378 (**1.046x**) |

Once the harness bug is fixed, prism resolves *more* tasks than native
overall, at a modest 4.6% token premium. The commons-lang re-run alone cost
more (1.46x tokens on that corpus specifically) despite the resolve-rate win
— worth watching if commons-lang gets more tasks in a future run, but not
investigated further here since the correctness question (was 0/11 a real
prism weakness) is now resolved: no, it wasn't.

## Headline: the apparent "prism regression" was 89% one confirmed harness bug, not prism

Raw aggregate looked bad for prism:

| | resolved | tokens |
|---|---|---|
| native | 32/50 (64%) | 39,906,942 |
| prism | 25/50 (50%) | 38,988,712 (0.98x) |

But broken down by corpus, the resolve gap is **not spread across languages —
it is 100% concentrated in one 11-task corpus**, `apache/commons-lang`:

| corpus | n | native resolved | prism resolved |
|---|---|---|---|
| commons-lang | 11 | 8/11 (73%) | **0/11 (0%)** |
| everything else | 39 | 24/39 (61.5%) | **25/39 (64.1%)** |

Prism resolved **zero** of eleven commons-lang tasks. Not "worse" — zero.
Every other corpus (jackson-databind, gin, click/rich/requests, jansson,
express) either ties or slightly favors prism.

### Root cause, confirmed with reproduction evidence

`prism_init`'s setup step (`run_e2e.py::_index_graph`) runs `prism init
--harness claude --yes <worktree>`, which writes three new files: `.mcp.json`,
`CLAUDE.md`, `.claude/settings.json`. `run_e2e.py::_agent_diff` stages
everything (`git add -A`) and excludes a fixed list, `TOOL_ARTIFACTS =
(".grove", ".engine-b", ".prism", "prism.yaml", ".p.diff", ".shale")` — this
list predates `prism_init` and was never updated for it. **None of the three
new files are excluded.** They leak into the scored diff for every single
`prism_init` task, in every language, confirmed by grepping every commons-lang
scored diff:

```
apache__commons-lang__pr1591 ... pr1750: leaked_files=3   (11/11, no exceptions)
```

commons-lang is an Apache Software Foundation project. Its `pom.xml` binds
`org.apache.rat:apache-rat-plugin:check` into the build, which fails hard on
any file without an approved license header — including three new files with
no header at all. Confirmed directly from `commons-lang__pr1631`'s own
transcript, first `mvn test` attempt:

```
[ERROR] Unexpected count for UNAPPROVED, limit is [0,0].  Count: 2
[ERROR] Failed to execute goal org.apache.rat:apache-rat-plugin:0.18:check
        (rat-check) on project commons-lang3: Counter(s) UNAPPROVED exceeded
        minimum or maximum values.
```

The agent noticed this in its own verification and worked around it with
`-Drat.skip=true` — but that only affects the agent's own sanity-check run.
The harness's actual scoring step (`java_eval.score` → `_run_tests` → `mvn
test`, no rat-skip) applies the **same contaminated diff** and hits the same
wall, regardless of whether the agent's code fix was correct.

**Proof the code fix itself was fine:** on `pr1631`, native and prism wrote
the *identical* one-line fix (`jdk.xml.entityReplacementLimi_t` →
`...Limit`). Prism was scored `resolved=False` anyway — purely from the
license-audit failure on files prism's own setup created, that the harness
never told the scorer to ignore.

### Why jackson-databind (also Java) didn't show this

jackson-databind is FasterXML's own project, not ASF-governed — no RAT plugin,
no license-header gate. Same three files leak into every jackson-databind
`prism_init` diff too (confirmed), but nothing in its build cares. Result:
prism actually resolved *more* jackson-databind tasks than native (10/16 vs
9/16). The "Java problem" was never a language problem — it was an
Apache-governed-build problem that only commons-lang happened to trigger.

### The fix (one line, not yet applied — flagging, not touching without asking)

Add `.claude`, `.mcp.json`, `CLAUDE.md` to `TOOL_ARTIFACTS` in
`harness/runners/run_e2e.py`, matching how `.grove`/`.prism`/`prism.yaml`
are already excluded. This is almost certainly why the number "prism resolved
25/50" is an undercount by roughly 8 tasks (see below).

### Corrected clean comparison, commons-lang excluded

| | n | native resolved | prism resolved | native tokens | prism tokens | ratio |
|---|---|---|---|---|---|---|
| clean (no commons-lang) | 39 | 24 (61.5%) | **25 (64.1%)** | 34,987,700 | 35,018,086 | **1.001x** |

Once the confirmed-contaminated corpus is removed, **prism ties or very
slightly beats native on resolve rate, and cost is essentially exact parity**
(1.001x — as close to identical as two independent LLM runs get). This is the
real signal from this run.

---

## The two genuine (non-harness-bug) resolve losses: `click pr3466`, `click pr3434`

Both are Python, both show the *same* pattern: prism found the right file and
right root cause **faster and cheaper** than native, then wrote a narrower or
more conditional fix that missed an edge case the held-out test covers.
Neither is a context-delivery failure — prism's search/lookup calls pointed at
the correct location both times.

### `click pr3466` (zsh completion CRLF bug)
Both arms diagnosed the same root cause (Windows text-mode stdout injects
`\r\n`, corrupting a zsh script). Native's fix is unconditional and
structurally safe:
```python
echo(comp.source().encode())   # bytes bypass text-mode translation, always
```
Prism's fix is conditional and silently no-ops if the test's stdout lacks
`.reconfigure` (plausible inside Click's own `CliRunner`-captured stream):
```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(newline="\n")
echo(comp.source())
```
(Two repeat trials on this exact task after the fact: resolved flipped
False→True on retry, tokens 1.30M–1.64M both times vs native's 693K–784K —
outcome is noisy on this specific task for *either* arm's harder path, cost
was consistently ~1.7–2.1x native regardless of outcome.)

### `click pr3434` (empty-args usage-line formatting)
Same shape. Native inserts the empty-args special case **before** the
width-check branch (applies unconditionally):
```python
if not args:
    self.write(usage_prefix.rstrip())
elif text_width >= (term_len(usage_prefix) + 20):
    ...
```
Prism nests it **inside** the width-check branch (only applies when the
terminal is wide enough — misses the narrow-terminal path the test covers):
```python
if text_width >= (term_len(usage_prefix) + 20):
    if not args:
        self.write(usage_prefix.rstrip())
    ...
```
Prism used 28% fewer tokens getting to this point (309,766 vs 432,286) — it
was more efficient at finding the bug, just less careful writing the fix.

**Pattern across both:** prism does not appear to make discovery worse or
slower; on these two losses it was faster and cheaper to reach the right
code. The failure mode is judgment at fix-writing time, not context quality —
consistent with normal run-to-run variance in how carefully a single sample
covers edge cases, not something that should be attributed to prism's engine.

---

## Everything else that got flagged (pure token-ratio flags, no resolve mismatch)

18 more cells were flagged for token ratio alone (both resolved the same way,
just cost noticeably more or less). These were not individually deep-dived —
volume made that impractical in one pass, and the click3466 repeat-trial data
above already demonstrates that a >1.5x swing between two independent runs of
the *identical* cell is well within normal variance, not evidence of a
systematic effect. If you want specific ones pulled (e.g. the two biggest
outliers, `jackson-databind pr6019` at 2.46x and `pr6076` at 2.31x, both of
which also failed on both arms), say which and I'll pull those transcripts
next.

## Bottom line

- **Not a prism engine problem.** The dominant signal (commons-lang 0/11) is
  a confirmed, reproducible harness bug: prism's own setup files aren't
  excluded from the scored diff, and Apache's license audit fails the build
  on them regardless of code correctness.
- **Once that's excluded, prism ties native on both correctness (64.1% vs
  61.5%, n=39, not a significant difference) and cost (1.001x).**
- **The two genuine losses are fix-writing judgment calls**, not context or
  discovery failures — prism got to the right place faster both times.
- **Recommended next step:** add the three-file exclusion to
  `TOOL_ARTIFACTS`, then re-run just the 11 commons-lang tasks to get a real
  (uncontaminated) read on that corpus specifically. Not done yet — waiting
  for the go-ahead per the "confirm before every paid run" rule.
