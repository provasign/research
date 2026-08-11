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
import re
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
# Matched-arm design (per RESULTS.md §8.2.1 finding #4: arm comparisons need
# MATCHED steering or the tool effect is unmeasurable). BOTH arms receive
# INVESTIGATION_GUIDANCE verbatim; the prism arm additionally receives
# PRISM_STEERING, which is a purely DESCRIPTIVE tool reference — no workflow
# doctrine, no request-pricing mandate. The arms differ in tool availability
# and tool documentation only.
INVESTIGATION_GUIDANCE = """
Investigation discipline (applies regardless of which tools you use):
- Where an error is raised is where the bug SURFACES, not necessarily where it
  lives. Before deciding where to edit, read the WHOLE file that defines the
  failing behavior, not just the lines a search hit.
- Before finishing, run the tests for the module the issue is about, not only
  the tests nearest the code you edited.
- Make the smallest change that resolves the issue; do not restructure
  neighboring code the issue does not require.
"""

# FAITHFUL DEPLOYMENT ARM (2026-08-11). The shipped prism deployment routes
# STRUCTURALLY: prism init's deny-builtin-search puts Grep/Bash(grep|rg) in
# permissions.deny (active on this machine), and the steering the agent sees
# is the init-GENERATED block, not harness-authored prose. The prism arm
# therefore (a) removes the built-in search tools and (b) injects the real
# generated steering verbatim, read from the prism repo's AGENTS.md at run
# time so it can never drift from what init writes.
SEARCH_TOOLS = {"Grep", "Bash(grep:*)", "Bash(rg:*)"}


MCP_CFG = Path("/tmp/ab-swebench")
MCP_CFG.mkdir(exist_ok=True)
(MCP_CFG / "prism.json").write_text(json.dumps({"mcpServers": {
    "prism": {"type": "stdio", "command": str(Path.home() / "bin/prism"), "args": ["mcp"]}}}))


def real_prism_steering() -> str:
    src = Path.home() / "Projects/provasign/prism/AGENTS.md"
    text = src.read_text()
    end = text.find("<!-- prism:end -->")
    return text[:end].strip() if end >= 0 else text.strip()

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
    # Detect an actual prism INVOCATION (the binary run as a command), not the
    # substring "prism" anywhere — the worktree path could contain it. Matches
    # `prism ...` or `/path/to/prism ...`, not an unrelated path segment.
    env["prism_used"] = any(re.search(r"(?:^|[\s;&|(])(?:[^\s;&|(]*/)?prism\s", t)
                            for t in trace)
    return env


def run_agent(prompt: str, tools: list[str], workdir: Path, model: str = "",
              mcp: str = "") -> dict:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--allowedTools", ",".join(tools)]
    if mcp:
        cmd += ["--mcp-config", mcp]
    if model:
        cmd += ["--model", model]
    t0 = time.time()
    # GIT_ALLOW_PROTOCOL=file: git stays fully usable locally but cannot fetch
    # over the network. Audit of trials 1-2 caught agents running
    # `git fetch origin refs/pull/<N>/head` to pull the GOLD fix (the instance
    # id leaks the PR number); gh/curl were already blocked by the allowlist,
    # git was the remaining hole. Applies identically to both arms.
    env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file"}
    proc = subprocess.Popen(cmd, cwd=str(workdir), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True,
                            env=env)
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


