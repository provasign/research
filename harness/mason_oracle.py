#!/usr/bin/env python3
"""Oracle-scored mason cells: run mason on a SWE-bench task, then score the
resulting patch against FAIL_TO_PASS / PASS_TO_PASS in the instance's own
official image.

Why this exists (2026-09-07): the local harness had no correctness oracle in
the loop. It was scored by PROCESS proxies -- turns-to-first-graph-tool,
tokens/task, blocked searches, no-ops rejected -- and a measured do-nothing
run maximized every one of them (63.9% token savings, two run_tests calls,
few turns, a one-line edit for a 13-item task, closed as complete). Fourteen
steering items were tuned against that. Nothing asked whether the fix worked.

Discipline this enforces:
  * CONTROLS FIRST. --control scores the gold patch (must resolve) and the
    empty patch (must NOT resolve) before any agent number is believed. A
    task failing either control is unscoreable -- its agent result is
    discarded, not reported. (docker_eval's own history: 17 of 38 tasks were
    unscoreable on the hand-rolled image path, every one a build problem
    rather than a bad task, which is why score_official is used here.)
  * The agent worktree NEVER sees the gold patch or the test patch. Scoring
    happens in a separate container over a throwaway checkout.
  * The .grove index is excluded from the scored diff -- a stale artifact in
    the patch zeroed every Prism score once already (2026-07-14).

Usage:
  python3 mason_oracle.py --task dynaconf__dynaconf-1225 --control
  python3 mason_oracle.py --task dynaconf__dynaconf-1225 \
      --mason /tmp/mason-bench --model ollama:qwen2.5-coder:14b --trials 3
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import docker_eval
import static_oracle
import swebench_ab as ab

HARNESS = Path(__file__).resolve().parent
TASK_POOLS = [
    HARNESS / "runs" / "swebench-live" / "live-lite-300.json",
    HARNESS / "runs" / "swebench-live" / "slice-radius.json",
]
WT_ROOT = Path("/tmp/swebench-wt")
# Never let mason's own index, session store, or steering land in the scored
# diff. `.shale` was caught by static_oracle listing the agent's changed
# files on the very first scored cell (2026-09-07): mason's session JSONL was
# being committed into the patch under evaluation. The same class of leak
# (a .grove index inside agent diffs) zeroed every Prism score once before,
# so this list is checked against agent_files on every run, not assumed.
FOOTPRINT = [".grove", ".shale", ".mcp.json", "MASON.md", "CLAUDE.md",
             "AGENTS.md", "GEMINI.md"]


def load_task(instance_id: str) -> dict:
    for pool in TASK_POOLS:
        if not pool.exists():
            continue
        for t in json.loads(pool.read_text()):
            if isinstance(t, dict) and t.get("instance_id") == instance_id:
                if not t.get("FAIL_TO_PASS"):
                    raise SystemExit(f"{instance_id} in {pool.name} carries no FAIL_TO_PASS")
                return t
    raise SystemExit(f"{instance_id} not found in any task pool")


def controls(task: dict) -> dict:
    """Gold must resolve; empty must not. Anything else = unscoreable task."""
    t0 = time.time()
    gold = docker_eval.score_official(task, task["patch"])
    empty = docker_eval.score_official(task, "")
    ok = bool(gold.get("resolved")) and not empty.get("resolved")
    return {"gold": gold, "empty": empty, "scoreable": ok,
            "secs": round(time.time() - t0, 1)}


def agent_worktree(task: dict) -> Path:
    """A clean checkout at base_commit -- no gold, no test patch, no prism
    leftovers. The agent sees only the buggy source."""
    repo = ab.ensure_repo(task["repo"])
    wt = WT_ROOT / f"{task['instance_id']}.oracle"
    if wt.exists():
        ab.sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)
    WT_ROOT.mkdir(parents=True, exist_ok=True)
    ab.sh("git", "-C", str(repo), "worktree", "add", "--force", "--detach",
          str(wt), task["base_commit"], timeout=300)
    head = ab.sh("git", "-C", str(wt), "rev-parse", "HEAD").stdout.strip()
    if head != task["base_commit"]:
        raise RuntimeError(f"worktree at {head}, expected {task['base_commit']}")
    ab.sanitize_worktree(wt, "mason")
    return wt


def patch_files_all(patch: str) -> set[str]:
    """Every file in a diff, docs and dotfiles included — the leak check must
    see exactly what the scored patch carries, not the filtered source view."""
    return static_oracle.patch_files(patch, source_only=False)


def agent_patch(wt: Path) -> str:
    """The agent's edits to the PROJECT only. Intent-to-add first so a fix
    whose shape is 'create a new module' keeps its new file in the diff."""
    ex = [f":(exclude){p}" for p in FOOTPRINT]
    ab.sh("git", "-C", str(wt), "add", "-N", "--", ".", *ex)
    return ab.sh("git", "-C", str(wt), "diff", "--", ".", *ex).stdout


# Process metrics, kept ALONGSIDE the verdict so a cheap run that solves
# nothing can never again look like a win.
GUARD_RES = {
    "unverified": re.compile(r"UNVERIFIED|change is NOT verified", re.I),
    "hands_back": re.compile(r"hands commands back to the user", re.I),
    "fabrication": re.compile(r"claimed test success contradicts", re.I),
    "incomplete_diff": re.compile(r"diff is INCOMPLETE", re.I),
    "no_change": re.compile(r"asked for a change but no file was modified", re.I),
}
USAGE_RE = re.compile(r"usage:\s*(\d+)\s*in\s*/\s*(\d+)\s*out")


def run_cell(task: dict, mason_bin: str, model: str, prompt: str, timeout: int) -> dict:
    wt = agent_worktree(task)
    t0 = time.time()
    p = subprocess.run([mason_bin, "--dir", str(wt), "--model", model,
                        "--yes", "--no-tui", prompt],
                       capture_output=True, text=True, timeout=timeout)
    secs = round(time.time() - t0, 1)
    log = p.stdout + p.stderr
    patch = agent_patch(wt)
    m = USAGE_RE.search(log)
    return {
        "secs": secs, "exit": p.returncode,
        "tokens_in": int(m.group(1)) if m else None,
        "tokens_out": int(m.group(2)) if m else None,
        "patch_bytes": len(patch),
        "tool_calls": len(re.findall(r"^  [·$✎]", log, re.M)),
        "guards": {k: bool(r.search(log)) for k, r in GUARD_RES.items()},
        "_patch": patch, "_log": log,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--control", action="store_true",
                    help="score gold + empty and exit (run this FIRST)")
    ap.add_argument("--mason", default="/tmp/mason-bench")
    ap.add_argument("--model", default="ollama:qwen2.5-coder:14b")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out", default=str(HARNESS / "runs" / "mason-oracle"))
    ap.add_argument("--no-docker", action="store_true",
                    help="static scoring only; never invoke the test oracle")
    a = ap.parse_args()

    task = load_task(a.task)
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ctl_path = out_dir / f"{a.task}.control.json"
    if a.no_docker and not ctl_path.exists():
        # The gold/empty control is the ONE place the container genuinely
        # earns its keep: it proves the task's verdicts mean anything. Static
        # scoring can still classify the failure bucket without it, so this
        # is a warning rather than a refusal -- but a `plausible` bucket is
        # then an unconfirmed guess, and is reported as exactly that.
        print(f"[warn] {a.task}: no validated control on file and --no-docker "
              f"given; failure buckets are still valid, but nothing here can "
              f"confirm a fix actually resolves the task.", flush=True)
    elif a.control or not ctl_path.exists():
        print(f"[control] {a.task}: scoring gold and empty patches…", flush=True)
        ctl = controls(task)
        ctl_path.write_text(json.dumps(ctl, indent=2))
        print(json.dumps(ctl, indent=2), flush=True)
        if not ctl["scoreable"]:
            raise SystemExit(
                "UNSCOREABLE: gold did not resolve or empty did resolve — "
                "no agent number from this task is meaningful.")
        print("[control] OK: gold resolves, empty does not.", flush=True)
        if a.control:
            return
    elif not json.loads(ctl_path.read_text())["scoreable"]:
        raise SystemExit(f"{a.task} is recorded UNSCOREABLE — fix the task, not the agent.")

    prompt = ab.BASE_PROMPT.format(repo=task["repo"],
                                   problem=task["problem_statement"], steer="")
    for i in range(a.trials):
        print(f"[trial {i+1}/{a.trials}] running mason…", flush=True)
        cell = run_cell(task, a.mason, a.model, prompt, a.timeout)
        # Static classification FIRST: it decides the failure bucket for free
        # and, for everything except `plausible`, is already conclusive --
        # an empty patch or a 7%-coverage edit does not need a container to
        # be known as unresolved. Cross-validated 2026-09-07 against the
        # official image on this very task: both said not-resolved, and the
        # static side additionally named the cause (shallow) and caught a
        # .shale leak the container silently applied.
        static = static_oracle.classify(task, cell["_patch"], cell["_log"])
        leaked = [f for f in patch_files_all(cell["_patch"])
                  if any(f == p or f.startswith(p + "/") for p in FOOTPRINT)]
        if leaked:
            print(f"  !! harness footprint leaked into the scored patch: {leaked}", flush=True)
        if static["needs_execution"] and not a.no_docker:
            verdict = docker_eval.score_official(task, cell["_patch"])
        else:
            verdict = {"resolved": False, "by": "static",
                       "reason": f"bucket={static['bucket']} "
                                 f"coverage={static['coverage']} size_ratio={static['size_ratio']}"}
        rec = {"instance_id": a.task, "model": a.model, "trial": i + 1,
               **{k: v for k, v in cell.items() if not k.startswith("_")},
               "static": static, "score": verdict}
        (out_dir / f"{a.task}.t{i+1}.json").write_text(json.dumps(rec, indent=2))
        (out_dir / f"{a.task}.t{i+1}.patch").write_text(cell["_patch"])
        (out_dir / f"{a.task}.t{i+1}.log").write_text(cell["_log"])
        print(json.dumps({"trial": rec["trial"], "secs": rec["secs"],
                          "tokens_in": rec["tokens_in"], "bucket": static["bucket"],
                          "coverage": static["coverage"], "size_ratio": static["size_ratio"],
                          "files_hit": static["files_hit"], "flags": static["flags"],
                          "score": rec["score"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
