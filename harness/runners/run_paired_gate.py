#!/usr/bin/env python3
"""Sequential paired native-vs-prism run with a fail-fast stop-loss gate.

For each task, in order: run native (baseline) then prism (prism_source),
score both, report resolved/tokens/wall_s for both, and STOP as soon as
either gate trips:
  (1) native resolved and prism did not  -- a real regression, not noise.
  (2) prism's total tokens > --token-multiplier x native's total tokens
      -- "substantially more tokens", not a rounding difference.

Cheapest-first ordering (by task churn) so a bad signal is caught before
burning budget on the expensive tasks. Every cell is still written to
results/e2e/ by run_cell itself (cache-compatible with run_e2e.py); this
script additionally writes a running paired report to
results/paired-gate/<label>.json and prints a table row per task.
"""
from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.abspath(__file__))
for _d in (_os.path.dirname(_H), _H, _os.path.join(_os.path.dirname(_H), "aggregate"),
           _os.path.join(_os.path.dirname(_H), "build"), _os.path.join(_os.path.dirname(_H), "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse
import json
import time
from pathlib import Path

import run_e2e

TASKS_DIR = Path("tasks/e2e")
REPORT_DIR = Path("results/paired-gate")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def total_tokens(rec: dict) -> int | None:
    a, b = rec.get("tokens_request"), rec.get("tokens_out")
    return a + b if isinstance(a, int) and isinstance(b, int) else None


def load_task(iid: str) -> dict:
    return json.loads((TASKS_DIR / f"{iid}.json").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="JSON file: list of instance_ids")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--native-arm", default="baseline")
    ap.add_argument("--prism-arm", default="prism_source")
    ap.add_argument("--token-multiplier", type=float, default=1.5,
                    help="stop if prism_tokens > multiplier * native_tokens")
    ap.add_argument("--label", default="run1")
    a = ap.parse_args()

    iids = json.loads(Path(a.manifest).read_text())
    tasks = [load_task(i) for i in iids]
    # No churn field on the task JSON itself; gold-patch byte length is a
    # cheap proxy for task size/cost, and is available on every task uniformly.
    tasks.sort(key=lambda t: len(t.get("patch") or ""))

    report_path = REPORT_DIR / f"{a.label}.json"
    rows = []
    print(f"# {len(tasks)} tasks, cheapest-first, model={a.model}, "
          f"native={a.native_arm} prism={a.prism_arm}, stop if prism > {a.token_multiplier}x tokens "
          f"or prism fails where native solves", flush=True)

    for task in tasks:
        iid = task["instance_id"]
        lang = task.get("lang") or "python"
        patch_len = len(task.get("patch") or "")
        print(f"\n-- {iid} ({lang}, patch_bytes={patch_len}) --", flush=True)

        t0 = time.monotonic()
        native = run_e2e.run_cell(task, a.native_arm, a.model)
        n_tok = total_tokens(native)
        print(f"  native: resolved={native.get('resolved')} tokens={n_tok} "
              f"wall_s={native.get('wall_s')} cost=${native.get('cost_usd')} "
              f"tools={native.get('tool_trace')}", flush=True)

        prism = run_e2e.run_cell(task, a.prism_arm, a.model)
        p_tok = total_tokens(prism)
        prism_calls = sum(v for k, v in (prism.get("tool_trace") or {}).items()
                          if k.startswith("mcp__prism") and isinstance(v, int))
        print(f"  prism : resolved={prism.get('resolved')} tokens={p_tok} "
              f"wall_s={prism.get('wall_s')} cost=${prism.get('cost_usd')} "
              f"prism_calls={prism_calls} tools={prism.get('tool_trace')}", flush=True)
        if prism_calls == 0:
            print(f"  !! WARNING: 0 prism tool calls on {iid} -- check the MCP "
                  f"server actually started before trusting this cell", flush=True)

        row = {"task": iid, "lang": lang, "patch_bytes": patch_len,
               "native": {"resolved": native.get("resolved"), "tokens": n_tok,
                          "wall_s": native.get("wall_s"), "cost_usd": native.get("cost_usd"),
                          "tool_trace": native.get("tool_trace")},
               "prism": {"resolved": prism.get("resolved"), "tokens": p_tok,
                        "wall_s": prism.get("wall_s"), "cost_usd": prism.get("cost_usd"),
                        "tool_trace": prism.get("tool_trace"), "prism_calls": prism_calls}}
        rows.append(row)
        report_path.write_text(json.dumps(rows, indent=2))

        # Gate 1: solved regression
        if native.get("resolved") and not prism.get("resolved"):
            print(f"\n!!! STOP: prism failed {iid} where native solved it. "
                  f"({len(rows)}/{len(tasks)} tasks run)", flush=True)
            _summary(rows, stopped_reason="solved_regression", stopped_at=iid)
            return
        # Gate 2: substantially more tokens
        if n_tok and p_tok and p_tok > a.token_multiplier * n_tok:
            print(f"\n!!! STOP: prism used {p_tok} tokens vs native {n_tok} "
                  f"({p_tok / n_tok:.2f}x > {a.token_multiplier}x) on {iid}. "
                  f"({len(rows)}/{len(tasks)} tasks run)", flush=True)
            _summary(rows, stopped_reason="token_blowup", stopped_at=iid)
            return

    print(f"\n# completed all {len(tasks)} tasks with no gate trip", flush=True)
    _summary(rows, stopped_reason=None, stopped_at=None)


def _summary(rows, stopped_reason, stopped_at):
    n = len(rows)
    n_res = sum(1 for r in rows if r["native"]["resolved"])
    p_res = sum(1 for r in rows if r["prism"]["resolved"])
    n_tok = [r["native"]["tokens"] for r in rows if r["native"]["tokens"]]
    p_tok = [r["prism"]["tokens"] for r in rows if r["prism"]["tokens"]]
    summary = {
        "n_tasks": n, "native_resolved": n_res, "prism_resolved": p_res,
        "native_tokens_total": sum(n_tok) if n_tok else None,
        "prism_tokens_total": sum(p_tok) if p_tok else None,
        "stopped_reason": stopped_reason, "stopped_at": stopped_at,
        "rows": rows,
    }
    (REPORT_DIR / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print(f"\n=== SUMMARY: {n} tasks | native resolved {n_res}/{n} | prism resolved {p_res}/{n} | "
          f"native tokens {summary['native_tokens_total']} | prism tokens {summary['prism_tokens_total']} | "
          f"stopped_reason={stopped_reason} ===", flush=True)


if __name__ == "__main__":
    main()
