# SWE-bench A/B: does prism help an agent fix real issues, at equal correctness?

The real-life proof that survives the oracle problem: real GitHub issues, the
fixing PR's own tests as the objective judge. "Equivalent fix" = clears the same
test bar (FAIL_TO_PASS flips to pass, PASS_TO_PASS stays pass), NOT textually
identical. Two arms, identical except prism availability; compare resolve-rate
(correctness) and turns/tokens/cost (efficiency).

## Status
- Harness built: `swebench_ab.py` (both arms, metrics capture, predictions out).
- Plumbing VALIDATED free: task-load -> clone@base_commit -> worktree -> prism
  index (xarray, 3877 symbols). Everything up to the agent run works.
- NOT yet run: the agentic arms (paid) and the correctness eval (needs Docker).

## Run it (when Docker is up + budget allows)
1. Fetch a repo-diverse slice:
   python swebench_ab.py --fetch 40 --tasks /tmp/swebench_slice.json
2. Run both arms (PAID — agentic, ~2x tasks):
   python swebench_ab.py --tasks /tmp/swebench_slice.json --limit 20 \
       --arms no-prism prism --out runs/swebench --prism ~/bin/prism
   -> writes runs/swebench/{no-prism,prism}.predictions.jsonl + per-task metrics.
3. Score correctness (needs Docker running):
   pip install swebench
   python -m swebench.harness.run_evaluation \
       --dataset_name princeton-nlp/SWE-bench_Verified \
       --predictions_path runs/swebench/prism.predictions.jsonl --run_id prism-ab-prism
   (repeat for no-prism)
4. Report RESOLVE-RATE FIRST (the correctness/equivalence bar), THEN
   turns/tokens/cost. Efficiency is only meaningful at equal resolve-rate.

## Honest scope
- SWE-bench tasks are bug fixes, so this measures prism's GENERAL value (read/SHA
  context layer + prism_query) more than change_impact specifically — a more real
  and general test than the refactor benchmarks.
- Start with a 20-task slice to size the effect before a full 500-task run.
