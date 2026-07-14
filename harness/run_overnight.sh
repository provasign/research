#!/bin/bash
# Overnight end-to-end benchmark: mason (running) -> haiku -> sonnet -> local
# neutral loop -> aggregate. Sequential for robustness (no ollama/Docker/worktree
# contention). Aggregates after every stage, so a partial RESULTS-E2E.md always
# exists. Rides through subscription rate limits via E2E_WAIT_ON_LIMIT.
set -u
cd "$(dirname "$0")"
export E2E_WAIT_ON_LIMIT=1
export E2E_LIMIT_SLEEP=1200
M=tasks-e2e/manifest.pilot.json
ARMS=baseline,prism_g,prism_gstar,codegraph
log(){ echo "[overnight $(date +%H:%M)] $*"; }

log "waiting for the in-flight mason run to finish (produces the 5 local mason cells)"
while pgrep -f 'run_e2e.py.*--arms mason' >/dev/null 2>&1; do sleep 60; done
python3 aggregate_e2e.py >/dev/null 2>&1 || true

log "HAIKU (cloud) — the clean 4-arm comparison"
python3 run_e2e.py "$M" --models haiku  --arms "$ARMS"   || log "haiku stage error"
python3 aggregate_e2e.py >/dev/null 2>&1 || true

log "SONNET (cloud)"
python3 run_e2e.py "$M" --models sonnet --arms "$ARMS"   || log "sonnet stage error"
python3 aggregate_e2e.py >/dev/null 2>&1 || true

log "LOCAL neutral loop (control: does the tool help a weak loop)"
python3 run_e2e.py "$M" --models local  --arms "$ARMS"   || log "local stage error"

log "aggregating final"
python3 aggregate_e2e.py
log "ALL DONE"
