#!/usr/bin/env python3
"""Build + validate mined JS/TS candidates into e2e tasks (resumable).

JS analogue of promote_go.py / promote_java.py, using js_eval (node:20 docker
fail->pass; mocha for express, vitest for the TypeScript repos). Writes
tasks/e2e/<iid>.json for valid ones; appends every outcome, with its reject
reason, to results/mining/promoted_js.jsonl.

Gates, cheapest first:
  - the prompt comes from a linked ISSUE (prompt_source "issue"), never the PR
    body or title;
  - the PR touches source AND tests, and nothing else that changes behaviour
    (package.json, lockfiles, configs, fixtures -> reject);
  - --runs N (default 2) docker validations of each side: FAIL->PASS must be
    identical across runs (flaky -> reject), PASS->PASS keeps only tests that
    pass in every run.

Usage: python3 build/promote_js.py [--runs 2] [--only PR,PR] cands.json ...
"""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse, json, glob, time
from pathlib import Path

import js_eval

TASKS = Path("tasks/e2e")
LOG = Path("results/mining/promoted_js.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)
REPO_DIR = js_eval.REPO_DIR
ALIASES = {"unjs/h3": "h3js/h3"}  # GitHub redirect; the canonical name is the key

ap = argparse.ArgumentParser()
ap.add_argument("cands", nargs="*")
ap.add_argument("--runs", type=int, default=2)
ap.add_argument("--only", default="", help="comma-separated PR numbers")
a = ap.parse_args()
only = {int(x) for x in a.only.split(",") if x}

done = set()
if LOG.exists():
    for l in LOG.read_text().splitlines():
        try: done.add(json.loads(l)["instance_id"])
        except Exception: pass

cands = []
for f in a.cands or glob.glob("results/mining/*.cands.json"):
    for c in json.load(open(f)):
        c["repo"] = ALIASES.get(c.get("repo"), c.get("repo"))
        if c["repo"] in REPO_DIR and (not only or c["pr"] in only):
            cands.append(c)


def log(entry):
    with LOG.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


print(f"{len(cands)} js/ts candidates, {len(done)} already done\n")
for c in cands:
    repo, pr = c["repo"], c["pr"]
    iid = f"{repo.replace('/', '__')}__pr{pr}"
    if iid in done:
        continue
    rd = REPO_DIR[repo]
    base_entry = {"instance_id": iid, "repo": repo, "pr": pr, "title": c.get("title", ""),
                  "churn": c.get("churn")}
    try:
        task = js_eval.build_task(rd, repo, pr)
    except Exception as e:
        print(f"  {iid}: ERROR build {e}")
        log({**base_entry, "valid": False, "reject": "build_error", "error": str(e)[:200]})
        continue
    reject = None
    if task.get("prompt_source") != "issue":
        reject = "no_linked_issue"
    elif not task["src_files"] or not task["test_modules"]:
        reject = "no_src_or_no_tests"
    elif task.get("other_files"):
        reject = "other_files:" + ",".join(task["other_files"][:4])
    if reject:
        print(f"  {iid}: REJECT {reject}")
        log({**base_entry, "valid": False, "reject": reject})
        continue
    t0 = time.time()
    try:
        v = js_eval.validate(rd, repo, task, runs=a.runs)
    except Exception as e:
        print(f"  {iid}: ERROR validate {e}")
        log({**base_entry, "valid": False, "reject": "validate_error", "error": str(e)[:200]})
        continue
    reject = (None if v["valid"] else
              "flaky_f2p" if v["flaky"] else
              # e.g. pnpm 11 / nub packageManager, or a stale lockfile: the
              # base commit cannot be installed on node 20
              "install_failed" if "INSTALL_FAILED" in js_eval.LAST_LOG["text"] else
              "suite_did_not_run" if not v["n_before"] or not v["n_after"] else "no_f2p")
    entry = {**base_entry, "valid": v["valid"], "reject": reject,
             "n_f2p": len(v["fail_to_pass"]), "n_p2p": len(v["pass_to_pass"]),
             "n_before_runs": v["n_before_runs"], "n_after_runs": v["n_after_runs"],
             "flaky": v["flaky"][:5], "gold_flaky": v["gold_flaky"][:5],
             "secs": round(time.time() - t0)}
    print(f"  {iid}: valid={v['valid']} reject={reject} f2p={len(v['fail_to_pass'])} "
          f"p2p={len(v['pass_to_pass'])} before={v['n_before_runs']} after={v['n_after_runs']} "
          f"gold_flaky={len(v['gold_flaky'])} {entry['secs']}s")
    log(entry)
    if v["valid"]:
        mocha = js_eval.RUNNER.get(repo, "vitest") == "mocha"
        task.update(fail_to_pass=v["fail_to_pass"], pass_to_pass=v["pass_to_pass"],
                    lang="js" if mocha else "ts", build="mocha" if mocha else "vitest",
                    validation_runs=a.runs)
        TASKS.mkdir(parents=True, exist_ok=True)
        (TASKS / f"{iid}.json").write_text(json.dumps(task, indent=2))
