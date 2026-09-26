#!/usr/bin/env python3
"""Go fail->pass eval — the Go analogue of java_eval.py (Maven) / docker_eval (Python).

Builds a task from a merged Go PR (base/gold/test_patch), then derives
FAIL_TO_PASS by running the changed test functions in a golang container on
base+tests (must FAIL) vs base+tests+gold (must PASS). A persistent GOPATH/
module cache volume keeps repeat runs from re-downloading deps.

Single-module repos (gin, ripgrep-equivalent Go projects) for the prototype;
multi-module (go.work) repos are a follow-up.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))
from build_task import problem_statement as _problem_statement  # noqa: E402

IMAGE = "golang:1.25"

GOMOD_CACHE = Path.home() / ".gocache-eval"  # persistent module cache (host)
GOMOD_CACHE.mkdir(exist_ok=True)
CLONE_ROOT = Path.home() / "gvg-corpus"

REPO_DIR = {
    "gin-gonic/gin": CLONE_ROOT / "gin",
    "urfave/cli": CLONE_ROOT / "cli",
    "go-chi/chi": CLONE_ROOT / "chi",
    "labstack/echo": CLONE_ROOT / "echo",
}

# The agent runs host go 1.25 with GOTOOLCHAIN=local (run_e2e._agent_env); a
# base whose go.mod asks for a newer go/toolchain can't build for the agent,
# while the scorer's GOTOOLCHAIN=auto would silently download one.
MAX_GO = (1, 25)


GO_IMAGES = {(1, 25): "golang:1.25", (1, 26): "golang:1.26"}


def go_version_for(repo_dir: Path, base: str) -> tuple[int, int]:
    """The Go minor a task's base needs: the highest `go`/`toolchain` line in
    go.mod, floored at 1.25. gin pr4805/pr4819 declare go 1.26.0, which the
    agent's pinned 1.25 (GOTOOLCHAIN=local) couldn't build while this scorer's
    GOTOOLCHAIN=auto silently downloaded 1.26 (2026-09-26). The agent
    (run_e2e._agent_env) and the scorer both use this version now."""
    try:
        mod = sh("git", "-C", str(repo_dir), "show", f"{base}:go.mod")
    except RuntimeError:
        return (1, 25)
    best = (1, 25)
    for m in re.finditer(r"(?m)^(go|toolchain)\s+(?:go)?(\d+)\.(\d+)", mod):
        best = max(best, (int(m.group(2)), int(m.group(3))))
    return best


def base_go_version_ok(repo_dir: Path, base: str) -> tuple[bool, str]:
    """(ok, detail): go.mod's `go` and `toolchain` lines at base are <= MAX_GO."""
    mod = sh("git", "-C", str(repo_dir), "show", f"{base}:go.mod")
    for m in re.finditer(r"(?m)^(go|toolchain)\s+(?:go)?(\d+)\.(\d+)", mod):
        if (int(m.group(2)), int(m.group(3))) > MAX_GO:
            return False, m.group(0).strip()
    return True, ""

TESTP = re.compile(r"_test\.go$")
SRCP = re.compile(r"\.go$")  # non-test .go files (filtered below)
FUNC_RE = re.compile(r"^func (Test\w+)\(")


def sh(*a, cwd=None, timeout=600, check=True):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(a[:3])}: {r.stderr[:300]}")
    return r.stdout


def _test_func_names(diff_text: str) -> list[str]:
    """Names of Test* functions touched (added or modified) by a diff.

    A changed line counts toward the function enclosing it: the hunk header's
    function context (`@@ ... @@ func TestX(`), updated by any `func` line
    inside the hunk. Matching only +/- `func Test` lines missed every test
    whose body alone changed (go-chi/chi#1029 edits TestMethodNotAllowed)."""
    names = set()
    cur = None
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            m = re.search(r"@@ func (Test\w+)\(", line)
            cur = m.group(1) if m else None
            continue
        if line.startswith(("diff --git", "--- ", "+++ ")):
            cur = None
            continue
        body = line[1:]
        if body.startswith("func "):
            m = FUNC_RE.match(body)
            cur = m.group(1) if m else None
        if line[:1] in "+-" and cur:
            names.add(cur)
    return sorted(names)


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
    test_funcs = _test_func_names(tpatch)
    return {"instance_id": f"{repo.replace('/', '__')}__pr{pr}", "repo": repo, "pr": pr,
            "base_commit": base, "merge_commit": merge, "patch": gold,
            "test_patch": tpatch, "test_functions": test_funcs, "src_files": src,
            "test_modules": tst,
            # The linked ISSUE, never the PR body: PR bodies routinely
            # describe the fix (2026-09-24: 23/38 non-Python headline tasks named
            # the gold file in the prompt). Same source rule as build_task.py.
            "problem_statement": _problem_statement(repo, pr, meta)}


