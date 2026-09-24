"""H3 A/B: control (main binary, verify optional) vs treatment (branch
h3-verify-steering: mandated verify testCoverage read before finishing),
19 movable tasks x 3 passes. Per-task resolves, hard-core coverage, verify
adoption (from transcripts), token ratio."""
import json
from pathlib import Path
from collections import defaultdict
R = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/h3-ab")
ROOT = Path.home() / ".claude" / "projects"
HARD = {"FasterXML__jackson-databind__pr6018","FasterXML__jackson-databind__pr6044",
 "FasterXML__jackson-databind__pr6052","FasterXML__jackson-databind__pr6076",
 "akheron__jansson__pr740","apache__commons-lang__pr1655","apache__commons-lang__pr1703",
 "gin-gonic__gin__pr4535","gin-gonic__gin__pr4805","pallets__click__pr3473",
 "pallets__click__pr3504","pallets__click__pr3678"}

def verify_called(sid):
    hits = list(ROOT.glob(f"*/{sid}.jsonl"))
    if not hits: return None
    for line in hits[0].read_text(errors="ignore").splitlines():
        if '"op": "verify"' in line or '"op":"verify"' in line:
            return True
    return False

per = defaultdict(lambda: {"c": [], "t": [], "ctok": 0, "ttok": 0, "cver": 0, "tver": 0, "cn": 0, "tn": 0})
for p in (1, 2, 3):
    for r in json.load(open(R / f"pass{p}" / "results.json")):
        e = per[r["task"]]
        e["c"].append(bool(r["native"]["resolved"])); e["t"].append(bool(r["prism"]["resolved"]))
        e["ctok"] += r["native"]["tokens"] or 0; e["ttok"] += r["prism"]["tokens"] or 0
        for arm, key in (("native", "c"), ("prism", "t")):
            v = verify_called(r[arm].get("session_id"))
            if v is not None:
                e[key + "n"] += 1
                if v: e[key + "ver"] += 1

tasks = sorted(per)
C = sum(sum(per[t]["c"]) for t in tasks); T = sum(sum(per[t]["t"]) for t in tasks)
cells = sum(len(per[t]["c"]) for t in tasks)
print(f"cells per arm: {cells}")
print(f"resolved: control {C}/{cells}   treatment {T}/{cells}")
hc_c = sum(1 for t in tasks if t in HARD and any(per[t]["c"])); hc_t = sum(1 for t in tasks if t in HARD and any(per[t]["t"]))
print(f"hard-core tasks (12) resolved at least once: control {hc_c}   treatment {hc_t}")
fl_c = sum(1 for t in tasks if t not in HARD and any(per[t]["c"])); fl_t = sum(1 for t in tasks if t not in HARD and any(per[t]["t"]))
print(f"flaky tasks (7) resolved at least once: control {fl_c}   treatment {fl_t}")
ctok = sum(per[t]["ctok"] for t in tasks); ttok = sum(per[t]["ttok"] for t in tasks)
print(f"tokens: control {ctok:,}  treatment {ttok:,}  ratio {ttok/ctok:.3f}")
cv = sum(per[t]["cver"] for t in tasks); cn = sum(per[t]["cn"] for t in tasks)
tv = sum(per[t]["tver"] for t in tasks); tn = sum(per[t]["tn"] for t in tasks)
print(f"verify called: control {cv}/{cn} sessions   treatment {tv}/{tn} sessions")
print(f"\n{'task':38s} {'hard':4s} control  treatment")
for t in tasks:
    e = per[t]
    print(f"{t:38s} {'HC' if t in HARD else '  ':4s} {sum(e['c'])}/3      {sum(e['t'])}/3")
