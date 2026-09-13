"""Agentic A/B: does Engine B actually cut tool calls / tokens / time — and at
what CORRECTNESS? Same agent (claude -p), same task, three arms differing ONLY
in the tool available:

  baseline  — grep/read only            (Engine B's claim is 'fewer calls than this')
  engine-b — Engine B MCP (explore/impact/callers)
  prism     — Prism MCP (change_impact)

Per arm we record recall (oracle-scored — the headline), num_turns (tool-call
proxy), tokens, cost, wall_s. Correctness first: a cheaper wrong answer loses.

Usage:  python ab_agentic_mcp.py --model opus  tasks/jackson-jsonnode-get.json ...
"""
from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)


import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from schema import Answer, Task
from score import SCORER_VERSION, score
import usage_account

HOME = Path.home()
# Every process owns its configs; importing a runner cannot retarget another.
CFG_DIR = Path(tempfile.mkdtemp(prefix="ab-agentic-mcp-"))

# MCP server configs (stdio).
# The vendor renamed the binary engine-b -> codegraph (v1.5.0); the old path
# no longer exists, so this arm died at startup until fixed.
(CFG_DIR / "engine-b.json").write_text(json.dumps({"mcpServers": {
    "codegraph": {"type": "stdio", "command": str(HOME/".local/bin/codegraph"),
                  "args": ["serve", "--mcp"]}}}))
# Mirrors what `prism init` writes. v0.55.0 added alwaysLoad because cheap
# tiers stopped reaching for deferred tools; the 2026-08-29 ab_deferral A/B
# (9 pairs, haiku) reversed that finding — zero routing losses, recall delta
# +0.004 deferred — so init dropped it and this arm follows. Cells cached
# before this date ran with alwaysLoad; the measured delta between the two
# configs is ~0, but note it when comparing across that boundary.
(CFG_DIR / "prism.json").write_text(json.dumps({"mcpServers": {
    "prism": {"type": "stdio", "command": str(HOME/"bin/prism"), "args": ["mcp"]}}}))

CONTRACT = """
When done, output ONLY a single JSON object, exactly:
{{"sites": ["<relpath>:<Symbol>", ...], "complete": true|false, "unresolved": []}}
Use "<repo-relative-path>:<FunctionOrMethodName>" per site. A missed site is a
broken fix; a false site wastes a review. No prose after the JSON.

ISSUE:
{prompt}
"""

