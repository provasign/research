#!/bin/bash
# Haiku T-vs-G pilot over the 4 Spoon-oracle jackson tasks (fixed Java prompt).
# Cheap first signal on whether graph advantage tracks grep-ambiguity.
set -u
cd "$(dirname "$0")/.."   # harness/
LOG=~/gvg-corpus/jackson-pilot-$(date +%Y%m%d-%H%M).log
MODEL=${MODEL:-haiku}
TRIALS=${TRIALS:-3}
TASKS="${TASKS:-jackson-jsonnode-get jackson-settable-set jackson-writetypeprefix jackson-serializewithtype jackson-deserialize jackson-serialize}"
echo "pilot start $(date)  model=$MODEL trials=$TRIALS" | tee -a "$LOG"
for t in $TASKS; do
  echo "=== $t ===" | tee -a "$LOG"
  python3 run.py --task tasks/$t.json --arms T G --trials "$TRIALS" \
    --model "$MODEL" --workdir ~/gvg-corpus/jackson-databind --pace 20 2>&1 | tee -a "$LOG"
done
echo "pilot done $(date)" | tee -a "$LOG"
echo "LOG=$LOG"
