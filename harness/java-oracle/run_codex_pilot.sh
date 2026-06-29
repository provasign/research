#!/bin/bash
# GPT (Codex) arm over the 6 jackson tasks. Mirrors run_jackson_pilot.sh but
# drives `codex exec` via run_codex.py. Scores land in runs/<task>/<MODEL>/ and
# drop into rescore_java.py / agg_jackson.py unchanged.
#
#   MODEL=gpt-5-codex TRIALS=5 bash run_codex_pilot.sh
#
# SMOKE TEST FIRST (verify trace parsing + answer parsing on your Codex version):
#   MODEL=gpt-5-codex TRIALS=1 TASKS=jackson-settable-set bash run_codex_pilot.sh
#   then inspect runs/jackson-settable-set/<MODEL>/G.t1.events.jsonl and .lastmsg.txt
set -u
cd "$(dirname "$0")/.."   # harness/
MODEL=${MODEL:?set MODEL to a GPT model id, e.g. gpt-5-codex}
TRIALS=${TRIALS:-5}
WORKDIR=${WORKDIR:-~/gvg-corpus/jackson-databind}
# small->large by default; override TASKS to subset
TASKS="${TASKS:-jackson-jsonnode-get jackson-settable-set jackson-writetypeprefix jackson-serializewithtype jackson-deserialize jackson-serialize}"
LOG=~/gvg-corpus/codex-pilot-$MODEL-$(date +%Y%m%d-%H%M).log
echo "codex pilot start $(date) model=$MODEL trials=$TRIALS" | tee -a "$LOG"
for t in $TASKS; do
  echo "=== $t ===" | tee -a "$LOG"
  python3 run_codex.py --task tasks/$t.json --arms T G --trials "$TRIALS" \
    --model "$MODEL" --workdir "$WORKDIR" --pace 10 --reset-corpus 2>&1 | tee -a "$LOG"
done
echo "codex pilot done $(date)" | tee -a "$LOG"
echo "Then: for t in $TASKS; do python3 rescore_java.py --task tasks/\$t.json; done; python3 agg_jackson.py"
