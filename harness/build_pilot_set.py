"""Mine -> build -> Docker-validate a repo's 2026 candidates into a task set.

Keeps only tasks whose test genuinely discriminates (non-empty FAIL_TO_PASS on
base+tests, passing with gold). Writes each validated task to tasks-e2e/ and a
manifest. Docker-heavy; safe to run in the background. Idempotent: already-built
task files are reused, already-validated tasks (with fail_to_pass) are skipped.
"""
from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

import build_task
import docker_eval
import mine_2026_tasks

OUT = Path("tasks-e2e")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--scan", type=int, default=80)
    ap.add_argument("--max", type=int, default=15, help="stop after this many VALID tasks")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    cands = mine_2026_tasks.candidates(args.repo, args.scan)
    print(f"# {len(cands)} candidates in {args.repo}; validating for fail->pass\n", flush=True)
    validated = []
    for c in cands:
        if len(validated) >= args.max:
            break
        iid = c["instance_id"]
        dst = OUT / f"{iid}.json"
        try:
            if dst.exists() and json.loads(dst.read_text()).get("fail_to_pass"):
                validated.append(iid); print(f"  SKIP  {iid} (already valid)", flush=True); continue
            task = build_task.build(c["repo"], c["pr"], str(build_task.Path.home() / "gvg-corpus" / "e2e-2026"))
            if not task["test_patch"].strip():
                print(f"  DROP  {iid}: no test patch", flush=True); continue
            v = docker_eval.validate(task)
            if v["valid"]:
                task.update(kind=c["kind"], fail_to_pass=v["fail_to_pass"], pass_to_pass=v["pass_to_pass"])
                dst.write_text(json.dumps(task, indent=2))
                validated.append(iid)
                print(f"  OK    {iid}  F2P={len(v['fail_to_pass'])} P2P={len(v['pass_to_pass'])} [{c['kind']}]", flush=True)
            else:
                print(f"  DROP  {iid}: no discriminating test (before {v['n_before']}/after {v['n_after']})", flush=True)
        except Exception as e:
            print(f"  ERR   {iid}: {str(e)[:120]}", flush=True)
            traceback.print_exc()
    (OUT / f"manifest.{args.repo.replace('/','__')}.json").write_text(json.dumps(validated, indent=2))
    print(f"\n# {len(validated)} validated tasks -> {OUT}/manifest.{args.repo.replace('/','__')}.json", flush=True)


if __name__ == "__main__":
    main()
