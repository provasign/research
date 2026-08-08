"""Promote mined meaningful candidates to verified e2e tasks.

For each candidate in runs/meaningful-candidates.json:
  build_task.build()  -> task JSON (base pin, gold/test patch split, issue text)
  docker_eval.validate() -> FAIL_TO_PASS derivation (fail on base+tests, pass
                            on base+tests+gold)
Valid tasks land in tasks-e2e-meaningful/; every verdict (including rejects,
with the reason) lands in runs/meaningful-promotion.json — a rejected
candidate is data, not noise.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_task
import docker_eval

CANDS = json.loads(Path("runs/meaningful-candidates.json").read_text())
OUT_DIR = Path("tasks-e2e-meaningful")
OUT_DIR.mkdir(exist_ok=True)
CLONE_ROOT = str(Path.home() / "gvg-corpus" / "e2e-2026")

rows = []
for c in CANDS:
    tag = f"{c['repo']}#{c['pr']}"
    try:
        task = build_task.build(c["repo"], c["pr"], CLONE_ROOT)
    except Exception as e:
        rows.append({"tag": tag, "stage": "build", "ok": False, "err": str(e)[:200]})
        print(f"{tag}: BUILD FAIL {str(e)[:120]}")
        continue
    if not task["patch"] or not task["test_patch"]:
        rows.append({"tag": tag, "stage": "build", "ok": False,
                     "err": "empty gold or test patch after split"})
        print(f"{tag}: REJECT empty patch split")
        continue
    try:
        v = docker_eval.validate(task)
    except Exception as e:
        rows.append({"tag": tag, "stage": "docker", "ok": False, "err": str(e)[:200]})
        print(f"{tag}: DOCKER FAIL {str(e)[:120]}")
        continue
    rec = {"tag": tag, "stage": "validate", "ok": v["valid"],
           "fail_to_pass": v["fail_to_pass"], "n_p2p": len(v["pass_to_pass"]),
           "issue_chars": c["issue_body_chars"], "src_files": c["src_files"],
           "functions_changed": c["functions_changed"]}
    rows.append(rec)
    if v["valid"]:
        task["fail_to_pass"] = v["fail_to_pass"]
        task["pass_to_pass"] = v["pass_to_pass"]
        dst = OUT_DIR / f"{task['instance_id']}.json"
        dst.write_text(json.dumps(task, indent=2))
        print(f"{tag}: VALID  f2p={len(v['fail_to_pass'])} p2p={len(v['pass_to_pass'])} -> {dst}")
    else:
        print(f"{tag}: REJECT no discriminating fail->pass "
              f"(before/after collected {v['n_before']}/{v['n_after']})")

Path("runs/meaningful-promotion.json").write_text(json.dumps(rows, indent=2))
valid = sum(1 for r in rows if r.get("ok"))
print(f"\n{valid}/{len(CANDS)} promoted -> {OUT_DIR}/  (verdicts: runs/meaningful-promotion.json)")
