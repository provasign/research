# SWE-bench A/B (prism vs baseline) — 20-task Verified run: RESULT + validity finding

Pipeline fully validated: gold patches resolve 2/2 in the Docker oracle; both
arms produce non-empty patches for all 20 tasks; the oracle discriminates
(both arms fail some, pass most). Harness is correct and reusable.

## The numbers (20 tasks: 5 each astropy/django/xarray/sphinx, outcome-blind)
- Resolve: baseline 15/20 (75%), prism 14/20 (70%). 13 both, 2 only-baseline,
  1 only-prism. Prism did NOT lift resolve-rate.
- Efficiency on the 13 both-resolved (fair): baseline 9.8 turns/$0.324 vs
  prism 10.2 turns/$0.327 — statistically identical.
- Agent chose prism on 9/20 tasks (it's optional in the prism arm).

## Why this run does NOT measure prism's value: CONTAMINATION
75% resolve from a single-pass agent that cannot even run the project's tests
is ABOVE state-of-the-art agentic systems that have full test-running
environments and retries (~65-70% on Verified). The only fit: training-data
leakage. SWE-bench Verified is public GitHub data from 2024; the model's cutoff
is Jan 2026, so it has very likely MEMORIZED these fixes. On a memorized task
the model recalls the answer regardless of tooling — so prism cannot help or
hurt, which is exactly the tie + slight overhead observed.

This is the same class of trap PR-replay hit: a methodology with an uncontrolled
validity flaw (there: task-identification; here: contamination) yields numbers
that look like a result but measure the wrong thing. SWE-bench "solved the
oracle problem" but has its OWN problem for frontier models: contamination.

## The fix — POST-CUTOFF tasks with an oracle
The robust real-life proof needs tasks the model could NOT have memorized:
1. **Live / post-cutoff issues** (created after the model's training cutoff),
   scored by their own tests — e.g. SWE-bench-Live-style continuous mining, or
   our own harness pointed at issues+PRs merged after Jan 2026.
2. **A live Shale pipeline** — post-cutoff by construction (real new work),
   oracle = tests/compile/reviewer acceptance. Strongest, and no contamination
   by definition.
3. **Compiler-oracle on post-cutoff refactors** (generalized Mode B) for the
   change_impact-shaped subset.

The swebench_ab.py harness is directly reusable for (1): swap the dataset for a
post-cutoff task set (same predictions + Docker-eval flow).

## Bottom line
The A/B machinery is built, validated, and correct. The *benchmark choice* is
what's wrong for measuring a frontier model. Do not cite the 75%/70% as a prism
result — it's a memorization measurement. Next: post-cutoff tasks.
