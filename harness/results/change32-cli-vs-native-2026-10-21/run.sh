cd ~/Projects/provasign/research/harness
# Change-impact bed (seeded32: interface-method renames with namesakes, signature changes,
# property renames; py/go/ts/java). native vs prism_cli on released v0.87.38, Sonnet 5.5, no-cache repriced.
export PRISM_INIT_BIN=~/prism-ab-bins/prism-v0.87.38 CLI_BENCH_SPEND_CAP_USD=35
python3 ~/Projects/provasign/prism/docs/research/cli-issue42-2026-10-18/run_cli_product.py \
  --manifest results/seeded32-manifest.json --out-dir results/change32-cli-vs-native-2026-10-21 \
  --arms native,prism_cli --no-cache --order-seed change32-cli
echo "ALLDONE rc=$?" >> results/change32-cli-vs-native-2026-10-21/run.log
