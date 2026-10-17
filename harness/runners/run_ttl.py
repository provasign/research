#!/usr/bin/env python3
"""Standard cost runner (2026-10-17): every cell isolated, cost split into startup and task.

Default use, the standard method for every native-vs-prism cost claim:

    python3 -u runners/run_ttl.py --manifest <manifest> --out-dir <dir> --no-cache

--no-cache sets DISABLE_PROMPT_CACHING=1 for every cell, so no cell can read
the prompt cache another cell wrote (cells otherwise share ~12.8k cached
prefix tokens across arms within the TTL). Each cell's dollar cost is then
reconstructed from its per-request tokens at the 5m and 1h cache rates
(usage_account.reprice, within 0.02% of the CLI bill on 67 cached cells) and
split into STARTUP (the first request's cache write: system prompt, tools,
steering) and TASK (everything after). The headline comparison is task-only;
startup is reported beside it per arm and is not a benchmark target.

Stop rule (2026-10-10, applied to task-only cost): resolve loss (native solved,
prism did not), any cell error, or prism/native task cost > 1.25 after 10
complete pairs. Tasks with invalid_reason are skipped out loud. SUMMARY.md is
written at the end with missing-measurement counts.

Earlier purpose, still available: the TTL experiment (--ttls 1h,5m, or
--cold-gap to wait out the TTL between cells instead of disabling caching).

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
    trust_tries = 0
    while True:
        try:
            return run_e2e.run_cell(task, arm, model)
        except run_e2e.TrustPrompt as e:
            trust_tries += 1
            log(f"TRUST PROMPT on {task['instance_id']}/{arm} (try {trust_tries}/5): {str(e)[-200:]!r}")
            if trust_tries >= 5:
                return {"resolved": None, "error": f"TrustPrompt after 5 tries: {str(e)[-200:]}"}
            time.sleep(60)
        except run_e2e.RateLimited as e:
            msg = str(e)
            sleep_s = 300 if isinstance(e, (run_e2e.NetworkDown, run_e2e.AuthExpired)) else 1800
            m = re.search(r"(\d+)\s*(second|minute|hour)s?", msg, re.I)
            if m:
                sleep_s = int(m.group(1)) * UNIT_S[m.group(2).lower()]
            log(f"RATE LIMIT on {task['instance_id']}/{arm}: sleeping {sleep_s}s ({msg[-300:]!r})")
            time.sleep(sleep_s)
        except Exception as e:  # noqa: BLE001
            return {"resolved": None, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def run_meta(a, arms, ttls, n_tasks) -> dict:
    """What this run was: pinned so the results file explains itself."""
    import hashlib
    bin_path = os.environ.get("PRISM_INIT_BIN") or "prism (PATH)"
    sha = None
    if os.path.isfile(bin_path):
        sha = hashlib.sha256(Path(bin_path).read_bytes()).hexdigest()[:16]
    return {"manifest": a.manifest, "tasks": n_tasks, "arms": arms, "ttls": ttls, "model": a.model,
            "claude_version": run_e2e.usage_account.claude_version(), "prism_bin": bin_path, "prism_sha256": sha,
            "order_seed": a.order_seed,
            "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)" if a.no_cache
                          else (f"cold-gap {a.cold_gap}s" if a.cold_gap else "warm (cells share the cached prefix)"),
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def task_usd(cell, ttl="5m"):
    rp = (cell.get("repriced") or {}).get(ttl) or {}
    if rp.get("usd") is None or rp.get("startup_usd") is None:
        return None
    return rp["usd"] - rp["startup_usd"]


def write_summary(out: Path, results: dict, arms: list) -> str:
    rows = [(k, v) for k, v in results.items() if not k.startswith("_")]
    native, prism = arms
    lines = [f"# {out.name}", "", f"meta: {json.dumps(results.get('_meta'), indent=None)}", ""]
    complete, missing, unscored = [], [], []
    for k, v in rows:
        c = {x["arm"]: x for x in v["cells"].values()}
        for arm in arms:
            x = c.get(arm)
            if x is None or task_usd(x) is None:
                missing.append((k, arm))
            if x is not None and x.get("resolved") is None:
                unscored.append((k, arm))
        if all(arm in c and task_usd(c[arm]) is not None for arm in arms):
            complete.append((k, c))
    tot = {arm: {"task5": 0.0, "st5": 0.0, "task1": 0.0, "st1": 0.0, "solved": 0, "api": 0} for arm in arms}
    wins = 0
    lines += ["| task | native task@5m | prism task@5m | p/n | native solved | prism solved |", "|---|---:|---:|---:|---|---|"]
    for k, c in complete:
        for arm in arms:
            t, x = tot[arm], c[arm]
            t["task5"] += task_usd(x); t["st5"] += x["repriced"]["5m"]["startup_usd"]
            t["task1"] += task_usd(x, "1h"); t["st1"] += x["repriced"]["1h"]["startup_usd"]
            t["solved"] += bool(x.get("resolved")); t["api"] += x.get("api_calls") or 0
        n, p = task_usd(c[native]), task_usd(c[prism])
        wins += p < n
        lines.append(f"| {k} | {n:.4f} | {p:.4f} | {p / n:.2f} | {c[native].get('resolved')} | {c[prism].get('resolved')} |")
    n, p = tot[native], tot[prism]
    lines += ["", f"complete pairs: {len(complete)} of {len(rows)}; prism cheaper on task cost in {wins}/{len(complete)}",
              f"solved: native {n['solved']}/{len(complete)}, prism {p['solved']}/{len(complete)}; model requests native {n['api']}, prism {p['api']}"]
    if n["task5"]:
        lines += [f"TASK cost @5m: native ${n['task5']:.3f}, prism ${p['task5']:.3f}, prism/native {p['task5'] / n['task5']:.3f}",
                  f"TASK cost @1h: native ${n['task1']:.3f}, prism ${p['task1']:.3f}, prism/native {p['task1'] / n['task1']:.3f}",
                  f"STARTUP per cell @5m: native ${n['st5'] / len(complete):.4f}, prism ${p['st5'] / len(complete):.4f} "
                  f"(@1h ${n['st1'] / len(complete):.4f} / ${p['st1'] / len(complete):.4f}); reported apart, not a target"]
    adjudicated = [(k, v["adjudication"]) for k, v in rows if v.get("adjudication")]
    if adjudicated:
        lines += ["", "## Adjudicated resolve losses (user ruling after reading both transcripts)", ""]
        for k, adj in adjudicated:
            lines.append(f"- {k}: {adj.get('ruling')} — {adj.get('reason')} "
                         f"(task cost native ${adj.get('native_task_usd')}, prism ${adj.get('prism_task_usd')}; "
                         f"prism calls {adj.get('prism_calls')}; ruled by {adj.get('by')} {adj.get('at')})")
        tool_ok = sum(1 for _, a in adjudicated if a.get("ruling", "").startswith("prism success"))
        lines.append(f"\nresolve losses ruled a prism success: {tool_ok}/{len(adjudicated)}; "
                     f"prism solved + ruled-success: {p['solved'] + tool_ok}/{len(complete)}")
    lines += [f"cells with unknown cost: {len(missing)} {missing}", f"cells with unknown result (scorer failed): {len(unscored)} {unscored}", ""]
    text = "\n".join(lines)
    (out / "SUMMARY.md").write_text(text)
    return text


def cell_summary(rec):
    usage = rec.get("usage") or {}
    ttl = (usage.get("transcript") or {}).get("cache_ttl") or usage.get("cache_ttl") or {}
    return {"resolved": rec.get("resolved"), "cost_usd": rec.get("cost_usd"), "turns": rec.get("turns"),
            "startup": rec.get("startup"),
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
    ap.add_argument("--baseline", default="",
                    help="run_overnight results.json of a 1h run on the same tasks; per task, each arm's "
                         "5m cost is reported against that run's cost (2026-10-17: Topo asked for 5m "
                         "cells only, compared with the recorded 1h benches)")
    ap.add_argument("--cold-gap", type=int, default=0,
                    help="seconds every cell must start after the previous cell ended, so the API has "
                         "expired the prompt cache (5m TTL: 360). Nothing is added to any prompt; each "
                         "cell's first request is checked to have read 0 cached tokens, else the run stops. "
                         "Deferred MCP tools cannot bust the static prefix (tried 2026-10-17).")
    ap.add_argument("--no-cache", action="store_true",
                    help="DISABLE_PROMPT_CACHING=1 for every cell: no cache exists, so no cell can share "
                         "state with another; CLI cost is then NOT what a user pays, and each cell carries "
                         "a repriced 5m/1h cost reconstructed from per-request tokens (usage_account.reprice)")
    a = ap.parse_args()
    if a.no_cache:
        os.environ["DISABLE_PROMPT_CACHING"] = "1"
        a.ttls = "nocache"
    if a.cold_gap:
        os.environ["E2E_COLD"] = "1"
    baseline = {}
    if a.baseline:
        for r in json.loads(Path(a.baseline).read_text()):
            baseline[r["task"]] = {a.native_arm: r["native"], a.prism_arm: r["prism"]}

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
    for t in [t for t in tasks if t.get("invalid_reason")]:
        log(f"(skipped invalid) {t['instance_id']}: {t['invalid_reason'][:140]}")
    tasks = [t for t in tasks if not t.get("invalid_reason")]
    tasks.sort(key=lambda t: len(t.get("patch") or ""))
    if a.limit:
        tasks = tasks[:a.limit]
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    if a.cold_gap and "_last_cell_end" not in results:
        # A fresh run cannot know when the account's last request was made
        # (another run, a probe); the first cell waits a full gap.
        results["_last_cell_end"] = time.time()
    results.setdefault("_meta", {}).update(run_meta(a, arms, ttls, len(tasks)))
    log(f"start: {len(tasks)} tasks x {arms} x {ttls}, model={a.model}, "
        f"claude={run_e2e.usage_account.claude_version()}, seed={a.order_seed}, "
        f"prism={results['_meta'].get('prism_bin')} mode={results['_meta']['cache_mode']}")

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
                if ttl != "nocache":
                    os.environ[name] = ttl
            if a.cold_gap:
                wait = results.get("_last_cell_end", 0) + a.cold_gap - time.time()
                if wait > 0:
                    log(f"   cold gap: sleeping {int(wait)}s so the previous cell's cache expires")
                    time.sleep(wait)
            log(f"-- {iid} {key}")
            rec = run_with_retry(task, arm, a.model, log)
            results["_last_cell_end"] = time.time()
            rec["transcript"] = run_e2e._preserve_transcript(
                rec.get("session_id"), out / "transcripts" / f"{iid}.{a.model}.{arm}.{ttl}.jsonl")
            row["cells"][key] = {**cell_summary(rec), "ttl": ttl, "arm": arm}
            if a.no_cache:
                pr = ((rec.get("usage") or {}).get("transcript") or {}).get("per_request") or []
                row["cells"][key]["repriced"] = {t: run_e2e.usage_account.reprice(pr, t, rec.get("model"))
                                                 for t in ("5m", "1h")}
            results_path.write_text(json.dumps(results, indent=2))
            c = row["cells"][key]
            st = c.get("startup") or {}
            log(f"   {key}: resolved={c['resolved']} cost=${c['cost_usd']} startup=${st.get('startup_usd')} "
                f"task=${st.get('task_usd')} cold={st.get('was_cold')} api_calls={c['api_calls']} "
                f"cache_5m={c['cache_5m']} cache_1h={c['cache_1h']}"
                + (f" ERROR {c['error'][:160]}" if c["error"] else ""))
            if c["error"]:
                log(f"STOP: cell error on {iid} {key}")
                return
            if a.no_cache:
                rp = c["repriced"]
                if (c["cache_write"] or 0) or (c["cache_read"] or 0):
                    log(f"STOP: {iid} {key} still used the prompt cache (write={c['cache_write']} read={c['cache_read']})")
                    return
                log(f"   {key}: repriced 5m=${rp['5m'].get('usd')} (startup ${rp['5m'].get('startup_usd')}) "
                    f"1h=${rp['1h'].get('usd')} (startup ${rp['1h'].get('startup_usd')}) uncached-bill=${c['cost_usd']}")
            if os.environ.get("E2E_COLD") == "1" and st.get("was_cold") is False:
                log(f"STOP: {iid} {key} was not cache-cold (first request read {st['first_request']['cache_read']} tokens)")
                return
        complete += 1
        # Per-pair report: within each arm, 1h vs 5m (1h from this run or the baseline run).
        for arm in arms:
            h, m = row["cells"].get(f"{arm}/1h"), row["cells"].get(f"{arm}/5m")
            if h is None and iid in baseline:
                b = baseline[iid][arm]
                h = {"cost_usd": b.get("cost_usd"), "resolved": b.get("resolved"), "cache_5m": None, "cache_1h": None}
                row.setdefault("baseline_1h", {})[arm] = {"cost_usd": b.get("cost_usd"), "resolved": b.get("resolved"),
                                                           "source": a.baseline}
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
        if a.no_cache:
            n, p = row["cells"].get(f"{arms[0]}/nocache"), row["cells"].get(f"{arms[1]}/nocache")
            if n and p:
                nt, pt = task_usd(n), task_usd(p)
                log(f"   PAIR {iid} task@5m: native ${nt and round(nt, 4)} resolved={n['resolved']} | "
                    f"prism ${pt and round(pt, 4)} resolved={p['resolved']} | prism/native={round(pt / nt, 3) if nt and pt else None} "
                    f"| startup ${n['repriced']['5m'].get('startup_usd')} / ${p['repriced']['5m'].get('startup_usd')}")
                if n["resolved"] and not p["resolved"] and not row.get("adjudication"):
                    # An adjudicated row (results.json "adjudication": the user's ruling after
                    # reading the transcripts) does not re-trigger the stop on resume.
                    write_summary(out, results, arms)
                    log(f"STOP: resolve loss on {iid} (native solved, prism did not)")
                    return
                done = [(k, {x["arm"]: x for x in v["cells"].values()}) for k, v in results.items() if not k.startswith("_")]
                done = [(k, c) for k, c in done if all(arm in c and task_usd(c[arm]) is not None for arm in arms)]
                if len(done) >= 10:
                    tn = sum(task_usd(c[arms[0]]) for _, c in done); tp = sum(task_usd(c[arms[1]]) for _, c in done)
                    if tn and tp / tn > 1.25:
                        write_summary(out, results, arms)
                        log(f"STOP: prism/native task cost {tp / tn:.3f} > 1.25 after {len(done)} pairs")
                        return
        if complete >= 10:
            tot = {}
            for r in (v for k, v in results.items() if not k.startswith("_")):
                for arm in arms:
                    h, m = r["cells"].get(f"{arm}/1h"), r["cells"].get(f"{arm}/5m")
                    if h and m and h["cost_usd"] and m["cost_usd"]:
                        t = tot.setdefault(arm, [0.0, 0.0]); t[0] += h["cost_usd"]; t[1] += m["cost_usd"]
            for arm, (h_usd, m_usd) in tot.items():
                if m_usd / h_usd > 1.25:
                    log(f"STOP: {arm} 5m/1h cost {m_usd / h_usd:.3f} > 1.25 after {complete} tasks")
                    return
    if a.no_cache:
        log(write_summary(out, results, arms))
    log("DONE")


if __name__ == "__main__":
    main()
