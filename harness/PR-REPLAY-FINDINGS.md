# Phase-1 PR-replay pilot — findings (Netty, outcome-blind)

**Goal:** prove the engine's change-set matches what real engineers merged, on
real (non-benchmark) PRs, no LLM, no hand-built oracle. Fresh project: netty/netty.

## What the pilot established

1. **The harness plumbing works end-to-end** (`pr_replay.py`): mine merged PRs
   → mechanically classify → index the before-state in an isolated worktree →
   run `change-impact` → score vs the merged human diff → aggregate. Reusable
   for any GitHub project.

2. **The engine is NOT the bottleneck. Valid-task identification is.** Every low
   score traced to the *harness*, not grove — exactly the "sampling discipline
   matters more than the project" thesis, confirmed empirically:
   - v1: `method_name()` matched qualified CALLS (`x.foo(a,b)`) as declarations,
     so feature PRs that changed call ARGUMENTS were misflagged as signature
     changes. Fixed (reject `.name(` and require a return-type/modifier token).
   - v2: still flagged aggregate "Merge branches from forks" PRs and feature PRs
     whose signature change is incidental — their GT is polluted with feature
     work (new class/tests/threaded params) that is not the target's mechanical
     blast radius. Added merge-PR and feature-dominated (net-new-method) gates.
   - v3: gates over-corrected to ~1.7% yield. The middle is hard to hit
     mechanically.

3. **Clean, BREAKING signature-change refactors are RARE in real history**
   (low single-digit % base rate). Most "signature-ish" PRs are: additive
   overloads (new param with old kept → NO forced callers, not a change-impact
   task at all — e.g. netty#16850 adds a `ZstdDecoder(int,int)` overload),
   features that thread a param incidentally, or aggregate merges. The rare
   genuine breaking refactors need confirmation that the merged diff IS the
   target's blast radius.

## Honest conclusion

Fully-automatic, outcome-blind mining of *clean* change-impact tasks from real
PR history is a genuine research-grade problem — too-loose classification
pollutes ground truth (artificially low scores), too-strict yields almost
nothing. This is why the paper's tasks were HUMAN-VERIFIED at N~14. **No recall
number from this pilot is citable** — the clean-task set isn't clean yet.

## The path that actually proves real-life value

- **Compiler-as-oracle (generalize Mode B), not diff-as-oracle.** On the rare
  verified breaking refactors, apply the agent's change-set and compile — the
  build is a clean oracle that doesn't depend on the merged diff being the exact
  blast radius. This sidesteps the GT-pollution problem entirely.
- **Mechanical pre-filter (this harness) + a verification pass** — human
  spot-check (as the paper did) or a cheap LLM-judge confirming "clean breaking
  refactor, merged diff == target blast radius" — then score only the confirmed.
- **A live pipeline (Shale) is the strongest real-life proof:** the tasks are
  whatever real work flows through, and the oracle is compile/tests/reviewer
  acceptance — no task mining, no synthetic GT, disinterested judges.

`pr_replay.py` is the reusable pre-filter for any of these; what it proved is
that the pre-filter alone is not enough, and where the real work is.
