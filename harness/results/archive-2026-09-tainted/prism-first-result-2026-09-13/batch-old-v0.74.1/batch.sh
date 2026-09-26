#!/bin/sh
cd /Users/tapabratapal/Projects/provasign/research/harness
OLD=/opt/homebrew/bin/prism
NEW=/Users/tapabratapal/Projects/provasign/prism/bin/prism
echo "OLD: $($OLD version) sha=$(shasum -a 256 $OLD | cut -c1-12)  NEW: $($NEW version) sha=$(shasum -a 256 $NEW | cut -c1-12)  start=$(date)" > /tmp/beforeafter.status
rm -rf /tmp/beforeafter-old-v0.74.1 /tmp/beforeafter-codex-fix
python3 bench.py run --suite e2e --phase pilot --agents claude --tools prism --trials 3 --concurrency 3 --out /tmp/beforeafter-old-v0.74.1 --prism-binary "$OLD" > /tmp/beforeafter-old.log 2>&1
echo "run A exit=$? at $(date)" >> /tmp/beforeafter.status
python3 bench.py run --suite e2e --phase pilot --agents claude --tools prism --trials 3 --concurrency 3 --out /tmp/beforeafter-codex-fix --prism-binary "$NEW" > /tmp/beforeafter-codex.log 2>&1
echo "run B exit=$? at $(date)" >> /tmp/beforeafter.status
echo ALL_DONE >> /tmp/beforeafter.status