ARMS = {
    "baseline": {
        "guidance": "TOOLS: ripgrep/grep/find and file reads only. Search for the "
                    "symbols, read the code, reason about every site a fix must touch.",
        "allowed": ["Read", "Grep", "Glob", "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)"],
        "mcp": None,
    },
    "engine-b": {
        "guidance": "TOOLS: the Engine B MCP server (its `engine_b_explore` returns "
                    "relevant symbols + call paths + blast radius in one call; also "
                    "`impact`/`callers`). Use it to find every site a change affects.",
        "allowed": ["Read", "mcp__codegraph"],
        "mcp": str(CFG_DIR / "engine-b.json"),
    },
    "prism": {
        "guidance": "TOOLS: the Prism MCP server. `prism_change_impact` returns the "
                    "COMPLETE change-set for a signature change in one call: declaration, "
                    "override/implementation family, and every resolved caller. Report the "
                    "method sites in declarations+family+callers+supers. declaringTypes are "
                    "container context and must not be emitted as separate type-name sites "
                    "under the FunctionOrMethodName answer contract.",
        "allowed": ["Read", "mcp__prism"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
}


def run_arm(arm: str, task: Task, corpus: Path, model: str) -> dict:
    spec = ARMS[arm]
    prompt = spec["guidance"] + "\n" + CONTRACT.format(prompt=task.prompt)
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--strict-mcp-config",
           "--allowedTools", *spec["allowed"]]
    if spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"]]
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=corpus, capture_output=True, text=True, timeout=1200)
    wall = round(time.monotonic() - t0, 1)
    rec = {"arm": arm, "wall_s": wall}
    try:
        j = json.loads(r.stdout)
        rec["turns"] = j.get("num_turns")
        rec["usage"] = usage_account.cli_usage(j)
        u = rec["usage"]["tokens"]
        rec["cost_usd"] = rec["usage"]["cost_usd_cli"]
        # tokens_in kept for older readers; cache CREATION tokens are billed
        # too and were dropped here until 2026-09-05 — all four categories
        # are now recorded separately.
        rec["tokens_in"] = (u["input_uncached"] + u["cache_read"]
                            if u["input_uncached"] is not None and u["cache_read"] is not None else None)
        rec["tokens_out"] = u["output"]
        rec["tokens_uncached"] = u["input_uncached"]
        rec["tokens_cache_write"] = u["cache_creation"]
        rec["tokens_cache_read"] = u["cache_read"]
        # The normalized total every comparison should use (proposal §4.1).
        rec["tokens_request"] = rec["usage"]["input_total"]
        rec["usage_raw"] = rec["usage"]["raw_usage"]
        rec["pricing_basis"] = "claude-cli total_cost_usd"
        rec["session_id"] = j.get("session_id")
        rec["raw_result"] = j
        rec["exit_code"] = r.returncode
        if not rec["usage"]["usage_complete"]:
            rec["measurement_error"] = "missing or invalid final usage"
            rec["error"] = rec["measurement_error"]
        elif r.returncode or j.get("is_error"):
            rec["error"] = f"agent failed: exit={r.returncode}, is_error={j.get('is_error')}"
        answer = Answer.parse(j.get("result", ""))
        _sc = score(task, answer, arm, 1)
        # The parsed answer itself, so a future scorer change can rescore
        # this cell offline instead of paying for it again.
        rec["answer"] = {"sites": [str(s) for s in answer.sites],
                         "complete": answer.complete, "unresolved": answer.unresolved}
        rec["scorer_version"] = SCORER_VERSION
        rec["recall"] = round(_sc.recall, 3)
        rec["weak_recall"] = round(_sc.weak_recall, 3)
        rec["precision"] = round(_sc.precision, 3)
        rec["f1"] = round(_sc.f1, 3)
        rec["n_sites"] = len(answer.sites)
        rec["complete_claim"] = answer.complete
    except Exception as e:
        rec["error"] = str(e)[:200]
        rec["stderr"] = (r.stderr or "")[-300:]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="opus")
    ap.add_argument("--arms", default="baseline,engine-b,prism")
    ap.add_argument("tasks", nargs="+")
    args = ap.parse_args()

    outdir = Path("results/ab-agentic") ; outdir.mkdir(parents=True, exist_ok=True)
    allrows = []
    for tpath in args.tasks:
        task = Task.load(tpath)
        corpus = Path(task.workdir or task.repo)
        if not corpus.exists():
            print(f"SKIP {task.id}: corpus absent {corpus}"); continue
        subprocess.run(["git", "-C", str(corpus), "checkout", "-q", task.pin], capture_output=True)
        print(f"\n== {task.id} ({args.model}) GT={len(task.ground_truth)} ==")
        for arm in args.arms.split(","):
            f = outdir / f"{task.id}.{args.model}.{arm}.json"
            if f.exists():
                rec = json.loads(f.read_text()); print(f"  (cached) ", end="")
            else:
                rec = run_arm(arm, task, corpus, args.model)
                rec["task"] = task.id; rec["model"] = args.model
                f.write_text(json.dumps(rec, indent=2))
            allrows.append(rec)
            if "error" in rec:
                print(f"  {arm:9} ERROR {rec['error'][:80]}")
            else:
                print(f"  {arm:9} recall={rec.get('recall')}  turns={rec.get('turns')}  "
                      f"tok={rec.get('tokens_in',0)//1000}k/{rec.get('tokens_out',0)//1000}k  "
                      f"${rec.get('cost_usd')}  {rec.get('wall_s')}s")
    json.dump(allrows, open(outdir / f"summary.{args.model}.json", "w"), indent=2)
    print(f"\n-> {outdir}/summary.{args.model}.json")


if __name__ == "__main__":
    main()
