"""Turn a mined 2026 PR into a SWE-bench-format task.

Given repo + PR number, emit: base_commit (the PR's parent -- the pre-fix
state), gold patch (non-test source changes -- what the agent must reproduce
the *effect* of, never shown to it), test_patch (the test-file changes -- these
ARE applied before scoring, and define fail->pass), problem_statement (the
linked issue / PR body), and the changed test modules (the Docker step derives
exact FAIL_TO_PASS by running them on base vs gold).

Pure git/gh -- no Docker. Docker only enters at fail->pass verification.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

TEST_RE = re.compile(r"(^|/)(tests?|testing)/|_test\.py$|test_.*\.py$", re.I)


def sh(*a, cwd=None, timeout=600):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(" ".join(a) + "\n" + r.stderr[:400])
    return r.stdout


def _issue_text(repo: str, num) -> str | None:
    """Title+body of #num IFF it is a real issue. The issues API returns PRs
    too (a PR is an issue in GitHub's model), so check the pull_request
    marker instead of trusting an exit code -- `gh issue view <pr-number>`
    SUCCEEDS on PRs, which is how task pr3653 ended up carrying PR #2969's
    body as its problem statement."""
    r = subprocess.run(["gh", "api", f"repos/{repo}/issues/{num}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    d = json.loads(r.stdout)
    if "pull_request" in d:
        return None
    return (d["title"] + "\n\n" + (d.get("body") or "")).strip()


def problem_statement(repo: str, pr: int, meta: dict) -> str:
    """The agent must get the PROBLEM, not the PR author's solution.

    Sources, in trust order:
    1. GitHub's own issue linkage (closingIssuesReferences) -- authoritative.
    2. Keyword-linked numbers in the PR text (fixes/closes/resolves #N).
       A bare cross-referenced #N is NEVER followed: "regression introduced
       by #N" names a DIFFERENT PR (measured: that attached PR #2969's body
       to task pr3653 and poisoned the cell grid).
    3. The PR title alone -- never the PR body, which routinely describes
       the fix and would leak the answer.
    Every candidate number is verified to be an actual issue (not a PR)."""
    r = subprocess.run(["gh", "pr", "view", str(pr), "-R", repo,
                        "--json", "closingIssuesReferences"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        for ref in (json.loads(r.stdout).get("closingIssuesReferences") or []):
            if (got := _issue_text(repo, ref.get("number"))) is not None:
                return got
    text = meta["title"] + " " + (meta.get("body") or "")
    for num in re.findall(
            r"(?i)\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)[:\s]+#(\d+)", text):
        if (got := _issue_text(repo, num)) is not None:
            return got
    return meta["title"].strip()


def build(repo: str, pr: int, clone_root: str) -> dict:
    root = Path(clone_root) / repo.replace("/", "__")
    if not root.exists():
        # blobless partial clone: full history (needed for base/diff), blobs on
        # demand -- minutes faster than a full clone on large repos like django.
        sh("git", "clone", "--quiet", "--filter=blob:none",
           f"https://github.com/{repo}.git", str(root), timeout=600)
    meta = json.loads(sh("gh", "pr", "view", str(pr), "-R", repo, "--json",
                         "title,body,mergeCommit,baseRefOid,files"))
    merge = meta["mergeCommit"]["oid"]
    # The merge/squash commit is on the default branch (already in the blobless
    # clone; commit objects are present, blobs fetched on demand). No pull-ref
    # fetch needed -- those are pruned for merged PRs. base = its first parent.
    sh("git", "-C", str(root), "fetch", "--quiet", "origin", merge, timeout=300)
    parents = sh("git", "-C", str(root), "rev-list", "--parents", "-n", "1", merge).split()
    base = parents[1]
    # full PR diff, split into gold (source) vs test by file
    files = [f["path"] for f in meta["files"]]
    src = [f for f in files if not TEST_RE.search(f)]
    tst = [f for f in files if TEST_RE.search(f)]
    gold = sh("git", "-C", str(root), "diff", f"{base}..{merge}", "--", *src) if src else ""
    tpatch = sh("git", "-C", str(root), "diff", f"{base}..{merge}", "--", *tst) if tst else ""
    problem = problem_statement(repo, pr, meta)
    return {
        "instance_id": f"{repo.replace('/', '__')}__pr{pr}",
        "repo": repo, "pr": pr, "base_commit": base, "merge_commit": merge,
        "problem_statement": problem,
        "patch": gold, "test_patch": tpatch,
        "test_modules": sorted({f for f in tst}),
        "src_files": src,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("pr", type=int)
    ap.add_argument("--clone-root", default=str(Path.home() / "gvg-corpus" / "e2e-2026"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    Path(a.clone_root).mkdir(parents=True, exist_ok=True)
    t = build(a.repo, a.pr, a.clone_root)
    dst = a.out or f"tasks-e2e/{t['instance_id']}.json"
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(json.dumps(t, indent=2))
    print(f"{t['instance_id']}: base={t['base_commit'][:10]} "
          f"src={len(t['src_files'])} test_mods={len(t['test_modules'])} "
          f"gold={len(t['patch'])}b test_patch={len(t['test_patch'])}b -> {dst}")
    print("  test modules:", t["test_modules"])
