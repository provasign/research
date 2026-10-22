cd ~/Projects/provasign/research/harness
export PRISM_INIT_BIN=~/prism-ab-bins/prism-v0.87.37 CLI_BENCH_SPEND_CAP_USD=45
python3 ~/Projects/provasign/prism/docs/research/cli-issue42-2026-10-18/run_cli_product.py \
  --manifest results/issue42-manifest.json --out-dir results/v0837-vs-native41-2026-10-20 \
  --arms native,prism_cli --no-cache --order-seed route-read-vs-native41-2026-10-20
echo "ALLDONE rc=$?" >> results/v0837-vs-native41-2026-10-20/run.log