def run_arm(task: dict, arm: str, prism: str, model: str = "") -> dict:
    """Check out the task's repo at base_commit, run the agent, capture the
    patch (git diff of its edits) + efficiency metrics."""
    repo_dir = ensure_repo(task["repo"])
    wt = WT_ROOT / f"{task['instance_id']}__{arm}"
    WT_ROOT.mkdir(parents=True, exist_ok=True)
    sh("git", "-C", str(repo_dir), "worktree", "prune")
    sh("git", "-C", str(repo_dir), "worktree", "add", "--detach", "-f",
       str(wt), task["base_commit"])
    try:
        steer = "\n" + INVESTIGATION_GUIDANCE
        tools = list(TOOLS_BASE)
        if arm == "prism":
            sh(prism, "index", ".", cwd=str(wt), timeout=600)
            # Faithful deployment: built-in search denied, prism is the
            # search path (scope="text" is the ripgrep passthrough).
            tools = [t for t in tools if t not in SEARCH_TOOLS]
            tools += [f"Bash(prism:*)", f"Bash({prism}:*)", "mcp__prism"]
            steer += "\n" + real_prism_steering()
        prompt = BASE_PROMPT.format(repo=task["repo"], problem=task["problem_statement"],
                                    steer=steer)
        env = run_agent(prompt, tools, wt, model,
                        mcp=str(MCP_CFG / "prism.json") if arm == "prism" else "")
        # The prediction patch = the agent's edits (exclude the .grove index).
        patch = sh("git", "-C", str(wt), "diff", "--", ".", ":(exclude).grove").stdout
        usage = env.get("usage") or {}
        return {
            "instance_id": task["instance_id"], "arm": arm,
            "model_patch": patch,
            "empty_patch": not patch.strip(),
            "turns": env.get("num_turns"),
            # Fresh (billed-at-full) input vs cheap cache reads, kept separate —
            # cache reads dominate and would distort a raw "input tokens" total;
            # cost_usd is the honest efficiency metric (it weights them correctly).
            "fresh_input_tokens": usage.get("input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": env.get("total_cost_usd"),
            "wall_s": env.get("_wall_s"),
            "timed_out": env.get("_timed_out"),
            "prism_used": env.get("prism_used"),
            "tool_trace": env.get("tool_trace", []),
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
    # "baseline" not "no-prism": the arm name becomes a worktree dir, and
    # "no-prism" contains the substring "prism" which fooled usage detection.
    ap.add_argument("--arms", nargs="+", default=["baseline", "prism"])
    ap.add_argument("--out", default="runs/swebench")
    ap.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    ap.add_argument("--model", default="opus")
    args = ap.parse_args()

    if args.fetch:
        fetch_tasks(args.tasks, args.fetch)
        return

    tasks = json.load(open(args.tasks))[:args.limit]
    outdir = HARNESS / args.out
    outdir.mkdir(parents=True, exist_ok=True)

    # Idempotent resume: per-task metric JSONs are the source of truth and
    # survive a kill. Skip any (task, arm) already recorded; a re-launch picks
    # up exactly where a turn-boundary kill left off, re-paying for nothing.
    for i, task in enumerate(tasks):
        for arm in args.arms:
            recpath = outdir / f"{task['instance_id']}.{arm}.json"
            if recpath.exists():
                print(f"[{i+1}/{len(tasks)}] {task['instance_id']} :: {arm}  SKIP (done)", flush=True)
                continue
            print(f"[{i+1}/{len(tasks)}] {task['instance_id']} :: {arm}", flush=True)
            rec = run_arm(task, arm, args.prism, args.model)
            json.dump(rec, open(recpath, "w"))
            print(f"      turns={rec['turns']} fresh_in={rec['fresh_input_tokens']} "
                  f"cache={rec['cache_read_tokens']} out={rec['output_tokens']} "
                  f"${rec['cost_usd']} empty={rec['empty_patch']} prism_used={rec['prism_used']}",
                  flush=True)

    # Rebuild predictions.jsonl from all present metric JSONs (kill-safe).
    metrics = {a: [] for a in args.arms}
    for arm in args.arms:
        with open(outdir / f"{arm}.predictions.jsonl", "w") as pf:
            for task in tasks:
                rp = outdir / f"{task['instance_id']}.{arm}.json"
                if not rp.exists():
                    continue
                rec = json.load(open(rp))
                metrics[arm].append(rec)
                pf.write(json.dumps({
                    "instance_id": rec["instance_id"],
                    "model_name_or_path": f"prism-ab-{arm}",
                    "model_patch": rec["model_patch"],
                }) + "\n")

    print("\n" + "=" * 74)
    print(f"{'arm':10} {'n':>3} {'nonempty':>9} {'mean_turns':>11} "
          f"{'mean_fresh':>11} {'mean_out':>9} {'mean_$':>8} {'prism%':>7}")
    for arm in args.arms:
        m = [r for r in metrics[arm] if not r["timed_out"]]
        if not m:
            continue
        ne = sum(1 for r in m if not r["empty_patch"])
        mt = sum(r["turns"] or 0 for r in m) / len(m)
        mf = sum(r["fresh_input_tokens"] for r in m) / len(m)
        mo = sum(r["output_tokens"] for r in m) / len(m)
        mc = sum(r["cost_usd"] or 0 for r in m) / len(m)
        pu = 100 * sum(1 for r in m if r["prism_used"]) / len(m)
        print(f"{arm:10} {len(m):>3} {ne:>9} {mt:>11.1f} {mf:>11.0f} {mo:>9.0f} {mc:>8.3f} {pu:>6.0f}%")
    print("\nNext: score correctness with the SWE-bench Docker harness on each")
    print("arm's predictions.jsonl (FAIL_TO_PASS/PASS_TO_PASS). Efficiency is only")
    print("comparable at EQUAL resolve-rate — report resolve-rate FIRST.")


if __name__ == "__main__":
    main()
