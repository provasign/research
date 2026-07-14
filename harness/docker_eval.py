"""Docker fail->pass verification and scoring for the end-to-end benchmark.

Two uses, same core:
  1. VALIDATE a candidate task: with the test_patch applied, the target test
     module must FAIL on base (fail-to-pass exists) and PASS once the gold patch
     is added. Tests failing-before / passing-after = FAIL_TO_PASS. A task with
     an empty FAIL_TO_PASS set is discarded (the test doesn't discriminate).
  2. SCORE an agent run: apply the agent's diff (instead of gold), rerun the
     FAIL_TO_PASS tests -> resolved iff all pass and no pass->fail regression.

Everything runs in an ephemeral container over a throwaway git worktree, so the
host repo and the agent's own edits are never mutated by scoring.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

CLONE_ROOT = Path.home() / "gvg-corpus" / "e2e-2026"
IMAGE = "python:3.12"
RESULT_RE = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR)", re.M)


def _sh(*a, cwd=None, timeout=600, check=True):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(" ".join(map(str, a)) + "\n" + (r.stderr or r.stdout)[:500])
    return r.stdout


def _repo_dir(task) -> Path:
    return CLONE_ROOT / task["repo"].replace("/", "__")


def _pytest_in_docker(worktree: Path, modules: list[str]) -> dict[str, str]:
    """Run the given test modules in a container; return {nodeid: outcome}."""
    # Install the project (editable) + pytest; project test-extras if declared.
    cmd = ("pip install -q -e . pytest 2>&1 | tail -2; "
           "python -m pytest " + " ".join(modules) +
           " -v --tb=no -p no:cacheprovider -o addopts=''")
    out = _sh("docker", "run", "--rm", "-v", f"{worktree}:/w", "-w", "/w",
              IMAGE, "bash", "-lc", cmd, timeout=1200, check=False)
    res = {m.group(1): m.group(2) for m in RESULT_RE.finditer(out)}
    if not res:  # nothing collected -- surface why instead of a silent 0/0
        print("  [docker_eval] no tests collected; container tail:\n" +
              "\n".join("    " + l for l in out.splitlines()[-12:]))
    return res


def _worktree(task, patches: list[str]):
    """A throwaway worktree at base_commit with the given patches applied."""
    repo = _repo_dir(task)
    wt = Path(tempfile.mkdtemp(prefix="e2e-wt-"))
    _sh("git", "-C", str(repo), "worktree", "add", "--force", "--detach",
        str(wt), task["base_commit"], timeout=300)
    for p in patches:
        if p and p.strip():
            (wt / ".p.diff").write_text(p)
            _sh("git", "-C", str(wt), "apply", "--3way", str(wt / ".p.diff"), check=False)
            (wt / ".p.diff").unlink(missing_ok=True)
    return repo, wt


def _cleanup(repo: Path, wt: Path):
    _sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt), check=False)


def validate(task: dict) -> dict:
    """Promote a candidate to a task: derive FAIL_TO_PASS (fail on base+tests,
    pass on base+tests+gold)."""
    mods = task["test_modules"]
    repo, wt = _worktree(task, [task["test_patch"]])
    try:
        before = _pytest_in_docker(wt, mods)
    finally:
        _cleanup(repo, wt)
    repo, wt = _worktree(task, [task["test_patch"], task["patch"]])
    try:
        after = _pytest_in_docker(wt, mods)
    finally:
        _cleanup(repo, wt)
    f2p = sorted(n for n, o in after.items()
                 if o == "PASSED" and before.get(n) in ("FAILED", "ERROR"))
    p2p = sorted(n for n, o in after.items()
                 if o == "PASSED" and before.get(n) == "PASSED")
    return {"fail_to_pass": f2p, "pass_to_pass": p2p,
            "valid": bool(f2p), "n_before": len(before), "n_after": len(after)}


def score(task: dict, agent_patch: str) -> dict:
    """Resolved iff every FAIL_TO_PASS passes and no PASS_TO_PASS regresses."""
    mods = task["test_modules"]
    repo, wt = _worktree(task, [task["test_patch"], agent_patch])
    try:
        res = _pytest_in_docker(wt, mods)
    finally:
        _cleanup(repo, wt)
    f2p_ok = all(res.get(n) == "PASSED" for n in task["fail_to_pass"])
    p2p_ok = all(res.get(n) == "PASSED" for n in task.get("pass_to_pass", []))
    return {"resolved": bool(f2p_ok and p2p_ok), "f2p_ok": f2p_ok,
            "p2p_ok": p2p_ok, "n_run": len(res)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("task_json")
    ap.add_argument("--score", help="path to an agent diff to score (else validate)")
    a = ap.parse_args()
    task = json.loads(Path(a.task_json).read_text())
    if a.score:
        print(json.dumps(score(task, Path(a.score).read_text()), indent=2))
    else:
        v = validate(task)
        print(json.dumps(v, indent=2))
        if v["valid"]:
            task.update(fail_to_pass=v["fail_to_pass"], pass_to_pass=v["pass_to_pass"])
            Path(a.task_json).write_text(json.dumps(task, indent=2))
            print(f"-> promoted: FAIL_TO_PASS={v['fail_to_pass']}")
