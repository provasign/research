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


# Per-repo test dependencies the plain `pip install -e . pytest` container
# lacks. pydantic: its conftest registers/uses markers and helpers from these
# plugins — without them collection dies with INTERNALERROR ('thread_unsafe'
# not found), which rejected all three pydantic candidates on 2026-08-05.
EXTRA_PIP = {
    "pydantic/pydantic": ["pytest-run-parallel", "dirty-equals", "pytest-mock",
                          "annotated-types", "email-validator", "pytest-examples"],
}


def _pytest_in_docker(worktree: Path, modules: list[str], repo: str = "",
                      test_cmds: list[str] | None = None) -> dict[str, str]:
    """Run the given test modules in a container; return {nodeid: outcome}."""
    # Install the project (editable) + pytest; project test-extras if declared.
    # pytest-timeout guards against a single hanging test (e.g. pager/stress
    # tests) blocking the whole module run.
    extra = " ".join(EXTRA_PIP.get(repo, []))
    # VCS-versioned builds (setuptools-scm / hatch-vcs / pdm-backend) need git
    # history the container does not have: the worktree's .git is a FILE
    # pointing at an unmounted host path, so `pip install -e .` dies deriving
    # a version (measured: every pytest/werkzeug/urllib3 candidate rejected
    # 0/0 on 2026-08-06). Pretend-version env vars skip the VCS lookup.
    # Test-only deps live in different places per ecosystem: extras
    # (.[dev]/.[test]), PEP-735 dependency groups (werkzeug: group "tests"
    # carries ephemeral-port-reserve — measured, its conftest ImportErrors
    # without it), or requirements files. Try them all, tolerantly; a miss
    # is harmless, a hit unblocks the repo.
    # VCS-versioning backends each need their own bypass. uv-dynamic-versioning
    # (a2a-python and friends) raises "This does not appear to be a Git project"
    # because the worktree's .git is a FILE pointing at an unmounted host path,
    # so pip install -e . fails, the package is never importable, and pytest
    # reports a collection ERROR -- which reads as "the fix did not work"
    # rather than "the harness could not build the project". Caught 2026-08-16
    # when the GOLD patch scored not-resolved.
    cmd = ("export SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PDM_BUILD_SCM_VERSION=0.0.0 "
           "HATCH_VCS_PRETEND_VERSION=0.0.0 UV_DYNAMIC_VERSIONING_BYPASS=0.0.0 "
           "SETUPTOOLS_SCM_PRETEND_VERSION_FOR_A2A_SDK=0.0.0; "
           "pip install -q --upgrade pip >/dev/null 2>&1; "
           "(pip install -q -e '.[dev]' 2>/dev/null || pip install -q -e '.[test]' 2>/dev/null "
           "|| pip install -q -e '.[tests]' 2>/dev/null || pip install -q -e .) 2>&1 | tail -2; "
           "pip install -q --group dev >/dev/null 2>&1; pip install -q --group tests >/dev/null 2>&1; "
           "for f in requirements/dev.txt requirements-dev.txt requirements/tests.txt "
           "requirements/test.txt dev-requirements.txt; do "
           "[ -f \"$f\" ] && pip install -q -r \"$f\" >/dev/null 2>&1; done; "
           f"pip install -q pytest pytest-timeout {extra} 2>&1 | tail -2; "
           "python -m pytest " + " ".join(modules) +
           " -v --tb=no -p no:cacheprovider -o addopts='' --timeout=90")
    # Prefer the environment the PROJECT declares. The bed carries test_cmds
    # (e.g. ["pytest -rA", "uv run pytest -rA"]) from mining, and a repo that
    # ships uv.lock needs `uv sync` to get its optional deps: a2a-python
    # installs fine with plain pip and then ImportErrors on SQLAlchemy at
    # collection, which scores the GOLD patch as not-resolved. Guessing extras
    # (.[dev]/.[test]/...) cannot cover this; the lockfile can.
    if any(c.startswith("uv ") or c.startswith("uv run") for c in (test_cmds or [])) \
            or (worktree / "uv.lock").exists():
        uv_cmd = ("export UV_DYNAMIC_VERSIONING_BYPASS=0.0.0 SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0; "
                  "pip install -q uv 2>&1 | tail -1; "
                  "uv sync --all-extras --frozen 2>&1 | tail -2 || uv sync --all-extras 2>&1 | tail -2; "
                  "uv pip install -q pytest pytest-timeout 2>&1 | tail -1; "
                  "uv run python -m pytest " + " ".join(modules) +
                  " -v --tb=no -p no:cacheprovider -o addopts='' --timeout=90")
        out = _sh("docker", "run", "--rm", "-v", f"{worktree}:/w", "-w", "/w",
                  IMAGE, "bash", "-lc", uv_cmd, timeout=1800, check=False)
        res = {m.group(1): m.group(2) for m in RESULT_RE.finditer(out)}
        if res:
            return res
        print("  [docker_eval] uv path collected nothing; falling back to pip")

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
        before = _pytest_in_docker(wt, mods, task["repo"], task.get("test_cmds"))
    finally:
        _cleanup(repo, wt)
    repo, wt = _worktree(task, [task["test_patch"], task["patch"]])
    try:
        after = _pytest_in_docker(wt, mods, task["repo"], task.get("test_cmds"))
    finally:
        _cleanup(repo, wt)
    # A collection ERROR on the base side (0 nodeids collected) usually means
    # the new tests import code that does not exist pre-fix — ImportError IS
    # a failure. Without this, click#3637 read as "0/58 collected" and was
    # rejected although every one of its 58 tests is genuinely fail->pass.
    if not before and after:
        f2p = sorted(n for n, o in after.items() if o == "PASSED")
        return {"fail_to_pass": f2p, "pass_to_pass": [],
                "valid": bool(f2p), "n_before": 0, "n_after": len(after),
                "note": "base-side collection error treated as fail (new-code import)"}
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
        res = _pytest_in_docker(wt, mods, task.get("repo", ""), task.get("test_cmds"))
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


