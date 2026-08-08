"""Validate and score FAN-OUT tasks (refactors/sweeps with no fail->pass).

Oracle, per task — each layer recorded, never silently skipped:
  1. green:    the chosen test modules pass with the GOLD fix applied
               (validation) / with the AGENT diff applied (scoring). Module
               choice: the PR's own test modules; else test files whose
               basename matches a touched source file; else the task is
               rejected (an unguarded refactor cannot be scored honestly).
  2. coverage: fraction of gold-touched source files the agent's diff also
               touched, and per-file changed-line overlap — the completeness
               layer where the measured 0.62-0.75 forgetting rate becomes
               visible even when no test breaks.

score = {"green": bool, "coverage_files": x/y, "resolved": green AND
coverage_files == 1.0}. Coverage uses FILES as the unit (line ranges are
recorded for audit but not gated: gold line numbers shift under any
equivalent edit).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import docker_eval

TEST_RE = re.compile(r"(^|/)(tests?|testing)/|_test\.py$|test_.*\.py$", re.I)
# Documentation and changelogs are NOT part of the code change under test.
# Leaving them in the gold set measured whether the agent volunteered a
# changelog entry: click#3695 capped every arm at 0.67 (3 of its 9 gold
# files are CHANGES.md + docs/), werkzeug#3169 at 0.83. That is an
# arbitrary coin-flip, and it was a large share of the run-to-run variance.
DOC_RE = re.compile(r"\.(md|rst|txt)$|(^|/)docs?/|CHANGE(S|LOG)", re.I)


def _gold_files(task) -> list[str]:
    """Source files the gold patch touches (the coverage denominator)."""
    files = []
    for line in task["patch"].splitlines():
        if line.startswith("+++ b/"):
            p = line[6:]
            if not TEST_RE.search(p) and not DOC_RE.search(p) and p != "/dev/null":
                files.append(p)
    return sorted(set(files))


def _test_modules(task) -> list[str]:
    """Modules for the green layer, in trust order (see module docstring)."""
    if task["test_modules"]:
        return task["test_modules"]
    repo_dir = docker_eval._repo_dir(task)
    mods = []
    for src in _gold_files(task):
        base = Path(src).stem
        for cand in (f"tests/test_{base}.py", f"tests/{base}_test.py",
                     f"test/test_{base}.py"):
            if (repo_dir / cand).exists() and cand not in mods:
                mods.append(cand)
    return mods


def validate(task: dict) -> dict:
    """A fan-out task is valid when its green layer is real: the chosen
    modules PASS with gold applied (and exist at all)."""
    task = dict(task)
    mods = _test_modules(task)
    if not mods:
        return {"valid": False, "reason": "no test modules to guard the refactor"}
    gold_files = _gold_files(task)
    if len(gold_files) < 3:
        return {"valid": False, "reason": f"gold touches only {len(gold_files)} source files"}
    repo, wt = docker_eval._worktree(task, [task["test_patch"], task["patch"]])
    try:
        res = docker_eval._pytest_in_docker(wt, mods, task["repo"])
    finally:
        docker_eval._cleanup(repo, wt)
    passed = sum(1 for o in res.values() if o == "PASSED")
    failed = [n for n, o in res.items() if o != "PASSED"]
    return {
        "valid": bool(res) and not failed,
        "reason": "" if (res and not failed) else f"gold-side failures: {failed[:5] or 'nothing collected'}",
        "test_modules": mods, "n_green": passed,
        "gold_files": gold_files,
    }


def score(task: dict, agent_diff: str) -> dict:
    """Score an agent diff: green on the task's modules + gold-file coverage."""
    mods = task["test_modules"]
    repo, wt = docker_eval._worktree(task, [task["test_patch"], agent_diff])
    try:
        res = docker_eval._pytest_in_docker(wt, mods, task["repo"])
    finally:
        docker_eval._cleanup(repo, wt)
    green = bool(res) and all(o == "PASSED" for o in res.values())

    touched = {line[6:] for line in agent_diff.splitlines()
               if line.startswith("+++ b/")}
    gold = task["gold_files"]
    covered = [f for f in gold if f in touched]
    missed = [f for f in gold if f not in touched]
    cov = len(covered) / len(gold) if gold else 0.0
    return {
        "resolved": green and not missed,
        "green": green,
        "coverage_files": round(cov, 3),
        "n_gold_files": len(gold),
        "missed_files": missed,
        "n_tests_run": len(res),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("task_json")
    ap.add_argument("--score")
    a = ap.parse_args()
    task = json.loads(Path(a.task_json).read_text())
    if a.score:
        print(json.dumps(score(task, Path(a.score).read_text()), indent=2))
    else:
        print(json.dumps(validate(task), indent=2))
