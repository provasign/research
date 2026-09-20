#!/usr/bin/env python3
"""Build + go-test-validate mined Go candidates into e2e tasks (resumable).

Go analogue of promote_java.py, using go_eval (golang docker fail->pass).
Writes tasks/e2e/<iid>.json for valid ones; appends to
results/mining/promoted_go.jsonl.
"""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import json, sys, glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import go_eval

TASKS = Path("tasks/e2e")
LOG = Path("results/mining/promoted_go.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)
REPO_DIR = go_eval.REPO_DIR

done = set()
if LOG.exists():
    for l in LOG.read_text().splitlines():
        try: done.add(json.loads(l)["instance_id"])
        except Exception: pass

cands = []
for f in sys.argv[1:] or glob.glob("results/mining/*.cands.json"):
    cands += [c for c in json.load(open(f)) if c.get("repo") in go_eval.REPO_DIR]

print(f"{len(cands)} go candidates, {len(done)} already done\n")
for c in cands:
    repo, pr = c["repo"], c["pr"]
    iid = f"{repo.replace('/', '__')}__pr{pr}"
    if iid in done:
        continue
    rd = REPO_DIR[repo]
    try:
        task = go_eval.build_task(rd, repo, pr)
        v = go_eval.validate(rd, task)
    except Exception as e:
        print(f"  {iid}: ERROR {e}")
        LOG.open("a").write(json.dumps({"instance_id": iid, "repo": repo, "pr": pr,
                                        "valid": False, "error": str(e)[:200]}) + "\n")
        continue
    entry = {"instance_id": iid, "repo": repo, "pr": pr, "title": c.get("title", ""),
              "churn": c.get("churn"), "valid": v["valid"],
              "n_f2p": len(v["fail_to_pass"]), "n_before": v["n_before"], "n_after": v["n_after"]}
    print(f"  {iid}: valid={v['valid']} f2p={len(v['fail_to_pass'])} "
          f"before={v['n_before']} after={v['n_after']}")
    LOG.open("a").write(json.dumps(entry) + "\n")
    if v["valid"]:
        task.update(fail_to_pass=v["fail_to_pass"], pass_to_pass=v["pass_to_pass"],
                    lang="go", build="go-test")
        TASKS.mkdir(parents=True, exist_ok=True)
        (TASKS / f"{iid}.json").write_text(json.dumps(task, indent=2))
