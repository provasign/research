#!/usr/bin/env python3
"""SWE-bench A/B: does prism make an agent fix real issues cheaper/faster at
EQUAL correctness? Real GitHub issues, the fixing PR's tests as the oracle.

Two arms per task, identical except for prism availability:
  no-prism : Read/Edit/Write + shell (grep/find/git). Plain agent baseline.
  prism    : the same, PLUS the prism CLI (pre-indexed) and its steering block.

Correctness is judged by the SWE-bench test oracle (FAIL_TO_PASS must flip to
pass, PASS_TO_PASS must stay pass) — so "equivalent fix" means "clears the same
objective bar", not "textually identical". Only tasks BOTH arms resolve (or the
resolve-rate itself) are the correctness comparison; turns/tokens/cost are the
efficiency comparison, fair because both cleared the same oracle.

This runner produces predictions.jsonl per arm + a metrics record per task. The
CORRECTNESS eval is the standard SWE-bench harness and needs Docker:

  python -m swebench.harness.run_evaluation \
      --predictions_path runs/swebench/<arm>.predictions.jsonl \
      --run_id prism-ab-<arm> --dataset_name princeton-nlp/SWE-bench_Verified

Usage:
  python swebench_ab.py --tasks /tmp/swebench_slice.json --limit 20 \
      --arms no-prism prism --out runs/swebench --prism ~/bin/prism
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
REPO_CACHE = Path("/tmp/swebench-repos")
WT_ROOT = Path("/tmp/swebench-wt")
RUN_TIMEOUT_S = 1800

# The prism CLI steering block, kept in sync with prism's own `init` output —
# the agent sees the same guidance a real prism user gets.
PRISM_STEERING = """
You also have the `prism` code-intelligence CLI (Bash, --format text). Prefer it
over raw grep/read to find and read code cheaply:
  prism query "<what you're looking for>" --terms a,b --include graph,tests --format text   # callers/callees/tests of a symbol
  prism lookup <pkg.Symbol> --format text     # one symbol's body (~5x cheaper than reading the file)
  prism read <file> --format text             # whole file, session-compressed on repeat reads
  prism change-impact 'Type.method' --format text   # every site a signature change must touch, in one call
A repeat `prism read` of an unchanged file returns a `// [prism:cached]` pointer,
not the body — you already have it; do not re-fetch. Use shell grep only to find
an anchor, then let prism expand from it.
"""

BASE_PROMPT = """You are fixing a real bug in the {repo} repository, checked out at the
commit where the bug exists. Read the issue, find the cause in the code, and EDIT
the source files to fix it. Do not write a new test; the project's own test suite
will judge your fix. Make the smallest change that resolves the issue.

ISSUE:
{problem}

