#!/usr/bin/env python3
"""Run mason over a bed of local-model-sized tasks, static scoring only.

The beds this harness had been using are outliers: dynaconf-1225 is 30KB of
source across 14 files, babel-1164 is 55KB across 9, against a corpus median
of 2.5KB. Nothing a local model does on those is measurable -- every run
floors at `shallow` regardless of steering quality. This bed is the opposite
end: single-file fixes of a few hundred bytes, the shape of an actual bug fix.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import mason_oracle as mo
import static_oracle as so
import swebench_ab as ab

OUT = Path(__file__).resolve().parent / "runs" / "mason-smallbed"


def main() -> None:
    bed = json.loads(Path(sys.argv[1]).read_text())
    mason = sys.argv[2] if len(sys.argv) > 2 else "/tmp/mason-bench"
    model = sys.argv[3] if len(sys.argv) > 3 else "ollama:qwen2.5-coder:14b"
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for i, tid in enumerate(bed, 1):
        try:
            task = mo.load_task(tid)
            prompt = ab.BASE_PROMPT.format(repo=task["repo"],
                                           problem=task["problem_statement"], steer="")
            t0 = time.time()
            cell = mo.run_cell(task, mason, model, prompt, 1200)
            st = so.classify(task, cell["_patch"], cell["_log"])
            rec = {"instance_id": tid, "secs": cell["secs"],
                   "tokens_in": cell["tokens_in"], "bucket": st["bucket"],
                   "coverage": st["coverage"], "size_ratio": st["size_ratio"],
                   "agent_bytes": st["agent_bytes"], "gold_bytes": st["gold_bytes"],
                   "files_hit": st["files_hit"], "flags": st["flags"],
                   "tool_calls": st["tool_calls"]}
            (OUT / f"{tid}.json").write_text(json.dumps({**rec, "static": st}, indent=2))
            (OUT / f"{tid}.patch").write_text(cell["_patch"])
            (OUT / f"{tid}.log").write_text(cell["_log"])
        except Exception as e:
            # Print the traceback, do not just record a bucket. An opaque
            # "ERROR" cost a whole bed cycle on 2026-09-07 (a bad kwarg in
            # agent_worktree) because the reason was swallowed into a summary
            # file that is only written after every task finishes.
            import traceback
            traceback.print_exc()
            rec = {"instance_id": tid, "bucket": "ERROR", "error": repr(e)[:300]}
        results.append(rec)
        if rec.get("bucket") == "ERROR":
            print(f"[{i}/{len(bed)}] {tid}: ERROR {rec['error']}", flush=True)
            print("HALTING: a harness error makes every later cell suspect. "
                  "Fix it, then rerun the bed.", flush=True)
            (OUT / "summary.partial.json").write_text(json.dumps(results, indent=2))
            raise SystemExit(1)
        print(f"[{i}/{len(bed)}] {tid}: {rec.get('bucket')} "
              f"cov={rec.get('coverage')} ratio={rec.get('size_ratio')} "
              f"{rec.get('secs')}s", flush=True)
    (OUT / "summary.json").write_text(json.dumps(results, indent=2))
    buckets = {}
    for r in results:
        buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
    print("\nBUCKETS:", json.dumps(buckets, indent=2))


if __name__ == "__main__":
    main()
