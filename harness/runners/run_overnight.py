#!/usr/bin/env python3
"""Unattended overnight run: all manifest tasks x (baseline, prism_init resident).

Auto-resumes through Claude usage-limit rate limits (sleeps and retries the
SAME cell, does not skip it). Never stops on an individual bad cell -- errors
are recorded and the run moves on. Every flagged cell (resolve mismatch, or
token ratio outside [1/multiplier, multiplier]) gets an evidence bundle
(tool trace + turns + errors for both arms) written straight into the
Markdown report, plus a heuristic attribution: prism_calls==0 means whatever
happened is a non-adoption artifact, not an engine result.

Resumable: results.json + state.json let a restart skip tasks already done.
Writes continuously so a kill at any point loses at most one in-flight task.
"""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.abspath(__file__))
for _d in (_os.path.dirname(_H), _H, _os.path.join(_os.path.dirname(_H), "aggregate"),
           _os.path.join(_os.path.dirname(_H), "build"), _os.path.join(_os.path.dirname(_H), "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse
import json
import re
import time
from pathlib import Path

import run_e2e

_ap = argparse.ArgumentParser()
_ap.add_argument("--manifest", default="results/archive-2026-09-tainted/paired-gate/manifest.json")
_ap.add_argument("--out-dir", default="results/overnight-run")
_ap.add_argument("--native-arm", default="baseline")
_ap.add_argument("--prism-arm", default="prism_init")
_ap.add_argument("--model", default="sonnet")
_args = _ap.parse_args()

MANIFEST = Path(_args.manifest)
TASKS_DIR = Path("tasks/e2e")
OUT_DIR = Path(_args.out_dir)
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS = OUT_DIR / "results.json"
REPORT = OUT_DIR / "REPORT.md"
STATE = OUT_DIR / "state.json"

MODEL = _args.model
NATIVE_ARM = _args.native_arm
PRISM_ARM = _args.prism_arm
TOKEN_FLAG_MULTIPLIER = 1.5
DEFAULT_RATE_LIMIT_SLEEP = 1800  # 30 min fallback when no reset hint is parseable

UNIT_S = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60, "hour": 3600, "hours": 3600}


def total_tokens(rec: dict):
    a, b = rec.get("tokens_request"), rec.get("tokens_out")
    return a + b if isinstance(a, int) and isinstance(b, int) else None


def prism_call_count(rec: dict) -> int:
    tt = rec.get("tool_trace") or {}
    return sum(v for k, v in tt.items() if k.startswith("mcp__prism") and isinstance(v, int))


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with REPORT.open("a") as f:
        f.write(f"\n> {line}\n")


def run_with_retry(task: dict, arm: str, model: str) -> dict:
    while True:
        try:
            return run_e2e.run_cell(task, arm, model)
        except run_e2e.RateLimited as e:
            msg = str(e)
            sleep_s = 300 if isinstance(e, run_e2e.NetworkDown) else DEFAULT_RATE_LIMIT_SLEEP
            m = re.search(r"(\d+)\s*(second|minute|hour)s?", msg, re.I)
            if m:
                sleep_s = int(m.group(1)) * UNIT_S[m.group(2).lower()]
            log(f"RATE LIMIT on {task['instance_id']}/{arm}: sleeping {sleep_s}s "
                f"(hint: {msg[:150]!r}), then retrying the same cell")
            time.sleep(sleep_s)
        except Exception as e:  # noqa: BLE001
            return {"resolved": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def evidence(rec: dict, label: str) -> str:
    lines = [f"- **{label}**: resolved={rec.get('resolved')} turns={rec.get('turns')} "
             f"tokens={total_tokens(rec)} wall_s={rec.get('wall_s')} cost=${rec.get('cost_usd')}",
             f"  - tools: {rec.get('tool_trace')}"]
    if rec.get("agent_error"):
        lines.append(f"  - agent_error: {rec['agent_error'][:400]}")
    if rec.get("error"):
        lines.append(f"  - error: {rec['error'][:400]}")
    return "\n".join(lines)


def main():
    manifest = json.loads(MANIFEST.read_text())
    tasks = [json.loads((TASKS_DIR / f"{i}.json").read_text()) for i in manifest]
    tasks.sort(key=lambda t: len(t.get("patch") or ""))

    state = load_json(STATE, {})
    results = load_json(RESULTS, [])

    if not REPORT.exists():
        REPORT.write_text(
            f"# Overnight run: native vs resident prism_init\n\n"
            f"Started {time.strftime('%Y-%m-%d %H:%M:%S')}. "
            f"{len(tasks)} tasks, model={MODEL}, arms={NATIVE_ARM} vs {PRISM_ARM}.\n\n"
            f"Flag rule: resolve mismatch, OR token ratio (prism/native) outside "
            f"[{1/TOKEN_FLAG_MULTIPLIER:.2f}, {TOKEN_FLAG_MULTIPLIER}]. "
            f"A flagged cell with 0 prism tool calls is a non-adoption artifact, "
            f"not attributable to prism's engine -- flagged separately below.\n"
        )

    log(f"starting: {len(tasks)} tasks, {sum(1 for i in manifest if state.get(i) == 'done')} already done")

    for task in tasks:
        iid = task["instance_id"]
        if state.get(iid) == "done":
            continue
        lang = task.get("lang") or "python"
        log(f"-- {iid} ({lang}) --")

        native = run_with_retry(task, NATIVE_ARM, MODEL)
        prism = run_with_retry(task, PRISM_ARM, MODEL)

        n_tok, p_tok = total_tokens(native), total_tokens(prism)
        p_calls = prism_call_count(prism)
        row = {
            "task": iid, "lang": lang,
            "native": {"resolved": native.get("resolved"), "turns": native.get("turns"),
                      "tokens": n_tok, "wall_s": native.get("wall_s"),
                      "cost_usd": native.get("cost_usd"), "tool_trace": native.get("tool_trace"),
                      "session_id": native.get("session_id"),
                      "runtimes": native.get("runtimes"),
                      "error": native.get("error") or native.get("agent_error")},
            "prism": {"resolved": prism.get("resolved"), "turns": prism.get("turns"),
                     "tokens": p_tok, "wall_s": prism.get("wall_s"),
                     "cost_usd": prism.get("cost_usd"), "tool_trace": prism.get("tool_trace"),
                     "prism_calls": p_calls, "session_id": prism.get("session_id"),
                     "runtimes": prism.get("runtimes"),
                     "error": prism.get("error") or prism.get("agent_error")},
        }
        results.append(row)
        RESULTS.write_text(json.dumps(results, indent=2))
        state[iid] = "done"
        STATE.write_text(json.dumps(state, indent=2))

        resolve_mismatch = native.get("resolved") != prism.get("resolved")
        ratio = (p_tok / n_tok) if (n_tok and p_tok) else None
        token_flag = ratio is not None and (ratio > TOKEN_FLAG_MULTIPLIER or ratio < 1 / TOKEN_FLAG_MULTIPLIER)
        flagged = resolve_mismatch or token_flag

        with REPORT.open("a") as f:
            f.write(f"\n## {iid} ({lang})\n\n")
            f.write(f"- native: resolved={native.get('resolved')} tokens={n_tok} "
                    f"turns={native.get('turns')} wall_s={native.get('wall_s')}\n")
            f.write(f"- prism : resolved={prism.get('resolved')} tokens={p_tok} "
                    f"turns={prism.get('turns')} wall_s={prism.get('wall_s')} "
                    f"prism_calls={p_calls}\n")
            if ratio:
                f.write(f"- token ratio (prism/native): {ratio:.2f}x\n")
            if flagged:
                reasons = []
                if resolve_mismatch:
                    reasons.append("resolve mismatch")
                if token_flag:
                    reasons.append(f"token ratio {ratio:.2f}x outside [{1/TOKEN_FLAG_MULTIPLIER:.2f}, {TOKEN_FLAG_MULTIPLIER}]")
                f.write(f"\n**FLAGGED** ({', '.join(reasons)})\n\n")
                if p_calls == 0:
                    f.write("**Attribution: NON-ADOPTION.** Prism was never called "
                            "(0 mcp__prism__prism calls) in this cell -- this result is "
                            "not attributable to prism's engine or context quality, only "
                            "to the agent not reaching for the tool.\n\n")
                else:
                    f.write(f"**Attribution: prism WAS called ({p_calls}x) -- this is a "
                            f"real signal, needs manual read of the evidence below, not "
                            f"an adoption excuse.**\n\n")
                f.write(evidence(native, "native") + "\n")
                f.write(evidence(prism, "prism") + "\n")

        log(f"   native resolved={native.get('resolved')} tokens={n_tok} | "
            f"prism resolved={prism.get('resolved')} tokens={p_tok} prism_calls={p_calls}"
            + (" [FLAGGED]" if flagged else ""))

    n_done = [r for r in results if r["native"].get("tokens") or r["prism"].get("tokens")]
    n_res = sum(1 for r in results if r["native"]["resolved"])
    p_res = sum(1 for r in results if r["prism"]["resolved"])
    n_tot = sum(r["native"]["tokens"] for r in results if r["native"]["tokens"])
    p_tot = sum(r["prism"]["tokens"] for r in results if r["prism"]["tokens"])
    flagged_rows = [r for r in results if r["native"]["resolved"] != r["prism"]["resolved"]
                    or (r["native"]["tokens"] and r["prism"]["tokens"]
                        and (r["prism"]["tokens"] / r["native"]["tokens"] > TOKEN_FLAG_MULTIPLIER
                             or r["prism"]["tokens"] / r["native"]["tokens"] < 1 / TOKEN_FLAG_MULTIPLIER))]
    non_adoption_flags = [r for r in flagged_rows if r["prism"]["prism_calls"] == 0]
    real_flags = [r for r in flagged_rows if r["prism"]["prism_calls"] > 0]

    with REPORT.open("a") as f:
        f.write(f"\n\n# SUMMARY\n\n{len(results)}/{len(tasks)} tasks completed.\n\n"
                f"- native resolved: {n_res}/{len(results)}\n"
                f"- prism  resolved: {p_res}/{len(results)}\n"
                f"- native tokens total: {n_tot}\n"
                f"- prism  tokens total: {p_tot} ({p_tot/n_tot:.2f}x native)\n" if n_tot else "")
        f.write(f"- flagged cells: {len(flagged_rows)} "
                f"({len(non_adoption_flags)} non-adoption, {len(real_flags)} real prism signal)\n")
        if real_flags:
            f.write("\n## Cells needing a real look (prism was called, still flagged)\n\n")
            for r in real_flags:
                f.write(f"- {r['task']}\n")
        f.write(f"\nCompleted {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    log(f"DONE: {len(results)}/{len(tasks)} tasks, {len(flagged_rows)} flagged "
        f"({len(non_adoption_flags)} non-adoption, {len(real_flags)} real)")


if __name__ == "__main__":
    main()