When done, stop — your edits to the working tree are the submission.{steer}"""

TOOLS_BASE = ["Read", "Edit", "Write", "Glob", "Grep",
              "Bash(git:*)", "Bash(grep:*)", "Bash(rg:*)", "Bash(find:*)",
              "Bash(cat:*)", "Bash(ls:*)", "Bash(sed:*)", "Bash(head:*)",
              "Bash(tail:*)", "Bash(python:*)", "Bash(python3:*)"]


def sh(*args, cwd=None, timeout=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def ensure_repo(repo: str) -> Path:
    """Clone `owner/name` once (blobless) into the cache."""
    dest = REPO_CACHE / repo.replace("/", "__")
    if not dest.exists():
        REPO_CACHE.mkdir(parents=True, exist_ok=True)
        sh("git", "clone", "--filter=blob:none", "--quiet",
           f"https://github.com/{repo}.git", str(dest))
    return dest


def parse_stream(stdout: str) -> dict:
    env = {"result": ""}
    trace = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "assistant":
            for b in obj.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    cmd = b.get("input", {}).get("command", "") if name == "Bash" else ""
                    trace.append(cmd[:120] if cmd else name)
        elif obj.get("type") == "result":
            env.update(obj)
    env["tool_trace"] = trace
    env["prism_used"] = any("prism" in t for t in trace)
    return env


def run_agent(prompt: str, tools: list[str], workdir: Path) -> dict:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--allowedTools", ",".join(tools)]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(workdir), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=RUN_TIMEOUT_S)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        out, err = proc.communicate()
        timed_out = True
    env = parse_stream(out)
    env["_wall_s"] = round(time.time() - t0, 1)
    env["_timed_out"] = timed_out
    return env


def run_arm(task: dict, arm: str, prism: str) -> dict:
    """Check out the task's repo at base_commit, run the agent, capture the
    patch (git diff of its edits) + efficiency metrics."""
    repo_dir = ensure_repo(task["repo"])
    wt = WT_ROOT / f"{task['instance_id']}__{arm}"
    WT_ROOT.mkdir(parents=True, exist_ok=True)
    sh("git", "-C", str(repo_dir), "worktree", "prune")
    sh("git", "-C", str(repo_dir), "worktree", "add", "--detach", "-f",
       str(wt), task["base_commit"])
    try:
        steer = ""
        tools = list(TOOLS_BASE)
        if arm == "prism":
            sh(prism, "index", ".", cwd=str(wt), timeout=600)
            tools += [f"Bash(prism:*)", f"Bash({prism}:*)"]
            steer = "\n" + PRISM_STEERING
        prompt = BASE_PROMPT.format(repo=task["repo"], problem=task["problem_statement"],
                                    steer=steer)
        env = run_agent(prompt, tools, wt)
        # The prediction patch = the agent's edits (exclude the .grove index).
        patch = sh("git", "-C", str(wt), "diff", "--", ".", ":(exclude).grove").stdout
        usage = env.get("usage") or {}
        return {
            "instance_id": task["instance_id"], "arm": arm,
            "model_patch": patch,
            "empty_patch": not patch.strip(),
            "turns": env.get("num_turns"),
            "input_tokens": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": env.get("total_cost_usd"),
            "wall_s": env.get("_wall_s"),
            "timed_out": env.get("_timed_out"),
            "prism_used": env.get("prism_used"),
        }
    finally:
        sh("git", "-C", str(repo_dir), "worktree", "remove", "--force", str(wt))


def fetch_tasks(out: str, n: int) -> None:
    """Pull a repo-diverse slice of SWE-bench Verified via the HF
    datasets-server API (no `datasets` package needed)."""
    import urllib.request
    rows, offsets = [], list(range(0, 500, max(1, 500 // max(n // 8, 1))))
    for off in offsets:
        url = ("https://datasets-server.huggingface.co/rows?dataset="
               "princeton-nlp%2FSWE-bench_Verified&config=default&split=test"
               f"&offset={off}&length=10")
        try:
            d = json.load(urllib.request.urlopen(url, timeout=30))
            rows += [r["row"] for r in d.get("rows", [])]
        except Exception as e:
            print("skip", off, e)
        time.sleep(0.3)
    json.dump(rows, open(out, "w"))
    from collections import Counter
    print(f"fetched {len(rows)} tasks -> {out}")
    for repo, c in Counter(r["repo"] for r in rows).most_common():
        print(f"  {repo}: {c}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", type=int, metavar="N",
                    help="fetch N SWE-bench Verified tasks to --tasks and exit")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--arms", nargs="+", default=["no-prism", "prism"])
    ap.add_argument("--out", default="runs/swebench")
    ap.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    args = ap.parse_args()

    if args.fetch:
        fetch_tasks(args.tasks, args.fetch)
        return

    tasks = json.load(open(args.tasks))[:args.limit]
    outdir = HARNESS / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    preds = {a: open(outdir / f"{a}.predictions.jsonl", "w") for a in args.arms}
    metrics = {a: [] for a in args.arms}

    for i, task in enumerate(tasks):
        for arm in args.arms:
            print(f"[{i+1}/{len(tasks)}] {task['instance_id']} :: {arm}", flush=True)
            rec = run_arm(task, arm, args.prism)
            metrics[arm].append(rec)
            preds[arm].write(json.dumps({
                "instance_id": rec["instance_id"],
                "model_name_or_path": f"prism-ab-{arm}",
                "model_patch": rec["model_patch"],
            }) + "\n")
            preds[arm].flush()
            json.dump(rec, open(outdir / f"{task['instance_id']}.{arm}.json", "w"))
            print(f"      turns={rec['turns']} in_tok={rec['input_tokens']} "
                  f"out_tok={rec['output_tokens']} ${rec['cost_usd']} "
                  f"empty={rec['empty_patch']} prism_used={rec['prism_used']}", flush=True)

    for f in preds.values():
        f.close()

    print("\n" + "=" * 66)
    print(f"{'arm':10} {'n':>3} {'nonempty':>9} {'mean_turns':>11} "
          f"{'mean_in_tok':>12} {'mean_out_tok':>13} {'mean_$':>8}")
    for arm in args.arms:
        m = [r for r in metrics[arm] if not r["timed_out"]]
        if not m:
            continue
        ne = sum(1 for r in m if not r["empty_patch"])
        mt = sum(r["turns"] or 0 for r in m) / len(m)
        mi = sum(r["input_tokens"] for r in m) / len(m)
        mo = sum(r["output_tokens"] for r in m) / len(m)
        mc = sum(r["cost_usd"] or 0 for r in m) / len(m)
        print(f"{arm:10} {len(m):>3} {ne:>9} {mt:>11.1f} {mi:>12.0f} {mo:>13.0f} {mc:>8.3f}")
    print("\nNext: score correctness with the SWE-bench Docker harness on each")
    print("arm's predictions.jsonl (FAIL_TO_PASS/PASS_TO_PASS). Efficiency is only")
    print("comparable at EQUAL resolve-rate — report resolve-rate FIRST.")


if __name__ == "__main__":
    main()
