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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))
from build_task import problem_statement as _problem_statement  # noqa: E402

IMAGE = "maven:3.9-eclipse-temurin-17"

# Era JDK. A 2016 jackson pom sets source 1.7; JDK 17 REMOVED source 7, so a
# modern image fails at compile and every test reads as "did not run" (n_run=0,
# measured 2026-08-25 on jackson-databind-1113). Same class of error as running
# 2019 Python on 3.14 — the fix is the same: match the image to the commit.
def image_for(date_iso: str) -> str:
    y = int(date_iso[:4]) if date_iso[:4].isdigit() else 2022
    if y <= 2017:
        return "maven:3.9-eclipse-temurin-8"
    if y <= 2020:
        return "maven:3.9-eclipse-temurin-11"
    return "maven:3.9-eclipse-temurin-17"
M2 = Path.home() / ".m2-eval"       # persistent dep cache (host)
M2.mkdir(exist_ok=True)
CLONE_ROOT = Path.home() / "gvg-corpus"

# Where each Java repo is cloned on the host (single source of truth, imported
# by promote_java.py and run_e2e.py). Single-module Maven projects only.
REPO_DIR = {
    "FasterXML/jackson-databind": CLONE_ROOT / "jackson-databind",
    # Multi-SWE-bench java_verified coverage (2026-08-25): 91 tasks across
    # these six repos, 72 of them jackson-core/databind.
    "FasterXML/jackson-core": CLONE_ROOT / "jackson-core",
    "FasterXML/jackson-dataformat-xml": CLONE_ROOT / "jackson-dataformat-xml",
    "google/gson": CLONE_ROOT / "gson",
    "GoogleContainerTools/jib": CLONE_ROOT / "jib",
    "apache/dubbo": CLONE_ROOT / "dubbo",
    "apache/commons-lang": CLONE_ROOT / "commons-lang",
    "apache/commons-collections": CLONE_ROOT / "commons-collections",
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
            # The linked ISSUE, never the PR body: PR bodies routinely
            # describe the fix (2026-09-24: 23/38 non-Python headline tasks named
            # the gold file in the prompt). Same source rule as build_task.py.
            "problem_statement": _problem_statement(repo, pr, meta)}


def _run_tests(repo_dir: Path, base: str, patches: list, classes: list, image: str = IMAGE) -> dict:
    """Worktree at base + patches; `mvn test -Dtest=...`; parse surefire XML."""
    wt = Path(tempfile.mkdtemp(prefix="java-eval-"))
    try:
        sh("git", "-C", str(repo_dir), "worktree", "add", "--force", "--detach",
           str(wt), base, timeout=300)
        # Pin BEFORE the patches: run_e2e hands the agent a worktree with the
        # same pin committed on top of base, so an agent diff that touches
        # pom.xml was made against the pinned file.
        _pin_snapshot_parent(wt)
        for p in patches:
            if p.strip():
                subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                               input=p, text=True, capture_output=True)
        dtest = ",".join(c.split(".")[-1] for c in classes)  # -Dtest by simple name
        # -nsu: a SNAPSHOT parent that has no release yet (jackson-base
        # 3.3.0-SNAPSHOT) resolves from the cached snapshot, never a newer one.
        cmd = (f"mvn -q -o -nsu test -Dtest='{dtest}' -DfailIfNoTests=false "
               "-Dsurefire.failIfNoSpecifiedTests=false -Dmaven.test.failure.ignore=true "
               "2>&1 | tail -5; echo '---SUREFIRE---'; "
               "find . -path '*/surefire-reports/*.xml' -exec cat {} +")
        # first pass may need network for deps; drop -o if offline cache is cold
        out = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w",
                              "-v", f"{M2}:/root/.m2", "-w", "/w", image,
                              "bash", "-lc", cmd.replace("-o ", "")],
                             capture_output=True, text=True, timeout=1800)
        return _parse_surefire(out.stdout + out.stderr)
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


