#!/usr/bin/env python3
"""Can each task be SCORED at all? Gold must resolve, empty must not.

A task whose GOLD patch does not score resolved is unscoreable — usually a
container/build problem, not a bad task — and including it in a run buys
cells whose correctness cannot be judged. That is how ~$100 of
efficiency-only numbers got produced before 2026-08-16. Runs Docker only:
no API spend.
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import docker_eval
from score_cell import scoreable
docker_eval.CLONE_ROOT = Path.home() / ".cache/prism-research/swebench-repos"

tasks = json.load(open(sys.argv[1]))
OFFICIAL = "--official" in sys.argv
scorer = docker_eval.score_official if OFFICIAL else (lambda t, p: docker_eval.score(scoreable(t), p))
print(f"scoring via {'OFFICIAL SWE-bench-Live images' if OFFICIAL else 'hand-rolled python:3.12'}")
out = {}
for i, t in enumerate(tasks, 1):
    tid = t["instance_id"]; t0 = time.time()
    try:
        g = scorer(t, t["patch"])
        e = scorer(t, "") if g.get("resolved") else {"resolved": None}
    except Exception as ex:                                    # noqa: BLE001
        g, e = {"resolved": None, "error": str(ex)[:150]}, {"resolved": None}
    ok = bool(g.get("resolved")) and e.get("resolved") is False
    out[tid] = {"gold": g, "empty": e, "scoreable": ok}
    print(f"[{i:2}/{len(tasks)}] {'OK  ' if ok else 'UNSCOREABLE'} {tid[:44]:44} "
          f"gold={g.get('resolved')} empty={e.get('resolved')} n={g.get('n_run')} "
          f"[{time.time()-t0:.0f}s] {g.get('error','')}", flush=True)
    json.dump(out, open(sys.argv[2], "w"), indent=1)
n = sum(1 for v in out.values() if v["scoreable"])
print(f"\nSCOREABLE: {n}/{len(tasks)}")
