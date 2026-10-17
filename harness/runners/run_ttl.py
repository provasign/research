#!/usr/bin/env python3
"""Prompt-cache TTL experiment: every manifest task x {native, prism} x {1h, 5m}.

Claude Code writes the prompt cache at the 1-hour rate ($4/M on Sonnet 5.5)
unless CLAUDE_CODE_PROMPT_CACHE_TTL=5m ($2.50/M). Cache writes were ~71% of
a wide cell's cost (2026-10-17 audit), so the TTL is a deployment lever for
BOTH arms. This runner measures it instead of repricing old traces: the 5m
cache can expire between requests and change the hit rate.

Cells of one task run back to back in a seeded order; each cell is written
as soon as it finishes (resumable per cell). Per task it prints, per arm,
1h vs 5m cost and the TTL counters the API reported, so a setting that did
not take effect is visible on the first task. Stop rule (2026-10-10):
resolve loss (1h solved, 5m not, same arm), any cell error, or 5m/1h cost
> 1.25 after 10 complete tasks -- the run halts and says why.
"""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.abspath(__file__))
for _d in (_os.path.dirname(_H), _H, _os.path.join(_os.path.dirname(_H), "aggregate"),
           _os.path.join(_os.path.dirname(_H), "build"), _os.path.join(_os.path.dirname(_H), "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse
import json
import os
import random
import re
import time
from pathlib import Path

import run_e2e

TTL_ENV = ("CLAUDE_CODE_PROMPT_CACHE_TTL", "CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL")
UNIT_S = {"second": 1, "minute": 60, "hour": 3600}


def run_with_retry(task, arm, model, log):
    while True:
        try:
            return run_e2e.run_cell(task, arm, model)
        except run_e2e.RateLimited as e:
            msg = str(e)
            sleep_s = 300 if isinstance(e, (run_e2e.NetworkDown, run_e2e.AuthExpired)) else 1800
            m = re.search(r"(\d+)\s*(second|minute|hour)s?", msg, re.I)
            if m:
                sleep_s = int(m.group(1)) * UNIT_S[m.group(2).lower()]
            log(f"RATE LIMIT on {task['instance_id']}/{arm}: sleeping {sleep_s}s ({msg[:120]!r})")
            time.sleep(sleep_s)
        except Exception as e:  # noqa: BLE001
            return {"resolved": None, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def cell_summary(rec):
    usage = rec.get("usage") or {}
    ttl = (usage.get("transcript") or {}).get("cache_ttl") or usage.get("cache_ttl") or {}
    return {"resolved": rec.get("resolved"), "cost_usd": rec.get("cost_usd"), "turns": rec.get("turns"),
            "api_calls": rec.get("api_calls"), "wall_s": rec.get("wall_s"),
            "tokens": rec.get("tokens_request"), "tokens_out": rec.get("tokens_out"),
            "cache_write": rec.get("tokens_cache_write"), "cache_read": rec.get("tokens_cache_read"),
            "cache_5m": ttl.get("cache_5m"), "cache_1h": ttl.get("cache_1h"),
            "session_id": rec.get("session_id"), "model": rec.get("model"),
            "tool_trace": rec.get("tool_trace"), "usage": usage, "transcript": rec.get("transcript"),
            "error": rec.get("error") or rec.get("agent_error")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--native-arm", default="native")
    ap.add_argument("--prism-arm", default="prism_init")
    ap.add_argument("--ttls", default="1h,5m")
    ap.add_argument("--order-seed", default="ttl-2026-10-17")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N tasks (probe)")
    a = ap.parse_args()

    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    results_path, log_path = out / "results.json", out / "run.log"
    arms, ttls = [a.native_arm, a.prism_arm], a.ttls.split(",")

    def log(msg):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        with log_path.open("a") as f:
            f.write(line + "\n")

    manifest = json.loads(Path(a.manifest).read_text())
    tasks = [json.loads((Path("tasks/e2e") / f"{i}.json").read_text()) for i in manifest]
    tasks.sort(key=lambda t: len(t.get("patch") or ""))
    if a.limit:
        tasks = tasks[:a.limit]
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    log(f"start: {len(tasks)} tasks x {arms} x {ttls}, model={a.model}, "
        f"claude={run_e2e.usage_account.claude_version()}, seed={a.order_seed}")

    complete = 0
    for task in tasks:
        iid = task["instance_id"]
        row = results.setdefault(iid, {"lang": task.get("lang"), "cells": {}})
        cells = [(arm, ttl) for arm in arms for ttl in ttls]
        random.Random(f"{a.order_seed}-{iid}").shuffle(cells)
        row["order"] = [f"{arm}/{ttl}" for arm, ttl in cells]
        for arm, ttl in cells:
            key = f"{arm}/{ttl}"
            if key in row["cells"]:
                continue
            for name in TTL_ENV:
                os.environ[name] = ttl
            log(f"-- {iid} {key}")
            rec = run_with_retry(task, arm, a.model, log)
            rec["transcript"] = run_e2e._preserve_transcript(
                rec.get("session_id"), out / "transcripts" / f"{iid}.{a.model}.{arm}.{ttl}.jsonl")
            row["cells"][key] = {**cell_summary(rec), "ttl": ttl, "arm": arm}
            results_path.write_text(json.dumps(results, indent=2))
            c = row["cells"][key]
            log(f"   {key}: resolved={c['resolved']} cost=${c['cost_usd']} api_calls={c['api_calls']} "
                f"cache_5m={c['cache_5m']} cache_1h={c['cache_1h']}"
                + (f" ERROR {c['error'][:160]}" if c["error"] else ""))
            if c["error"]:
                log(f"STOP: cell error on {iid} {key}")
                return
        complete += 1
        # Per-pair report: within each arm, 1h vs 5m.
        for arm in arms:
            h, m = row["cells"].get(f"{arm}/1h"), row["cells"].get(f"{arm}/5m")
            if not (h and m):
                continue
            ratio = (m["cost_usd"] / h["cost_usd"]) if h["cost_usd"] and m["cost_usd"] else None
            log(f"   PAIR {iid} {arm}: 1h ${h['cost_usd']} resolved={h['resolved']} | "
                f"5m ${m['cost_usd']} resolved={m['resolved']} | 5m/1h={ratio and round(ratio, 3)}")
            if h["resolved"] and not m["resolved"]:
                log(f"STOP: resolve loss on {iid} {arm} (1h solved, 5m did not)")
                return
            if m["cache_5m"] is not None and m["cache_1h"] and m["cache_5m"] == 0:
                log(f"STOP: 5m cell wrote only 1h cache entries on {iid} {arm}: the TTL setting did not take effect")
                return
        if complete >= 10:
            tot = {}
            for r in results.values():
                for arm in arms:
                    h, m = r["cells"].get(f"{arm}/1h"), r["cells"].get(f"{arm}/5m")
                    if h and m and h["cost_usd"] and m["cost_usd"]:
                        t = tot.setdefault(arm, [0.0, 0.0]); t[0] += h["cost_usd"]; t[1] += m["cost_usd"]
            for arm, (h_usd, m_usd) in tot.items():
                if m_usd / h_usd > 1.25:
                    log(f"STOP: {arm} 5m/1h cost {m_usd / h_usd:.3f} > 1.25 after {complete} tasks")
                    return
    log("DONE")


if __name__ == "__main__":
    main()
