#!/usr/bin/env bash
# Run the full jackson grid: {T, G, Gstar} x {haiku, sonnet, opus} x 1 trial
# each, for all 6 tasks.  Results land in runs/<task>/<model>/.
#
# Usage:
#   ./run_jackson_grid.sh                   # all arms x all models
#   ./run_jackson_grid.sh --arms T G        # subset of arms
#   ./run_jackson_grid.sh --models haiku    # subset of models
#   ./run_jackson_grid.sh --tasks jackson-serialize  # single task
#
# After all runs complete, score with:
#   python rescore_java.py          # map line refs to method names (MANDATORY)
#   python agg_jackson.py           # summary table
#
# The local (qwen3-coder:30b) arm is run separately via run_local.py since it
# needs a different invocation path.

set -euo pipefail
HARNESS="$(cd "$(dirname "$0")" && pwd)"

TASKS=(
  jackson-jsonnode-get
  jackson-settable-set
  jackson-writetypeprefix
  jackson-serializewithtype
  jackson-deserialize
  jackson-serialize
)
ARMS=(T G Gstar)
MODELS=(haiku sonnet opus)
TRIALS=1
PACE=5  # seconds between runs to spread API load

# --- parse flags ---
while [[ $# -gt 0 ]]; do
  case $1 in
    --arms)    shift; IFS=' ' read -r -a ARMS    <<< "$*"; break ;;
    --models)  shift; IFS=' ' read -r -a MODELS  <<< "$*"; break ;;
    --tasks)   shift; IFS=' ' read -r -a TASKS   <<< "$*"; break ;;
    --trials)  shift; TRIALS=$1 ;;
    --pace)    shift; PACE=$1 ;;
    *) echo "unknown flag: $1"; exit 1 ;;
  esac
  shift
done

echo "Grid: arms=${ARMS[*]}  models=${MODELS[*]}  tasks=${TASKS[*]}  trials=$TRIALS"
echo ""

cd "$HARNESS"
for model in "${MODELS[@]}"; do
  for task in "${TASKS[@]}"; do
    taskfile="tasks/${task}.json"
    if [[ ! -f "$taskfile" ]]; then
      echo "[skip] missing $taskfile"
      continue
    fi
    echo "=== $task  model=$model  arms=${ARMS[*]} ==="
    python run.py \
      --task "$taskfile" \
      --arms "${ARMS[@]}" \
      --model "$model" \
      --trials "$TRIALS" \
      --pace "$PACE"
    echo ""
  done
done

echo "=== grid done ==="
echo "Next: python rescore_java.py && python agg_jackson.py"
