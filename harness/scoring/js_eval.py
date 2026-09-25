#!/usr/bin/env python3
"""JS/mocha fail->pass eval — the JS analogue of go_eval.py / java_eval.py.

Builds a task from a merged JS PR (base/gold/test_patch), then derives
FAIL_TO_PASS by running the project's own mocha suite in a node container on
base+tests (must FAIL) vs base+tests+gold (must PASS). Test identity is the
mocha `fullTitle` (describe > it), not a function name — JS test files use
BDD closures, not named functions.

Single-suite repos (express) for the prototype.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))
from build_task import problem_statement as _problem_statement  # noqa: E402

IMAGE = "node:20"
NPM_CACHE = Path.home() / ".npm-eval"
NPM_CACHE.mkdir(exist_ok=True)
CLONE_ROOT = Path.home() / "gvg-corpus"

REPO_DIR = {
    "expressjs/express": CLONE_ROOT / "express",
}
TEST_CMD = {
    "expressjs/express": "npx mocha --require test/support/env --reporter json "
                          "--check-leaks test/ test/acceptance/",
}

TESTP = re.compile(r"(^|/)test/")
SRCP = re.compile(r"\.js$")


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
    tst = [f for f in files if TESTP.search(f)]
    src = [f for f in files if SRCP.search(f) and not TESTP.search(f)]
    gold = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *src)
    tpatch = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *tst)
    return {"instance_id": f"{repo.replace('/', '__')}__pr{pr}", "repo": repo, "pr": pr,
            "base_commit": base, "merge_commit": merge, "patch": gold,
            "test_patch": tpatch, "src_files": src, "test_modules": tst,
            # The linked ISSUE, never the PR body: PR bodies routinely
            # describe the fix (2026-09-24: 23/38 non-Python headline tasks named
            # the gold file in the prompt). Same source rule as build_task.py.
            "problem_statement": _problem_statement(repo, pr, meta)}


def _run_tests(repo_dir: Path, repo: str, base: str, patches: list, image: str = IMAGE) -> dict:
    """Worktree at base + patches; `npm ci` + full mocha suite with json reporter."""
    wt = Path(tempfile.mkdtemp(prefix="js-eval-"))
    try:
        sh("git", "-C", str(repo_dir), "worktree", "add", "--force", "--detach",
           str(wt), base, timeout=300)
        for p in patches:
            if p.strip():
                subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                               input=p, text=True, capture_output=True)
        cmd = f"npm install --no-audit --no-fund >/tmp/npm-install.log 2>&1; {TEST_CMD[repo]} 2>/dev/null"
        out = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w",
                              "-v", f"{NPM_CACHE}:/root/.npm", "-w", "/w", image,
                              "bash", "-c", cmd],
                             capture_output=True, text=True, timeout=1800)
        return _parse_mocha_json(out.stdout)
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


def _parse_mocha_json(text: str) -> dict:
    """mocha --reporter json prints ONE json object (not per-line); find it."""
    start = text.find('{"stats"')
    if start == -1:
        start = text.find("{")
    if start == -1:
        return {}
    try:
        doc = json.loads(text[start:])
    except json.JSONDecodeError:
        # trailing noise after the JSON blob — trim from the end
        depth = 0
        for i, ch in enumerate(text[start:]):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    doc = json.loads(text[start:start + i + 1])
                    break
        else:
            return {}
    res = {}
    for t in doc.get("passes", []):
        res[t["fullTitle"]] = "PASSED"
    for t in doc.get("failures", []):
        res[t["fullTitle"]] = "FAILED"
    for t in doc.get("pending", []):
        res[t["fullTitle"]] = "SKIPPED"
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
    repo = sys.argv[1] if len(sys.argv) > 1 else "expressjs/express"
    pr = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rd = REPO_DIR[repo]
    print(f"building task {repo}#{pr} ...")
    task = build_task(rd, repo, pr)
    print(f"  base={task['base_commit'][:10]} test_files={task['test_modules']} src={len(task['src_files'])}")
    print("validating (base vs base+gold in node docker) ...")
    v = validate(rd, repo, task)
    print(json.dumps({k: v[k] for k in ('n_before', 'n_after', 'fail_to_pass', 'valid')}, indent=2))
