cd ~/Projects/provasign/research/harness
# Change bed: released v0.87.38 (prism_cli) vs candidate v0.87.39 (prism_cli_b: text renders the
# index warning once, multiline signatures kept, CLI "known symbol -> change-impact/lookup" line). Sonnet 5.5.
export PRISM_INIT_BIN=~/prism-ab-bins/prism-v0.87.38 PRISM_CLI_B_BIN=~/prism-ab-bins/prism-cand-v08739 CLI_BENCH_SPEND_CAP_USD=35
python3 ~/Projects/provasign/prism/docs/research/cli-issue42-2026-10-18/run_cli_product.py \
  --manifest results/seeded32-manifest.json --out-dir results/change32-v08739cand-2026-10-21 \
  --arms prism_cli,prism_cli_b --no-cache --order-seed change32-v08739cand
echo "ALLDONE rc=$?" >> results/change32-v08739cand-2026-10-21/run.log
