#!/usr/bin/env python3
"""Build + Docker-validate mined candidates into e2e tasks (resumable).

For each candidate PR: build the SWE-bench task (base/gold/test_patch), then
run docker_eval.validate to derive FAIL_TO_PASS (tests fail on base, pass on
base+gold). Keep only valid ones. Classify each as 'localized' (1 source file
touched) or 'multi_site' (>1) so the final set can be balanced -- the pilot's
flaw was being all-localized, exactly where completeness has no room to help.

Writes each validated task to tasks-e2e/<instance_id>.json and appends a row
to runs/mining/promoted.jsonl. Skips candidates already built/validated.
"""
import json, sys, glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_task, docker_eval

TASKS = Path("tasks-e2e")
LOG = Path("runs/mining/promoted.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)
CLONE = str(Path.home() / "gvg-corpus" / "e2e-2026")

done = set()
if LOG.exists():
    for line in LOG.read_text().splitlines():
        try: done.add(json.loads(line)["instance_id"])
        except Exception: pass

cands = []
for f in sys.argv[1:] or glob.glob("runs/mining/*.cands.json"):
    cands += json.load(open(f))
print(f"{len(cands)} candidates, {len(done)} already processed\n")

for c in cands:
    iid = c["instance_id"]
    if iid in done:
        print(f"  (skip) {iid}"); continue
    repo, pr = c["repo"], c["pr"]
    n_src = len([s for s in c.get("src_files", []) if s.endswith(".py")])
    kind = "localized" if n_src <= 1 else "multi_site"
    row = {"instance_id": iid, "repo": repo, "pr": pr, "task_kind": kind,
           "n_src": n_src, "churn": c.get("churn"), "title": c.get("title", "")[:60]}
    try:
        task = build_task.build(repo, pr, CLONE)
        task["kind"] = c.get("kind"); task["task_kind"] = kind
        v = docker_eval.validate(task)
        row.update(valid=v["valid"], n_f2p=len(v["fail_to_pass"]),
                   n_p2p=len(v["pass_to_pass"]))
        if v["valid"]:
            task.update(fail_to_pass=v["fail_to_pass"], pass_to_pass=v["pass_to_pass"])
            (TASKS / f"{iid}.json").write_text(json.dumps(task, indent=2))
    except Exception as e:
        row.update(valid=False, error=f"{type(e).__name__}: {str(e)[:160]}")
    with LOG.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    tag = "OK  " if row.get("valid") else "FAIL"
    print(f"  [{tag}] {iid:28} {kind:10} f2p={row.get('n_f2p','-')} "
          f"{row.get('error','')[:70]}")

# summary
rows = [json.loads(l) for l in LOG.read_text().splitlines()]
valid = [r for r in rows if r.get("valid")]
import collections
byrepo = collections.Counter(r["repo"] for r in valid)
bykind = collections.Counter(r["task_kind"] for r in valid)
print(f"\n=== {len(valid)}/{len(rows)} validated ===")
print("by repo:", dict(byrepo))
print("by kind:", dict(bykind))
