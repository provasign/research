"""Agentic A/B: does CodeGraph actually cut tool calls / tokens / time — and at
what CORRECTNESS? Same agent (claude -p), same task, three arms differing ONLY
in the tool available:

  baseline  — grep/read only            (CodeGraph's claim is 'fewer calls than this')
  codegraph — CodeGraph MCP (explore/impact/callers)
  prism     — Prism MCP (change_impact)

Per arm we record recall (oracle-scored — the headline), num_turns (tool-call
proxy), tokens, cost, wall_s. Correctness first: a cheaper wrong answer loses.

Usage:  python ab_agentic_mcp.py --model opus  tasks/jackson-jsonnode-get.json ...
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from schema import Answer, Task
from score import score

HOME = Path.home()
CFG_DIR = Path("/tmp/ab-agentic-mcp")
CFG_DIR.mkdir(exist_ok=True)

# MCP server configs (stdio).
(CFG_DIR / "codegraph.json").write_text(json.dumps({"mcpServers": {
    "codegraph": {"type": "stdio", "command": str(HOME/".local/bin/codegraph"), "args": ["serve", "--mcp"]}}}))
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
    "codegraph": {
        "guidance": "TOOLS: the CodeGraph MCP server (its `codegraph_explore` returns "
                    "relevant symbols + call paths + blast radius in one call; also "
                    "`impact`/`callers`). Use it to find every site a change affects.",
        "allowed": ["Read", "mcp__codegraph"],
        "mcp": str(CFG_DIR / "codegraph.json"),
    },
    "prism": {
        "guidance": "TOOLS: the Prism MCP server. `prism_change_impact` returns the "
                    "COMPLETE change-set for a signature change in one call: declaration, "
                    "override/implementation family, and every resolved caller. Union its "
                    "groups (declarations+family+callers+declaringTypes) into your sites.",
        "allowed": ["Read", "mcp__prism"],
        "mcp": str(CFG_DIR / "prism.json"),
    },
}


def run_arm(arm: str, task: Task, corpus: Path, model: str) -> dict:
    spec = ARMS[arm]
    prompt = spec["guidance"] + "\n" + CONTRACT.format(prompt=task.prompt)
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--allowedTools", *spec["allowed"]]
    if spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"], "--strict-mcp-config"]
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=corpus, capture_output=True, text=True, timeout=1200)
    wall = round(time.monotonic() - t0, 1)
    rec = {"arm": arm, "wall_s": wall}
    try:
        j = json.loads(r.stdout)
        rec["turns"] = j.get("num_turns")
        rec["cost_usd"] = j.get("total_cost_usd")
        u = j.get("usage", {}) or {}
        rec["tokens_in"] = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        rec["tokens_out"] = u.get("output_tokens", 0)
        answer = Answer.parse(j.get("result", ""))
        _sc = score(task, answer, arm, 1)
        rec["recall"] = round(_sc.recall, 3)
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
    ap.add_argument("--arms", default="baseline,codegraph,prism")
    ap.add_argument("tasks", nargs="+")
    args = ap.parse_args()

    outdir = Path("runs/ab-agentic") ; outdir.mkdir(parents=True, exist_ok=True)
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
