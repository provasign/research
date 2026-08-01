#!/usr/bin/env python3
"""Build + Maven-validate mined Java candidates into e2e tasks (resumable).

Java analogue of promote_tasks.py, using java_eval (maven fail->pass). Writes
tasks-e2e/<iid>.json for valid ones; appends to runs/mining/promoted_java.jsonl.
"""
import json, sys, glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import java_eval

TASKS = Path("tasks-e2e")
LOG = Path("runs/mining/promoted_java.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)
REPO_DIR = java_eval.REPO_DIR

done = set()
if LOG.exists():
    for l in LOG.read_text().splitlines():
        try: done.add(json.loads(l)["instance_id"])
        except Exception: pass

cands = []
for f in sys.argv[1:] or glob.glob("runs/mining/*.cands.json"):
    cands += [c for c in json.load(open(f)) if "jackson" in c.get("repo", "") or "commons" in c.get("repo", "")]

print(f"{len(cands)} java candidates, {len(done)} already done\n")
for c in cands:
    repo, pr = c["repo"], c["pr"]
    iid = f"{repo.replace('/', '__')}__pr{pr}"
    if iid in done:
        print(f"  (skip) {iid}"); continue
    rd = REPO_DIR.get(repo)
    row = {"instance_id": iid, "repo": repo, "pr": pr,
           "task_kind": c.get("task_kind"), "churn": c.get("churn")}
    try:
        task = java_eval.build_task(rd, repo, pr)
        v = java_eval.validate(rd, task)
        row.update(valid=v["valid"], n_f2p=len(v["fail_to_pass"]),
                   n_before=v["n_before"], n_after=v["n_after"])
        if v["valid"]:
            task.update(fail_to_pass=v["fail_to_pass"], pass_to_pass=v["pass_to_pass"],
                        lang="java", build="maven", task_kind=c.get("task_kind"))
            (TASKS / f"{iid}.json").write_text(json.dumps(task, indent=2))
    except Exception as e:
        row.update(valid=False, error=f"{type(e).__name__}: {str(e)[:160]}")
    with LOG.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    print(f"  [{'OK  ' if row.get('valid') else 'FAIL'}] {iid:34} "
          f"{row.get('task_kind'):10} f2p={row.get('n_f2p','-')} {row.get('error','')[:60]}")

import collections
rows = [json.loads(l) for l in LOG.read_text().splitlines()]
seen = {r["instance_id"]: r for r in rows}; rows = list(seen.values())
valid = [r for r in rows if r.get("valid")]
print(f"\n=== {len(valid)}/{len(rows)} validated ===")
print("by kind:", dict(collections.Counter(r["task_kind"] for r in valid)))
