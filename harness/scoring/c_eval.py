#!/usr/bin/env python3
"""C/cmake+ctest fail->pass eval — the C analogue of go_eval.py / java_eval.py.

Builds a task from a merged C PR (base/gold/test_patch), then derives
FAIL_TO_PASS by running the project's ctest suite in a container on
base+tests (must FAIL) vs base+tests+gold (must PASS), parsed from ctest's
--output-junit XML.

Single cmake-project repos (jansson) for the prototype.
"""
import json, re, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

IMAGE = "jansson-eval:latest"
CLONE_ROOT = Path.home() / "gvg-corpus"

REPO_DIR = {
    "akheron/jansson": CLONE_ROOT / "jansson",
}
BUILD_CMD = {
    "akheron/jansson": (
        "cmake -B build -DCMAKE_BUILD_TYPE=Release -DJANSSON_BUILD_DOCS=OFF "
        ">/tmp/cmake.log 2>&1 && "
        "cmake --build build -j$(nproc) >>/tmp/cmake.log 2>&1 && "
        "cd build && ctest --output-junit /tmp/junit.xml --output-on-failure "
        "2>&1 | tail -5; cat /tmp/junit.xml"
    ),
}

TESTP = re.compile(r"(^|/)test/")
SRCP = re.compile(r"\.[ch]$")


def sh(*a, cwd=None, timeout=600, check=True):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(a[:3])}: {r.stderr[:300]}")
    return r.stdout


def ensure_image():
    have = subprocess.run(["docker", "image", "inspect", IMAGE],
                          capture_output=True).returncode == 0
    if have:
        return
    dockerfile = ("FROM ubuntu:24.04\n"
                  "RUN apt-get update && apt-get install -y --no-install-recommends "
                  "build-essential cmake git ca-certificates && rm -rf /var/lib/apt/lists/*\n")
    subprocess.run(["docker", "build", "-t", IMAGE, "-"], input=dockerfile,
                   text=True, check=True, capture_output=True, timeout=600)


def build_task(repo_dir: Path, repo: str, pr: int) -> dict:
    meta = json.loads(sh("gh", "pr", "view", str(pr), "-R", repo, "--json",
                         "title,body,mergeCommit,files"))
    merge = meta["mergeCommit"]["oid"]
    sh("git", "-C", str(repo_dir), "fetch", "--quiet", "origin", merge, timeout=300)
    parents = sh("git", "-C", str(repo_dir), "rev-list", "--parents", "-n", "1", merge).split()
    base = parents[1]
    files = [f["path"] for f in meta["files"]]
    tst = [f for f in files if TESTP.search(f)]
    src = [f for f in files if SRCP.search(f) and not TESTP.search(f)]
    gold = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *src)
    tpatch = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *tst)
    return {"instance_id": f"{repo.replace('/', '__')}__pr{pr}", "repo": repo, "pr": pr,
            "base_commit": base, "merge_commit": merge, "patch": gold,
            "test_patch": tpatch, "src_files": src, "test_modules": tst,
            "problem_statement": (meta.get("title") or "") + "\n\n" + (meta.get("body") or "")}


def _run_tests(repo_dir: Path, repo: str, base: str, patches: list, image: str = IMAGE) -> dict:
    ensure_image()
    wt = Path(tempfile.mkdtemp(prefix="c-eval-"))
    try:
        sh("git", "-C", str(repo_dir), "worktree", "add", "--force", "--detach",
           str(wt), base, timeout=300)
        for p in patches:
            if p.strip():
                subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                               input=p, text=True, capture_output=True)
        out = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w", "-w", "/w",
                              image, "bash", "-c", BUILD_CMD[repo]],
                             capture_output=True, text=True, timeout=1800)
        return _parse_junit(out.stdout)
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


def _parse_junit(text: str) -> dict:
    start = text.find("<?xml")
    if start == -1:
        start = text.find("<testsuite")
    if start == -1:
        return {}
    try:
        root = ET.fromstring(text[start:])
    except ET.ParseError:
        return {}
    res = {}
    for tc in root.iter("testcase"):
        name = tc.get("name")
        failed = tc.find("failure") is not None or tc.find("error") is not None
        res[name] = "FAILED" if failed else "PASSED"
    return res


def validate(repo_dir: Path, repo: str, task: dict) -> dict:
    before = _run_tests(repo_dir, repo, task["base_commit"], [task["test_patch"]])
    after = _run_tests(repo_dir, repo, task["base_commit"],
                       [task["test_patch"], task["patch"]])
    f2p_strict = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) == "FAILED")
    p2p = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) == "PASSED")
    return {"n_before": len(before), "n_after": len(after),
            "fail_to_pass": f2p_strict, "pass_to_pass": p2p, "valid": bool(f2p_strict)}


def score(repo_dir: Path, repo: str, task: dict, agent_patch: str) -> dict:
    res = _run_tests(repo_dir, repo, task["base_commit"], [task["test_patch"], agent_patch])
    f2p_ok = all(res.get(n) == "PASSED" for n in task["fail_to_pass"])
    p2p_ok = all(res.get(n) == "PASSED" for n in task.get("pass_to_pass", []))
    return {"resolved": bool(f2p_ok and p2p_ok), "f2p_ok": f2p_ok,
            "p2p_ok": p2p_ok, "n_run": len(res)}


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "akheron/jansson"
    pr = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rd = REPO_DIR[repo]
    print(f"building task {repo}#{pr} ...")
    task = build_task(rd, repo, pr)
    print(f"  base={task['base_commit'][:10]} test_files={task['test_modules']} src={len(task['src_files'])}")
    print("validating (base vs base+gold in cmake/ctest docker) ...")
    v = validate(rd, repo, task)
    print(json.dumps({k: v[k] for k in ('n_before', 'n_after', 'fail_to_pass', 'valid')}, indent=2))