def _run_tests(repo_dir: Path, base: str, patches: list, test_funcs: list, image: str | None = None) -> dict:
    """Worktree at base + patches; `go test -run '^(A|B)$' -json ./...`; parse events.
    The image follows the base's go.mod (go_version_for), the same Go the agent
    ran with, and GOTOOLCHAIN=local keeps it from switching mid-run."""
    if image is None:
        image = GO_IMAGES.get(go_version_for(repo_dir, base), IMAGE)
    wt = Path(tempfile.mkdtemp(prefix="go-eval-"))
    try:
        sh("git", "-C", str(repo_dir), "worktree", "add", "--force", "--detach",
           str(wt), base, timeout=300)
        for p in patches:
            if p.strip():
                subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                               input=p, text=True, capture_output=True)
        pattern = "^(" + "|".join(re.escape(t) for t in test_funcs) + ")$" if test_funcs else "^$"
        cmd = (f"go test -run '{pattern}' -json ./... 2>&1 || true")
        out = subprocess.run(["docker", "run", "--rm", "-e", "GOTOOLCHAIN=local",
                              "-v", f"{wt}:/w",
                              "-v", f"{GOMOD_CACHE}:/root/go", "-w", "/w", image,
                              "bash", "-c", cmd],
                             capture_output=True, text=True, timeout=1800)
        return _parse_go_json(out.stdout + out.stderr)
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


def _parse_go_json(text: str) -> dict:
    """`go test -json` emits one JSON object per line; Action in {pass,fail,skip} for Test events."""
    res = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        test = ev.get("Test")
        action = ev.get("Action")
        if not test or action not in ("pass", "fail", "skip"):
            continue
        if "/" in test:  # subtest — keep top-level name for now
            continue
        res[test] = {"pass": "PASSED", "fail": "FAILED", "skip": "SKIPPED"}[action]
    return res


def validate(repo_dir: Path, task: dict) -> dict:
    if not task["test_functions"]:
        return {"n_before": 0, "n_after": 0, "fail_to_pass": [], "pass_to_pass": [], "valid": False}
    before = _run_tests(repo_dir, task["base_commit"], [task["test_patch"]], task["test_functions"])
    after = _run_tests(repo_dir, task["base_commit"],
                       [task["test_patch"], task["patch"]], task["test_functions"])
    f2p_strict = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) == "FAILED")
    p2p = sorted(n for n, o in after.items() if o == "PASSED" and before.get(n) == "PASSED")
    return {"n_before": len(before), "n_after": len(after),
            "fail_to_pass": f2p_strict, "pass_to_pass": p2p, "valid": bool(f2p_strict)}


def commit_date(repo_dir: Path, sha: str) -> str:
    r = subprocess.run(["git", "-C", str(repo_dir), "show", "-s", "--format=%ci", sha],
                       capture_output=True, text=True)
    return r.stdout.strip()[:10]


def score(repo_dir: Path, task: dict, agent_patch: str) -> dict:
    res = _run_tests(repo_dir, task["base_commit"],
                     [task["test_patch"], agent_patch], task["test_functions"])
    f2p_ok = all(res.get(n) == "PASSED" for n in task["fail_to_pass"])
    p2p_ok = all(res.get(n) == "PASSED" for n in task.get("pass_to_pass", []))
    return {"resolved": bool(f2p_ok and p2p_ok), "f2p_ok": f2p_ok,
            "p2p_ok": p2p_ok, "n_run": len(res)}


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "gin-gonic/gin"
    pr = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rd = REPO_DIR.get(repo, CLONE_ROOT / repo.split("/")[-1])
    print(f"building task {repo}#{pr} ...")
    task = build_task(rd, repo, pr)
    print(f"  base={task['base_commit'][:10]} test_functions={task['test_functions']} "
          f"src={len(task['src_files'])}")
    print("validating (base vs base+gold in golang docker) ...")
    v = validate(rd, task)
    print(json.dumps({k: v[k] for k in ('n_before', 'n_after', 'fail_to_pass', 'valid')}, indent=2))
