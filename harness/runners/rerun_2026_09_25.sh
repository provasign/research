#!/bin/bash
# Rerun every recent benchmark on the corrected bed (2026-09-25):
#   - leak-free checkouts (run_e2e._worktree, aa3a98cb)
#   - issue / hand-written prompts instead of PR bodies (99b11ea5, df5e6cba, 5a15a22c)
# Same manifests and arms as the originals. Sequential (one agent + one scoring
# container at a time) because parallel Maven validation hit host memory limits.
# prism_init arms use the installed prism (v0.82.2), not the version of the
# original run; A/B builds come from exact commits in ~/prism-ab-bins.
# Resumable: rerun this script and every stage skips finished tasks.
set -u
cd "$(dirname "$0")/.."
OUT=results/rerun-2026-09-25
B=~/prism-ab-bins
mkdir -p "$OUT"
stage() {  # name manifest native_arm prism_arm [env...]
  local name=$1 man=$2 na=$3 pa=$4; shift 4
  echo "[$(date '+%F %T')] STAGE $name: $na vs $pa on $man"
  env "$@" python3 -u runners/run_overnight.py --manifest "$man" --out-dir "$OUT/$name" \
      --native-arm "$na" --prism-arm "$pa" --model sonnet >> "$OUT/$name.log" 2>&1
  echo "[$(date '+%F %T')] STAGE $name exit=$? $(tail -1 "$OUT/$name.log")"
}
stage headline     results/guard-fix-run-manifest.json baseline            prism_init
stage guard-hook   results/residency-ab-manifest.json  prism_init_no_guard prism_init
stage residency    results/residency-ab-manifest.json  prism_init_deferred prism_init
stage search-body  results/guard-fix-run-manifest.json prism_body_baseline prism_body_exp \
      PRISM_BODY_BASELINE_BIN=$B/prism-body-base PRISM_BODY_EXP_BIN=$B/prism-body-exp
for p in 1 2 3; do
  stage h3-pass$p  results/h3-movable-manifest.json    prism_body_baseline prism_body_exp \
      PRISM_BODY_BASELINE_BIN=$B/prism-h3-control PRISM_BODY_EXP_BIN=$B/prism-h3-treat
done
echo "[$(date '+%F %T')] ALL STAGES DONE"
