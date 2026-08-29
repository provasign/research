#!/usr/bin/env python3
"""Fail-fast A/B gate: baseline prism binary vs candidate, agentic bed.

The release gate for BEHAVIOR changes (result shapes, sizes, routing,
steering, schemas): unit suites and ci_invariants catch engine regressions
free, but only a paid agentic run catches "the agent stopped getting usable
results". This gate is built to fail FAST and cheap:

  - tasks run cheapest-first, one paired cell at a time
  - HARD-FAIL immediately (nonzero exit) when the candidate errors where the
    baseline succeeded, or its recall drops >0.15 on any task
  - aggregate FAIL when mean recall drops >0.05 over the bed
  - cells are cached per (task, model, binary-sha), so re-runs and repeated
    gates against the same baseline cost only the new candidate cells

Honest scope: n=9 haiku tasks detects BIG breaks (the realistic failure mode
for payload/steering changes), not ±5% quality shifts — the per-cell noise
floor is ~50%, subtle effects need ~48 pairs and a real study. A PASS here
means "not broken", never "proven better".

Usage:
  python ab_gate.py --baseline ~/bin/prism --candidate ../prism/bin/prism \
      [--model haiku] [--limit N] [--out runs/ab-gate]
Exit 0 = PASS, 1 = FAIL, 2 = harness error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_agentic_mcp as bed  # noqa: E402
from schema import Task  # noqa: E402

# Cheapest-first by measured wall time (2026-08-28 bed run).
TASKS = [
    "tasks/jackson-jsonnode-get.json",
    "tasks/jackson-settable-set.json",
    "tasks/typeorm-driver-escape.json",
    "tasks/django-quotename.json",
    "tasks/jackson-writetypeprefix.json",
    "tasks/guava-forwarding-delegate.json",
    "tasks/jackson-serialize.json",
    "tasks/grafana-checkhealth-impact.json",
    "tasks/grafana-querydata-impact.json",
]

HARD_RECALL_DROP = 0.15   # any single task
MEAN_RECALL_DROP = 0.05   # over the whole bed


def binary_sha(path: str) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:8]


def arm_for(binary: str, tag: str) -> str:
    """Register an ab_agentic_mcp arm bound to a specific prism binary."""
    cfg = Path(f"/tmp/ab-agentic-mcp/gate-{tag}.json")
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(json.dumps({"mcpServers": {"prism": {
        "type": "stdio", "command": str(Path(binary).resolve()),
        "args": ["mcp"], "alwaysLoad": True}}}))
    name = f"gate-{tag}"
    bed.ARMS[name] = dict(bed.ARMS["prism"], mcp=str(cfg))
    return name


def run_cell(arm: str, task: Task, corpus: Path, model: str,
             out: Path, binary: str, sha: str) -> dict:
    f = out / f"{task.id}.{model}.{sha}.json"
    if f.exists():
        return json.loads(f.read_text())
    subprocess.run(["git", "-C", str(corpus), "checkout", "-q", task.pin],
                   capture_output=True)
    subprocess.run([binary, "index", str(corpus)], capture_output=True,
                   timeout=900)
    rec = bed.run_arm(arm, task, corpus, model)
    rec.update(task=task.id, model=model, binary_sha=sha)
    f.write_text(json.dumps(rec, indent=2))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--limit", type=int, default=len(TASKS))
    ap.add_argument("--out", default="runs/ab-gate")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    b_sha, c_sha = binary_sha(args.baseline), binary_sha(args.candidate)
    if b_sha == c_sha:
        print(f"note: baseline == candidate ({b_sha}) — pipeline probe mode")
    b_arm = arm_for(args.baseline, "base")
    c_arm = arm_for(args.candidate, "cand")

    drops, cand_tok, base_tok = [], 0, 0
    for tp in TASKS[: args.limit]:
        task = Task.load(tp)
        corpus = Path(task.workdir or task.repo)
        if not corpus.exists():
            print(f"SKIP {task.id}: corpus absent")
            continue
        b = run_cell(b_arm, task, corpus, args.model, out, args.baseline, b_sha)
        c = run_cell(c_arm, task, corpus, args.model, out, args.candidate, c_sha)
        br, cr = b.get("recall"), c.get("recall")
        print(f"{task.id:30} base recall={br} tok={b.get('tokens_in',0)//1000}k | "
              f"cand recall={cr} tok={c.get('tokens_in',0)//1000}k")
        if "error" in c and "error" not in b:
            print(f"HARD FAIL: candidate errored where baseline succeeded "
                  f"({c['error'][:120]})")
            return 1
        if br is not None and cr is not None:
            if cr < br - HARD_RECALL_DROP:
                print(f"HARD FAIL: recall {br} -> {cr} on {task.id} "
                      f"(drop > {HARD_RECALL_DROP})")
                return 1
            drops.append(br - cr)
        cand_tok += c.get("tokens_in", 0) or 0
        base_tok += b.get("tokens_in", 0) or 0

    if not drops:
        print("HARNESS ERROR: no scored pairs")
        return 2
    mean_drop = sum(drops) / len(drops)
    tok_delta = (cand_tok - base_tok) / max(base_tok, 1) * 100
    print(f"\npairs={len(drops)} mean recall delta={-mean_drop:+.3f} "
          f"tokens {tok_delta:+.0f}%")
    if mean_drop > MEAN_RECALL_DROP:
        print(f"FAIL: mean recall drop {mean_drop:.3f} > {MEAN_RECALL_DROP}")
        return 1
    print("PASS (not-broken; subtle effects need a full study)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
