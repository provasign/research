"""Mine -> build -> Docker-validate a JAVA repo's 2026 candidates into a task
set, for run_e2e.py / java_eval.py. Same contract as build_pilot_set.py (the
Python pipeline) but for Maven repos: candidates() below is the Java-flavored
mine_2026_tasks.candidates (src/test/**/*.java conventions instead of pytest),
and validation goes through java_eval.build_task/validate (Docker Maven),
not docker_eval.

Keeps only tasks whose test genuinely discriminates (non-empty fail_to_pass on
base+tests, passing with gold). Writes each validated task to tasks-e2e/ and a
manifest. Idempotent: already-validated tasks (with fail_to_pass) are skipped.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import traceback
from pathlib import Path

import java_eval

OUT = Path("tasks-e2e")

# apache/commons-* use JIRA ("[COLLECTIONS-895]"), not GitHub "#N" issue
# linking -- the GitHub-issue-reference pattern (proven on jackson-databind,
# which links "#N") matched ZERO of this repo's PRs even though most titles
# are plainly bugfixes ("Fix Flat3Map...", "Reject out-of-range index...").
# Verified against 60 real merged 2026 titles before writing this regex.
BUG_RE = re.compile(
    r"^(fix|reject|prevent|correct|clamp|do not|don.t|remove stale|"
    r"increment|keep\b.*\bin sync)\b|\b[A-Z]+-\d+\b", re.I)
TEST_RE = re.compile(r"(^|/)src/test/.*\.java$")
SRC_RE = re.compile(r"(^|/)src/main/.*\.java$")
SKIP_RE = re.compile(r"\b(bump|merge|revert|typo|changelog|release note|"
                     r"pre-commit|github action|\bci\b)\b", re.I)


def gh_json(*args: str):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return json.loads(r.stdout)


def candidates(repo: str, limit: int, year: str = "2026"):
    prs = gh_json("pr", "list", "-R", repo, "--state", "merged", "--limit", str(limit),
                  "--json", "number,title,mergedAt,labels,body")
    out = []
    for p in prs:
        if not (p["mergedAt"] or "").startswith(year):
            continue
        title = p["title"]
        if SKIP_RE.search(title):
            continue
        labels = {l["name"].lower() for l in p.get("labels", [])}
        is_bug = bool(BUG_RE.search(title) or BUG_RE.search(p.get("body") or ""))
        is_feat = bool(labels & {"feature", "enhancement", "new feature"})
        if not (is_bug or is_feat):
            continue
        files = gh_json("pr", "view", str(p["number"]), "-R", repo, "--json", "files")["files"]
        paths = [f["path"] for f in files]
        has_test = any(TEST_RE.search(x) for x in paths)
        has_src = any(SRC_RE.search(x) for x in paths)
        churn = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
        if not (has_test and has_src) or churn > 400 or len(paths) > 25:
            continue
        out.append({"instance_id": f"{repo.replace('/', '__')}__pr{p['number']}",
                    "repo": repo, "pr": p["number"], "merged_at": p["mergedAt"],
                    "kind": "bug" if is_bug else "feature", "title": title,
                    "churn": churn, "n_files": len(paths)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="owner/name, e.g. google/guava")
    ap.add_argument("--repo-dir", required=True, help="local clone path")
    ap.add_argument("--scan", type=int, default=80)
    ap.add_argument("--max", type=int, default=8, help="stop after this many VALID tasks")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    repo_dir = Path(a.repo_dir)

    cands = candidates(a.repo, a.scan)
    print(f"# {len(cands)} candidates in {a.repo}; validating for fail->pass\n", flush=True)
    validated = []
    for c in cands:
        if len(validated) >= a.max:
            break
        iid = c["instance_id"]
        dst = OUT / f"{iid}.json"
        try:
            if dst.exists() and json.loads(dst.read_text()).get("fail_to_pass"):
                validated.append(iid); print(f"  SKIP  {iid} (already valid)", flush=True); continue
            task = java_eval.build_task(repo_dir, c["repo"], c["pr"])
            if not task["test_patch"].strip() or not task["test_classes"]:
                print(f"  DROP  {iid}: no usable test patch/classes", flush=True); continue
            v = java_eval.validate(repo_dir, task)
            if v["valid"]:
                task.update(kind=c["kind"], fail_to_pass=v["fail_to_pass"],
                           pass_to_pass=v["pass_to_pass"], lang="java",
                           build="maven", task_kind=c["kind"])
                dst.write_text(json.dumps(task, indent=2))
                validated.append(iid)
                print(f"  OK    {iid}  F2P={len(v['fail_to_pass'])} P2P={len(v['pass_to_pass'])} [{c['kind']}]", flush=True)
            else:
                print(f"  DROP  {iid}: no discriminating test (before {v['n_before']}/after {v['n_after']})", flush=True)
        except Exception as e:
            print(f"  ERR   {iid}: {str(e)[:150]}", flush=True)
            traceback.print_exc()
    (OUT / f"manifest.{a.repo.replace('/','__')}.json").write_text(json.dumps(validated, indent=2))
    print(f"\n# {len(validated)} validated tasks -> {OUT}/manifest.{a.repo.replace('/','__')}.json", flush=True)


if __name__ == "__main__":
    main()
