#!/usr/bin/env python3
"""JS/TS fail->pass eval — the JS analogue of go_eval.py / java_eval.py.

Builds a task from a merged JS/TS PR (base/gold/test_patch), then derives
FAIL_TO_PASS by running the project's own test suite in a node:20 container on
base+tests (must FAIL) vs base+tests+gold (must PASS).

Two runners:
  mocha  (express)          -- test identity is mocha's `fullTitle`.
  vitest (hono, zod, h3)    -- test identity is "<file> > <fullName>"; vitest
                               fullNames repeat across files, the file keeps
                               them distinct.
A vitest repo's worktree is copied INTO the container before install, so
node_modules never lands on the host bind mount (thousands of small files over
virtiofs made installs slow and left host worktrees dirty). Package-manager
caches are persistent host dirs, so repeated validations reuse downloads.
Tasks from TypeScript repos carry lang "ts"; run_e2e maps "ts" to this module.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))
from build_task import problem_statement as _problem_statement  # noqa: E402

IMAGE = "node:20"
NPM_CACHE = Path.home() / ".npm-eval"
NPM_CACHE.mkdir(exist_ok=True)
PNPM_STORE = Path.home() / ".pnpm-eval-store"
PNPM_STORE.mkdir(exist_ok=True)
BUN_CACHE = Path.home() / ".bun-eval-cache"
BUN_CACHE.mkdir(exist_ok=True)
CLONE_ROOT = Path.home() / "gvg-corpus"

REPO_DIR = {
    "expressjs/express": CLONE_ROOT / "express",
    "honojs/hono": CLONE_ROOT / "hono",
    "colinhacks/zod": CLONE_ROOT / "zod",
    "h3js/h3": CLONE_ROOT / "h3",
}
# pnpm 11 needs node >=22.13; pnpm 10 reads the same v9 lockfile on node 20.
_PNPM = ("npx -y pnpm@10.33.2 install --frozen-lockfile --store-dir /pnpm-store "
         "--config.package-import-method=copy --config.manage-package-manager-versions=false")
INSTALL_CMD = {
    "expressjs/express": "npm install --no-audit --no-fund",
    # hono used bun.lock (no npm/pnpm lockfile) until 2026-09-24's pnpm move.
    "honojs/hono": "npx -y bun@1.2.20 install --frozen-lockfile",
    # the docs packages pull next.js etc.; the zod project needs only root + zod.
    "colinhacks/zod": _PNPM + " --filter . --filter zod",
    "h3js/h3": _PNPM,
}
_VITEST = "npx vitest run --reporter=json --outputFile=/tmp/vitest.json --coverage.enabled=false"
TEST_CMD = {
    "expressjs/express": "npx mocha --require test/support/env --reporter json "
                          "--check-leaks test/ test/acceptance/",
    # runtime-tests/* projects need workerd/deno/bun/lambda runtimes; the three
    # node projects are hono's unit suite.
    "honojs/hono": _VITEST + " --project main --project jsx-runtime-default "
                             "--project jsx-runtime-dom",
    "colinhacks/zod": _VITEST + " --project zod",
    "h3js/h3": _VITEST,
}
RUNNER = {"expressjs/express": "mocha"}  # default: vitest

TESTP = re.compile(r"(^|/)test/")
SRCP = re.compile(r"\.js$")
# TypeScript repos: colocated *.test.ts / *.spec.ts, test/ dirs, snapshots.
TS_TESTP = re.compile(r"(^|/)(tests?|__tests__|__snapshots__)/|\.(test|spec)\.[cm]?[jt]sx?(\.snap)?$")
TS_SRCP = re.compile(r"\.([cm]?[jt]sx?)$")
# non-source, non-test churn that does not change behaviour
IGNORABLE = re.compile(r"\.(md|mdx|txt)$|(^|/)(docs?|\.changeset|\.github)/")


def _patterns(repo: str):
    if RUNNER.get(repo, "vitest") == "mocha":
        return TESTP, SRCP
    return TS_TESTP, TS_SRCP


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
    testp, srcp = _patterns(repo)
    tst = [f for f in files if testp.search(f)]
    src = [f for f in files if srcp.search(f) and not testp.search(f)]
    # config/lockfile/fixture churn outside src+tests: promotion rejects these
    other = [f for f in files if f not in tst and f not in src and not IGNORABLE.search(f)]
    gold = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *src)
    tpatch = sh("git", "-C", str(repo_dir), "diff", f"{base}..{merge}", "--", *tst)
    return {"instance_id": f"{repo.replace('/', '__')}__pr{pr}", "repo": repo, "pr": pr,
            "base_commit": base, "merge_commit": merge, "patch": gold,
            "test_patch": tpatch, "src_files": src, "test_modules": tst,
            "other_files": other,
            # The linked ISSUE, never the PR body: PR bodies routinely
            # describe the fix (2026-09-24: 23/38 non-Python headline tasks named
            # the gold file in the prompt). Same source rule as build_task.py.
            "problem_statement": (ps := _problem_statement(repo, pr, meta)),
            # build_task.problem_statement falls back to the PR title when no
            # real issue is linked; promotion requires "issue".
            "prompt_source": "issue" if ps.strip() != meta["title"].strip() else "title"}


class PatchError(RuntimeError):
    pass


def _run_tests(repo_dir: Path, repo: str, base: str, patches: list, image: str = IMAGE,
               strict: bool = False) -> dict:
    """Worktree at base + patches; install + the repo's suite in node docker.
    strict=True (validation) raises PatchError when a patch does not apply;
    scoring keeps the lenient behaviour (an unappliable agent diff just runs
    base+tests and fails)."""
    wt = Path(tempfile.mkdtemp(prefix="js-eval-"))
    try:
        sh("git", "-C", str(repo_dir), "worktree", "add", "--force", "--detach",
           str(wt), base, timeout=300)
        for p in patches:
            if p.strip():
                r = subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                                   input=p, text=True, capture_output=True)
                if strict and r.returncode != 0:
                    raise PatchError(f"patch does not apply: {r.stderr[:300]}")
        if RUNNER.get(repo, "vitest") == "mocha":
            cmd = f"npm install --no-audit --no-fund >/tmp/npm-install.log 2>&1; {TEST_CMD[repo]} 2>/dev/null"
            out = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w",
                                  "-v", f"{NPM_CACHE}:/root/.npm", "-w", "/w", image,
                                  "bash", "-c", cmd],
                                 capture_output=True, text=True, timeout=1800)
            return _parse_mocha_json(out.stdout)
        return _run_vitest(wt, repo, image)
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


MARK = "__JS_EVAL_VITEST_JSON__"
LAST_LOG = {"text": ""}  # tail of the last vitest container run, for diagnosis


def _run_vitest(wt: Path, repo: str, image: str) -> dict:
    cmd = ("set -o pipefail; mkdir -p /w && tar -C /src --exclude=./.git -cf - . | tar -C /w -xf - && cd /w && "
           f"({INSTALL_CMD[repo]}) >/tmp/install.log 2>&1 || "
           "{ echo INSTALL_FAILED; tail -40 /tmp/install.log; exit 3; }; "
           f"CI=1 {TEST_CMD[repo]} >/tmp/test.log 2>&1; "
           f"echo {MARK}; cat /tmp/vitest.json 2>/dev/null; echo; echo {MARK}; tail -40 /tmp/test.log")
    out = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/src:ro",
                          "-v", f"{NPM_CACHE}:/root/.npm",
                          "-v", f"{PNPM_STORE}:/pnpm-store",
                          "-v", f"{BUN_CACHE}:/root/.bun/install/cache",
                          image, "bash", "-c", cmd],
                         capture_output=True, text=True, timeout=2400)
    LAST_LOG["text"] = (out.stdout[-4000:] if MARK not in out.stdout
                        else out.stdout.split(MARK)[-1][-4000:]) + out.stderr[-2000:]
    parts = out.stdout.split(MARK)
    if len(parts) < 3:
        return {}
    return _parse_vitest_json(parts[1])


def _parse_vitest_json(text: str) -> dict:
    """vitest's json reporter (jest-compatible). A file that fails to load
    has status "failed" and no assertionResults: its tests are simply absent,
    so they can never count as FAIL->PASS (only a test that RAN and failed
    does). Duplicate ids within a file: any failure wins."""
    try:
        doc = json.loads(text.strip())
    except json.JSONDecodeError:
        return {}
    res = {}
    for f in doc.get("testResults", []):
        rel = f.get("name", "")
        rel = rel[len("/w/"):] if rel.startswith("/w/") else rel
        for a in f.get("assertionResults", []):
            st = a.get("status")
            o = {"passed": "PASSED", "failed": "FAILED"}.get(st, "SKIPPED")
            k = f"{rel} > {a.get('fullName') or a.get('title')}"
            if res.get(k) == "FAILED":
                continue
            if k in res and res[k] != o:
                o = "FAILED" if "FAILED" in (o, res[k]) else o
            res[k] = o
    return res


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


def validate(repo_dir: Path, repo: str, task: dict, runs: int = 1) -> dict:
    """runs>1 repeats both sides and keeps only tests stable across runs:
    a FAIL->PASS test must fail in every base+tests run and pass in every
    gold run; a PASS->PASS test must pass in all of them. Any disagreement
    is reported as `flaky` (promotion rejects tasks whose FAIL->PASS set
    differs between runs)."""
    befores, afters = [], []
    for _ in range(runs):
        befores.append(_run_tests(repo_dir, repo, task["base_commit"], [task["test_patch"]],
                                  strict=True))
        afters.append(_run_tests(repo_dir, repo, task["base_commit"],
                                 [task["test_patch"], task["patch"]], strict=True))
    f2p_sets = [{n for n, o in a.items() if o == "PASSED" and b.get(n) == "FAILED"}
                for b, a in zip(befores, afters)]
    f2p = set.intersection(*f2p_sets)
    p2p = set.intersection(*[{n for n, o in a.items() if o == "PASSED" and b.get(n) == "PASSED"}
                             for b, a in zip(befores, afters)]) - f2p
    # a gold-side test that is not PASSED in some run but PASSED in another
    gold_flaky = sorted(set.union(*[{n for n, o in a.items() if o == "PASSED"} for a in afters])
                        - set.intersection(*[{n for n, o in a.items() if o == "PASSED"} for a in afters]))
    flaky = sorted(set.union(*f2p_sets) - f2p)
    return {"n_before": len(befores[0]), "n_after": len(afters[0]),
            "n_before_runs": [len(b) for b in befores], "n_after_runs": [len(a) for a in afters],
            "fail_to_pass": sorted(f2p), "pass_to_pass": sorted(p2p),
            "flaky": flaky, "gold_flaky": gold_flaky,
            "valid": bool(f2p) and not flaky}


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
