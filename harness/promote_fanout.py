"""Promote fan-out candidates: build_task -> fanout_eval.validate -> tasks."""
import json
from pathlib import Path
import build_task, fanout_eval

CANDS = json.loads(Path("runs/fanout-candidates.json").read_text())
OUT = Path("tasks-e2e-fanout"); OUT.mkdir(exist_ok=True)
CLONE = str(Path.home() / "gvg-corpus" / "e2e-2026")
rows = []
for c in CANDS:
    tag = f"{c['repo']}#{c['pr']}"
    try:
        t = build_task.build(c["repo"], c["pr"], CLONE)
        t["kind"] = "fanout"; t["brief"] = c["brief"]; t["fanout_symbols"] = c["fanout_symbols"]
        v = fanout_eval.validate(t)
    except Exception as e:
        rows.append({"tag": tag, "ok": False, "err": str(e)[:200]}); print(f"{tag}: ERROR {str(e)[:120]}"); continue
    rows.append({"tag": tag, "ok": v["valid"], "reason": v.get("reason","")})
    if v["valid"]:
        t["test_modules"] = v["test_modules"]; t["gold_files"] = v["gold_files"]
        (OUT / f"{t['instance_id']}.json").write_text(json.dumps(t, indent=2))
        print(f"{tag}: VALID  modules={len(v['test_modules'])} green={v['n_green']} gold_files={len(v['gold_files'])}")
    else:
        print(f"{tag}: REJECT {v['reason']}")
Path("runs/fanout-promotion.json").write_text(json.dumps(rows, indent=2))
print(f"\n{sum(1 for r in rows if r.get('ok'))}/{len(CANDS)} promoted -> {OUT}/")
