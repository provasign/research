#!/usr/bin/env python3
"""Java/Maven fail->pass eval — the Java analogue of docker_eval (Python).

Builds a task from a merged Java PR (base/gold/test_patch), then derives
FAIL_TO_PASS by running the changed test classes in a maven container on
base+tests (must FAIL) vs base+tests+gold (must PASS). A persistent ~/.m2
cache volume keeps repeat runs from re-downloading the dependency world.

Single-module Maven projects (jackson-databind, commons-lang) only for the
prototype; multi-module (netty) needs -pl and is a follow-up.
"""
import json, re, subprocess, sys, tempfile, xml.etree.ElementTree as ET
from pathlib import Path

IMAGE = "maven:3.9-eclipse-temurin-17"
M2 = Path.home() / ".m2-eval"       # persistent dep cache (host)
M2.mkdir(exist_ok=True)
CLONE_ROOT = Path.home() / "gvg-corpus"

# Where each Java repo is cloned on the host (single source of truth, imported
# by promote_java.py and run_e2e.py). Single-module Maven projects only.
REPO_DIR = {
    "FasterXML/jackson-databind": CLONE_ROOT / "jackson-databind",
    "apache/commons-lang": CLONE_ROOT / "commons-lang",
}
TESTP = re.compile(r"src/test/.*\.java$")
SRCP = re.compile(r"src/main/.*\.java$")


def sh(*a, cwd=None, timeout=600, check=True):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(a[:3])}: {r.stderr[:300]}")
    return r.stdout


def build_task(repo_dir: Path, repo: str, pr: int) -> dict:
    meta = json.loads(sh("gh", "pr", "view", str(pr), "-R", repo, "--json",
                         "title,body,mergeCommit,files"))
    merge = meta["mergeCommit"]["oid"]
    sh("git", "-C", str(repo_dir), "fetch", "--quiet", "origin", merge, timeout=300)
    parents = sh("git", "-C", str(repo_dir), "rev-list", "--parents", "-n", "1", merge).split()
    base = parents[1]
    files = [f["path"] for f in meta["files"]]
    src = [f for f in files if SRCP.search(f)]
    tst = [f for f in files if TESTP.search(f)]
    gold = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *src)
    tpatch = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *tst)
    # test classes: FQN from path src/test/java/a/b/C.java -> a.b.C
    classes = []
    for t in tst:
        m = re.search(r"src/test/java/(.+)\.java$", t)
        if m:
            classes.append(m.group(1).replace("/", "."))
    return {"instance_id": f"{repo.replace('/', '__')}__pr{pr}", "repo": repo, "pr": pr,
            "base_commit": base, "merge_commit": merge, "patch": gold,
            "test_patch": tpatch, "test_classes": classes, "src_files": src,
            # test_modules = test FILE PATHS (the run_e2e agent-diff excludes these,
            # same role as the Python task's test_modules); test_classes are the FQNs
            # java_eval runs via -Dtest.
            "test_modules": tst,
            "problem_statement": (meta.get("title") or "") + "\n\n" + (meta.get("body") or "")}


def _run_tests(repo_dir: Path, base: str, patches: list, classes: list) -> dict:
    """Worktree at base + patches; `mvn test -Dtest=...`; parse surefire XML."""
    wt = Path(tempfile.mkdtemp(prefix="java-eval-"))
    try:
        sh("git", "-C", str(repo_dir), "worktree", "add", "--force", "--detach",
           str(wt), base, timeout=300)
        for p in patches:
            if p.strip():
                subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                               input=p, text=True, capture_output=True)
        dtest = ",".join(c.split(".")[-1] for c in classes)  # -Dtest by simple name
        cmd = (f"mvn -q -o test -Dtest='{dtest}' -DfailIfNoTests=false "
               "-Dsurefire.failIfNoSpecifiedTests=false -Dmaven.test.failure.ignore=true "
               "2>&1 | tail -5; echo '---SUREFIRE---'; "
               "find . -path '*/surefire-reports/*.xml' -exec cat {} +")
        # first pass may need network for deps; drop -o if offline cache is cold
        out = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w",
                              "-v", f"{M2}:/root/.m2", "-w", "/w", IMAGE,
                              "bash", "-lc", cmd.replace("-o ", "")],
                             capture_output=True, text=True, timeout=1800)
        return _parse_surefire(out.stdout + out.stderr)
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


def _parse_surefire(text: str) -> dict:
    res = {}
    xmls = re.split(r"---SUREFIRE---", text, 1)
    blob = xmls[1] if len(xmls) > 1 else text
    for m in re.finditer(r"<testcase\b[^>]*\bname=\"([^\"]+)\"[^>]*\bclassname=\"([^\"]+)\"[^>]*(/>|>(.*?)</testcase>)",
                         blob, re.S):
        name, cls, _, body = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        nodeid = f"{cls}::{name}"
        res[nodeid] = "FAILED" if ("<failure" in body or "<error" in body) else "PASSED"
    return res


def validate(repo_dir: Path, task: dict) -> dict:
    before = _run_tests(repo_dir, task["base_commit"], [task["test_patch"]], task["test_classes"])
    after = _run_tests(repo_dir, task["base_commit"],
                       [task["test_patch"], task["patch"]], task["test_classes"])
    f2p = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) in ("FAILED", None))
    p2p = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) == "PASSED")
    # only count as f2p if it actually ran-and-failed before (not merely absent)
    f2p_strict = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) == "FAILED")
    return {"n_before": len(before), "n_after": len(after),
            "f2p_present_or_new": f2p, "fail_to_pass": f2p_strict, "pass_to_pass": p2p,
            "valid": bool(f2p_strict)}


def score(repo_dir: Path, task: dict, agent_patch: str) -> dict:
    """Score an agent's fix: apply agent_patch + the task's test_patch, run the
    test classes, require every FAIL_TO_PASS to PASS and no PASS_TO_PASS to
    regress. Mirrors docker_eval.score (Python) so run_e2e can branch on lang."""
    res = _run_tests(repo_dir, task["base_commit"],
                     [task["test_patch"], agent_patch], task["test_classes"])
    f2p_ok = all(res.get(n) == "PASSED" for n in task["fail_to_pass"])
    p2p_ok = all(res.get(n) == "PASSED" for n in task.get("pass_to_pass", []))
    return {"resolved": bool(f2p_ok and p2p_ok), "f2p_ok": f2p_ok,
            "p2p_ok": p2p_ok, "n_run": len(res)}


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "FasterXML/jackson-databind"
    pr = int(sys.argv[2]) if len(sys.argv) > 2 else 6030
    rd = CLONE_ROOT / "jackson-databind"
    print(f"building task {repo}#{pr} ...")
    task = build_task(rd, repo, pr)
    print(f"  base={task['base_commit'][:10]} test_classes={task['test_classes']} "
          f"src={len(task['src_files'])}")
    print("validating (base vs base+gold in maven docker) ...")
    v = validate(rd, task)
    print(json.dumps({k: v[k] for k in ('n_before', 'n_after', 'fail_to_pass', 'valid')}, indent=2))
