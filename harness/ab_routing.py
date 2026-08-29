#!/usr/bin/env python3
"""R0: field-condition routing measurement on the fanout bed.

Each cell: throwaway worktree at the task's base_commit, set up EXACTLY like
a real prism repo (the generated CLAUDE.md steering block + .mcp.json — no
arm coaching), bare task prompt, agent edits freely. Measured per cell:

  - prism routing: per-tool calls, diffed from prism's own ledger around
    the cell (the v0.56.8 instrumentation; claude CLI summaries cannot
    say which tools ran)
  - completeness: gold-file recall of the agent's non-test diff vs the
    merged PR's gold_files (docs/changelog excluded)
  - cost: tokens_in, turns

Arms: field-prism (steering + MCP) vs field-bare (no prism, no steering).
Usage: python ab_routing.py --prism ~/bin/prism [--model haiku]
       [--seeds 2] [--tasks tasks-e2e-fanout/*.json] [--steering FILE]
--steering swaps the injected block (R1 variants) — file path or 'generated'.
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_deferral  # ledger_path/tool_calls  # noqa: E402

HARNESS = Path(__file__).resolve().parent
REPO_CACHE = Path.home() / ".cache" / "prism-research" / "routing-repos"
WT_ROOT = Path("/tmp/routing-wt")
RUN_TIMEOUT_S = 1200

SKIP_GOLD = ("CHANGES", "CHANGELOG", "docs/", ".rst", ".md")


def sh(*args, cwd=None, timeout=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def ensure_repo(owner_name: str) -> Path:
    d = REPO_CACHE / owner_name.replace("/", "__")
    if not (d / ".git" / "HEAD").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        r = sh("git", "clone", "--filter=blob:none",
               f"https://github.com/{owner_name}.git", str(d), timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"clone {owner_name}: {r.stderr[-300:]}")
    return d


def generated_steering(prism: str) -> str:
    """The exact block `prism init` writes, extracted from a scratch init."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sh("git", "init", "-q", td)
        Path(td, "main.py").write_text("x = 1\n")
        subprocess.run([prism, "init", td], input="n\n", capture_output=True,
                       text=True, timeout=120)
        return Path(td, "CLAUDE.md").read_text()


def make_worktree(repo: Path, base: str, tag: str) -> Path:
    wt = WT_ROOT / tag
    sh("git", "-C", str(repo), "worktree", "remove", "-f", str(wt))
    sh("git", "-C", str(repo), "fetch", "-q", "origin", base, timeout=300)
    r = sh("git", "-C", str(repo), "worktree", "add", "-f", str(wt), base,
           timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"worktree: {r.stderr[-300:]}")
    return wt


def gold_code_files(task: dict) -> set:
    files = task["gold_files"]
    if isinstance(files, str):
        files = json.loads(files.replace("'", '"'))
    return {f for f in files
            if not any(s in f for s in SKIP_GOLD)}


def changed_files(wt: Path) -> set:
    r = sh("git", "-C", str(wt), "diff", "--name-only")
    return {l for l in r.stdout.splitlines() if l.strip()}


def run_cell(task: dict, arm: str, prism: str, model: str, seed: int,
             steering: str, out: Path) -> dict:
    cell_id = f"{task['instance_id']}.{arm}.{model}.s{seed}"
    f = out / (cell_id + ".json")
    if f.exists():
        return json.loads(f.read_text())

    repo = ensure_repo(task["repo"])
    wt = make_worktree(repo, task["base_commit"], cell_id)
    rec = {"cell": cell_id, "arm": arm, "model": model, "seed": seed}
    try:
        allowed = ["Read", "Edit", "Write", "Grep", "Glob",
                   "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)",
                   "Bash(ls:*)", "Bash(cat:*)"]
        # Same edit contract run_e2e uses for every arm — task framing, not
        # tool coaching. Without it -p agents investigate and report instead
        # of editing (probe: 4 prism calls, 5 turns, zero files changed).
        prompt = (task["problem_statement"]
                  + "\n\nFix this issue by EDITING the repository files. Make the"
                    " complete change the issue requires — every affected file —"
                    " then stop. Do not just describe the fix.")
        cmd = ["claude", "-p", prompt,
               "--model", model, "--output-format", "json",
               "--dangerously-skip-permissions", "--strict-mcp-config"]
        if arm == "field-prism":
            (wt / "CLAUDE.md").write_text(steering)
            cfg = wt / ".mcp-routing.json"
            cfg.write_text(json.dumps({"mcpServers": {"prism": {
                "type": "stdio", "command": str(Path(prism).resolve()),
                "args": ["mcp"]}}}))
            sh(prism, "index", str(wt), timeout=900)
            cmd += ["--mcp-config", str(cfg),
                    "--allowedTools", *allowed, "mcp__prism"]
        else:
            cmd += ["--allowedTools", *allowed]

        before = ab_deferral.tool_calls(wt)
        t0 = time.monotonic()
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True,
                           timeout=RUN_TIMEOUT_S)
        rec["wall_s"] = round(time.monotonic() - t0, 1)
        after = ab_deferral.tool_calls(wt)
        rec["prism_calls"] = {t: after.get(t, 0) - before.get(t, 0)
                              for t in after
                              if after.get(t, 0) > before.get(t, 0)}
        try:
            j = json.loads(r.stdout)
            rec["turns"] = j.get("num_turns")
            rec["cost_usd"] = j.get("total_cost_usd")
            u = j.get("usage", {}) or {}
            rec["tokens_in"] = (u.get("input_tokens", 0)
                                + u.get("cache_read_input_tokens", 0))
        except Exception as e:
            rec["error"] = f"cli-parse: {e}"[:200]

        gold = gold_code_files(task)
        got = {c for c in changed_files(wt) if c != "CLAUDE.md"}
        rec["gold_files"] = sorted(gold)
        rec["changed_files"] = sorted(got)
        rec["gold_recall"] = round(len(gold & got) / len(gold), 3) if gold else None
        rec["extra_files"] = len(got - gold)
    finally:
        sh("git", "-C", str(repo), "worktree", "remove", "-f", str(wt))
    f.write_text(json.dumps(rec, indent=2))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prism", required=True)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--tasks", default="tasks-e2e-fanout/*.json")
    ap.add_argument("--arms", nargs="+",
                    default=["field-prism", "field-bare"])
    ap.add_argument("--steering", default="generated")
    ap.add_argument("--out", default="runs/ab-routing")
    ap.add_argument("--limit", type=int, default=99)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    steering = (generated_steering(args.prism) if args.steering == "generated"
                else Path(args.steering).read_text())

    for tp in sorted(glob.glob(str(HARNESS / args.tasks)))[: args.limit]:
        task = json.loads(Path(tp).read_text())
        for seed in range(1, args.seeds + 1):
            for arm in args.arms:
                rec = run_cell(task, arm, args.prism, args.model, seed,
                               steering, out)
                calls = rec.get("prism_calls") or {}
                ci = calls.get("prism_change_impact", 0)
                print(f"{rec['cell']:55} gold_recall={rec.get('gold_recall')} "
                      f"extra={rec.get('extra_files')} "
                      f"prism_calls={sum(calls.values())} (change_impact={ci}) "
                      f"turns={rec.get('turns')} "
                      f"err={str(rec.get('error',''))[:60]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