def _pin_snapshot_parent(wt: Path, m2: Path = M2) -> bool:
    """Point a -SNAPSHOT parent POM at its RELEASED version.

    Historical jackson poms declare `<parent>jackson-base:X-SNAPSHOT`, and
    Sonatype garbage-collects snapshots — so every commit older than the
    current dev line fails at POM resolution before a single test runs
    (measured 2026-08-25: 44 of 91 Multi-SWE-bench java tasks, all
    n_run=0). The released X exists on Maven Central and is the same
    coordinate the commit eventually shipped under; for TEST EXECUTION
    that substitution is faithful enough, and it is deterministic and
    visible here rather than hidden in an image.

    Exception: a dev line with no release yet (jackson-base 3.3.0, 2026-09)
    keeps its SNAPSHOT parent when that snapshot is in the cache and the
    release is not -- pinning it made pr6044/pr6052/pr6076 unbuildable.
    Returns whether pom.xml changed.
    """
    pom = wt / "pom.xml"
    if not pom.exists():
        return False
    src = pom.read_text(errors="replace")
    head = src.split("</parent>", 1)
    if len(head) != 2 or "-SNAPSHOT" not in head[0]:
        return False
    gav = re.search(r"<groupId>([^<]+)</groupId>.*?<artifactId>([^<]+)</artifactId>.*?"
                    r"<version>([^<]+)-SNAPSHOT</version>", head[0].split("<parent>", 1)[-1], re.S)
    if gav:
        d = m2.joinpath("repository", *gav.group(1).split("."), gav.group(2))
        rel, snap = gav.group(3), gav.group(3) + "-SNAPSHOT"
        if (not (d / rel / f"{gav.group(2)}-{rel}.pom").exists()
                and any((d / snap).glob(f"{gav.group(2)}-{rel}-*.pom"))):
            return False
    pinned = re.sub(r"<version>([^<]+)-SNAPSHOT</version>", r"<version>\1</version>", head[0], count=1)
    pom.write_text(pinned + "</parent>" + head[1])
    return True


_SUITE_RE = re.compile(r"<testsuite\b(?:[^>]*/>|.*?</testsuite>)", re.S)


def _parse_surefire(text: str) -> dict:
    """classname::name -> PASSED/FAILED/SKIPPED from the surefire XML reports
    concatenated after ---SUREFIRE---.

    A real XML parse per <testsuite> block. The regex parser this replaces let
    `[^>]*` swallow the `/` of a self-closing (passing) <testcase/>, so its body
    ran to the NEXT test's </testcase>: a passing test followed by a failing
    one read as FAILED and the failing one vanished (2026-09-26). A <failure>
    or <error> child is FAILED, <skipped> is SKIPPED, anything else PASSED
    (a <flakyFailure>/<rerunFailure> test passed on rerun). Duplicate ids: a
    failure anywhere wins. Malformed blocks (a report truncated mid-write) are
    skipped rather than guessed at."""
    parts = re.split(r"---SUREFIRE---", text, maxsplit=1)
    blob = parts[1] if len(parts) > 1 else text
    rank = {"PASSED": 0, "SKIPPED": 1, "FAILED": 2}
    res = {}
    for m in _SUITE_RE.finditer(blob):
        try:
            suite = ET.fromstring(m.group(0))
        except ET.ParseError:
            continue
        for tc in suite.iter("testcase"):
            name, cls = tc.get("name"), tc.get("classname") or suite.get("name")
            if not name or not cls:
                continue
            tags = {c.tag for c in tc}
            if tags & {"failure", "error"}:
                o = "FAILED"
            elif "skipped" in tags:
                o = "SKIPPED"
            else:
                o = "PASSED"
            k = f"{cls}::{name}"
            if k not in res or rank[o] > rank[res[k]]:
                res[k] = o
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


def commit_date(repo_dir: Path, sha: str) -> str:
    r = subprocess.run(["git", "-C", str(repo_dir), "show", "-s", "--format=%ci", sha],
                       capture_output=True, text=True)
    return r.stdout.strip()[:10]


def _entry_ok(res: dict, entry: str) -> bool:
    """A required entry passes when it names a METHOD that passed, or names a
    CLASS all of whose testcases passed. Multi-SWE-bench uses class-level ids
    (`src:com.foo.BarTest`), which never match a `class::method` key."""
    entry = entry.split(":", 1)[-1] if entry.startswith(("src:", "test:", "tests:")) else entry
    if "::" in entry:
        return res.get(entry) == "PASSED"
    hits = [v for k, v in res.items() if k.split("::")[0] == entry]
    # a @Disabled/assumption-skipped method neither passes nor fails the class
    return "PASSED" in hits and all(v in ("PASSED", "SKIPPED") for v in hits)


def score(repo_dir: Path, task: dict, agent_patch: str) -> dict:
    """Score an agent's fix: apply agent_patch + the task's test_patch, run the
    test classes, require every FAIL_TO_PASS to PASS and no PASS_TO_PASS to
    regress. Mirrors docker_eval.score (Python) so run_e2e can branch on lang."""
    img = image_for(commit_date(repo_dir, task["base_commit"]))
    res = _run_tests(repo_dir, task["base_commit"],
                     [task["test_patch"], agent_patch], task["test_classes"], image=img)
    f2p_ok = all(_entry_ok(res, n) for n in task["fail_to_pass"])
    p2p_ok = all(_entry_ok(res, n) for n in task.get("pass_to_pass", []))
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
