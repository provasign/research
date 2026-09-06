#!/usr/bin/env python3
"""Verification bed: does `prism verify` name the sites an incomplete diff
missed — and never call an incomplete diff complete?

No LLM. Each trial takes a wide-bed task (real upstream commit, gold diff
known), builds the isolated worktree at base, applies gold to every changed
file EXCEPT a held-out set, indexes, runs `prism verify`, and scores:

  named          held-out files that verify's missedSites point into
  false_complete verdict == "complete" while something IS held out
  false_accuse   missedSites in files that are already gold-complete
  complete-case  holdout = {} — the verdict must not accuse anything

Trials per task: the complete case, up to three single-file holdouts
(first / middle / last of the gt file list, so deleted files and modified
files both get a turn), and all-but-one. Deterministic, minutes per task
for Go corpora; Java corpora index slowly (--projects to choose).

Usage: python3 verify_bed.py --prism BIN [--projects grove,prism] [--tag t]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import run_wide as RW  # noqa: E402  (isolated_worktree, sh)

OUT = H / "runs" / "verify-bed"


def gold_changes(task: dict) -> dict[str, str]:
    """{path: A|M|D} between base and gold, renames split into D + A."""
    out = {}
    txt = RW.sh("git", "-C", task["repo_path"], "diff", "--name-status", "--no-renames",
                task["base_commit"], task["gold_commit"], check=True)
    for line in txt.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out[parts[1]] = parts[0][0]
    return out


def apply_partial(wt: Path, task: dict, changes: dict[str, str], holdout: set[str]) -> None:
    for path, status in changes.items():
        if path in holdout:
            continue
        dst = wt / path
        if status == "D":
            if dst.exists():
                dst.unlink()
            continue
        content = subprocess.run(
            ["git", "-C", task["repo_path"], "show", f"{task['gold_commit']}:{path}"],
            capture_output=True, check=True).stdout
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(content)


def run_verify(prism: str, wt: Path) -> dict:
    subprocess.run([prism, "index", str(wt)], capture_output=True, text=True, timeout=900)
    r = subprocess.run([prism, "verify", "--format", "json", "."], cwd=wt,
                       capture_output=True, text=True, timeout=600)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": (r.stderr or r.stdout)[-300:]}


def score(holdout: set[str], res: dict) -> dict:
    missed = res.get("missedSites") or []
    files = {m.get("file", "") for m in missed}
    verdict = res.get("verdict")
    return {
        "verdict": verdict,
        "holdout": sorted(holdout),
        "named": sorted(holdout & files),
        "unnamed": sorted(holdout - files),
        "false_accuse": sorted(files - holdout),
        "n_missed": len(missed),
        "n_unverified": len(res.get("unverifiedSeeds") or []),
        "false_complete": bool(holdout) and verdict == "complete",
        "error": res.get("error"),
    }


def trials_for(task: dict, changes: dict[str, str]) -> list[tuple[str, set[str]]]:
    gt = [f for f in task["gt_files"] if f in changes]
    out: list[tuple[str, set[str]]] = [("complete", set())]
    picks = sorted({gt[0], gt[len(gt) // 2], gt[-1]}, key=gt.index) if gt else []
    for f in picks:
        out.append((f"hold:{Path(f).name}", {f}))
    if len(gt) > 1:
        out.append(("all-but-one", set(gt[1:])))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prism", required=True)
    ap.add_argument("--tasks", default=str(H / "tasks-wide"))
    ap.add_argument("--projects", default="grove,prism")
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="v1")
    a = ap.parse_args()
    prism = str(Path(a.prism).expanduser().resolve())
    projects = set(a.projects.split(","))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for tf in sorted(Path(a.tasks).glob("*.json")):
        task = json.loads(tf.read_text())
        if task["project"] not in projects or (a.only and a.only not in tf.name):
            continue
        changes = gold_changes(task)
        for name, holdout in trials_for(task, changes):
            repo, wt = RW.isolated_worktree(task)
            try:
                apply_partial(wt, task, changes, holdout)
                res = run_verify(prism, wt)
            finally:
                shutil.rmtree(wt, ignore_errors=True)
            s = score(holdout, res)
            s.update(task=task["instance_id"], trial=name)
            rows.append(s)
            flag = " FALSE-COMPLETE" if s["false_complete"] else ""
            print(f"{task['instance_id']:20} {name:28} verdict={s['verdict']!s:10} "
                  f"named={len(s['named'])}/{len(holdout)} false_accuse={len(s['false_accuse'])} "
                  f"missed={s['n_missed']} unverified={s['n_unverified']}{flag}"
                  + (f" ERR {s['error']}" if s["error"] else ""), flush=True)
    held = [r for r in rows if r["holdout"]]
    agg = {
        "trials": len(rows),
        "false_complete": sum(1 for r in held if r["false_complete"]),
        "holdout_trials": len(held),
        "holdouts_named": sum(len(r["named"]) for r in held),
        "holdouts_total": sum(len(r["holdout"]) for r in held),
        "false_accusations": sum(len(r["false_accuse"]) for r in rows),
        "complete_case_accusations": sum(len(r["false_accuse"]) for r in rows if not r["holdout"]),
    }
    print("\nAGGREGATE", json.dumps(agg))
    (OUT / f"{a.tag}.json").write_text(json.dumps({"rows": rows, "aggregate": agg,
                                                    "prism": prism}, indent=1))


if __name__ == "__main__":
    main()