# --- Official SWE-bench-Live images -----------------------------------------
#
# The hand-rolled python:3.12 path guesses at extras and per-repo build
# quirks, and it left 17 of 38 tasks unscoreable on 2026-08-16 -- every
# failure a build problem, not a bad task. SWE-bench-Live publishes a
# prebuilt, dependency-complete image per instance (3,150 of them), which
# removes the guessing entirely.
#
# NOTE the image is NOT at base_commit. Verified on
# datamodel-code-generator-2349: HEAD sat on a LATER PR, with 214 refs, an
# intact origin, and 1,007 commits reachable beyond HEAD. Harmless for
# scoring, because we reset to base before applying anything -- but never
# hand /testbed to an AGENT as-is, it is a direct route to the gold fix.

OFFICIAL_NS = "starryzhang"


def official_image(instance_id: str) -> str:
    """owner__repo-pr  ->  starryzhang/sweb.eval.x86_64.owner_1776_repo-pr"""
    return f"{OFFICIAL_NS}/sweb.eval.x86_64.{instance_id.replace('__', '_1776_')}"


def score_official(task: dict, agent_patch: str, timeout: int = 2400) -> dict:
    """Score inside the instance's official image. Same verdict contract as
    score(): resolved iff every FAIL_TO_PASS passes and no PASS_TO_PASS in the
    executed modules regresses."""
    img = official_image(task["instance_id"])
    mods = sorted({n.split("::")[0] for n in task.get("FAIL_TO_PASS", []) if "::" in n})
    runner = "python -m pytest"
    for c in task.get("test_cmds") or []:
        if c.startswith("uv run"):
            runner = "uv run python -m pytest"
            break
    script = (
        "set -e; cd /testbed; "
        f"git checkout -f -q {task['base_commit']}; "
        "git apply --3way /tmp/test.patch 2>&1 | tail -2 || true; "
        "if [ -s /tmp/agent.patch ]; then git apply --3way /tmp/agent.patch 2>&1 | tail -2 || true; fi; "
        f"{runner} " + " ".join(mods) +
        # No --timeout: pytest-timeout is not in these images and injecting
        # plugins into a project's own environment is what the hand-rolled
        # path did wrong. The docker timeout bounds the run instead.
        " -v --tb=no -p no:cacheprovider -o addopts='' 2>&1 | tail -400")
    import os
    d = tempfile.mkdtemp(prefix="swebl-")
    Path(d, "test.patch").write_text(task.get("test_patch", "") or "")
    Path(d, "agent.patch").write_text(agent_patch or "")
    try:
        out = _sh("docker", "run", "--rm", "--platform", "linux/amd64",
                  "-v", f"{d}/test.patch:/tmp/test.patch:ro",
                  "-v", f"{d}/agent.patch:/tmp/agent.patch:ro",
                  img, "bash", "-lc", script, timeout=timeout, check=False)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    res = {m.group(1): m.group(2) for m in RESULT_RE.finditer(out)}
    if not res:
        print("  [official] nothing collected; tail:\n" +
              "\n".join("    " + l for l in out.splitlines()[-10:]))
    f2p = task.get("FAIL_TO_PASS", [])
    p2p = [n for n in task.get("PASS_TO_PASS", []) if n.split("::")[0] in mods]
    f2p_ok = bool(f2p) and all(res.get(n) == "PASSED" for n in f2p)
    p2p_ok = all(res.get(n) == "PASSED" for n in p2p)
    return {"resolved": bool(f2p_ok and p2p_ok), "f2p_ok": f2p_ok,
            "p2p_ok": p2p_ok, "n_run": len(res), "image": img}
