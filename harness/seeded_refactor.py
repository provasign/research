"""Seeded signature-change tasks scored by the COMPILER.

Every other oracle we built this week broke on ambiguity: gold-diff coverage
scored a valid alternative implementation as "forgot 5 sites" (click#3695,
:meta private: vs renaming), and refactors mostly have no fail->pass test.
javac has neither problem. A call site either type-checks or it does not,
so there is exactly one correct answer set and no judgement call in scoring.

Task shape: add a parameter to a widely-implemented/called method in a
statically typed repo, hand the agent the compile error, and ask it to make
the project compile. The required set is the method's override family plus
every caller — the change-impact closure, arrived at from inside real work
rather than asked for directly.

  seed(task)  -> apply the signature mutation, confirm the build BREAKS
                 (a mutation that still compiles is not a task)
  score(diff) -> apply the agent's diff on top of the mutation; the project
                 must COMPILE. Also reports how many of the oracle's known
                 sites the diff touched, for diagnosis only — the verdict is
                 the compiler's.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

IMAGE = "maven:3.9-eclipse-temurin-17"
M2 = Path.home() / ".m2-eval"
M2.mkdir(exist_ok=True)


def sh(*a, timeout=900):
    return subprocess.run(a, capture_output=True, text=True, timeout=timeout).stdout


def _worktree(repo: Path, base: str):
    wt = Path(tempfile.mkdtemp(prefix="seed-refactor-"))
    sh("git", "-C", str(repo), "worktree", "add", "--force", "--detach", str(wt), base)
    return wt


def _cleanup(repo: Path, wt: Path):
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
                   capture_output=True)


def compile_in_docker(wt: Path) -> tuple[bool, str]:
    """mvn compile only — no tests. Returns (ok, tail of output)."""
    # `mvn | tail` returns TAIL's exit status, not maven's — that reported a
    # build with 11 compile errors as a success. Capture maven's own status.
    cmd = ("set -o pipefail; mvn -q compile -DskipTests 2>&1 | tail -40")
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w",
                        "-v", f"{M2}:/root/.m2", "-w", "/w", IMAGE, "bash", "-lc", cmd],
                       capture_output=True, text=True, timeout=2400)
    out = (r.stdout + r.stderr)[-4000:]
    return r.returncode == 0, out


def apply_mutation(wt: Path, mutation: dict) -> bool:
    """Rewrite the declaration line(s) named by the mutation spec."""
    f = wt / mutation["file"]
    if not f.exists():
        return False
    src = f.read_text()
    if mutation["find"] not in src:
        return False
    f.write_text(src.replace(mutation["find"], mutation["replace"], 1))
    return True


def seed(repo: Path, task: dict) -> dict:
    """Confirm the mutation breaks the build (else it is not a task)."""
    wt = _worktree(repo, task["base_commit"])
    try:
        if not apply_mutation(wt, task["mutation"]):
            return {"valid": False, "reason": "mutation anchor not found"}
        ok, out = compile_in_docker(wt)
        errs = re.findall(r"\[ERROR\].*?\.java:\[\d+", out)
        return {"valid": not ok, "reason": "" if not ok else "mutation still compiles",
                "n_compile_errors": len(errs), "sample": errs[:5]}
    finally:
        _cleanup(repo, wt)


def score(repo: Path, task: dict, agent_diff: str) -> dict:
    """The compiler is the verdict; site coverage is diagnostic only."""
    # NO apply_mutation here: the agent worked in a tree that already had it,
    # and its diff is taken against BASE, so the diff already carries the
    # mutation. Re-applying it made every patch conflict and silently scored
    # the agent's work as absent (measured: residual errors identical to the
    # untouched build while the diff touched 9 of 11 required files).
    wt = _worktree(repo, task["base_commit"])
    try:
        if agent_diff.strip():
            subprocess.run(["git", "-C", str(wt), "apply", "--3way", "--whitespace=nowarn"],
                           input=agent_diff, text=True, capture_output=True)
        ok, out = compile_in_docker(wt)
        touched = {l[6:] for l in agent_diff.splitlines() if l.startswith("+++ b/")}
        known = task.get("oracle_files") or []
        return {
            "resolved": ok,
            "compiles": ok,
            "files_touched": len(touched),
            "oracle_files_touched": len([f for f in known if f in touched]),
            "n_oracle_files": len(known),
            "residual_errors": len(re.findall(r"\[ERROR\].*?\.java:\[\d+", out)) if not ok else 0,
            "error_tail": "" if ok else out[-1200:],
        }
    finally:
        _cleanup(repo, wt)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("task_json")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--score")
    a = ap.parse_args()
    task = json.loads(Path(a.task_json).read_text())
    repo = Path(a.repo).expanduser()
    if a.score:
        print(json.dumps(score(repo, task, Path(a.score).read_text()), indent=2))
    else:
        print(json.dumps(seed(repo, task), indent=2))
