"""Does change-impact deliver the required set that grep buries?

Per oracle task: grep the target's leaf name (whole word), and run
change-impact. Score BOTH against the task's compiler-grade ground truth,
at file granularity (grep gives lines, the oracle gives sites; files are the
common unit). Deterministic, no LLM.

  grep   -> every file containing the name: high recall, unknown precision
  impact -> the resolved required set
"""
import json, re, subprocess, sys
from pathlib import Path
PRISM=str(Path.home()/"bin"/"prism")
TEST=re.compile(r"(^|/)(tests?|testing)/|_test\.|test_|\.test\.|/test/",re.I)

def sh(*a,cwd=None,t=300):
    return subprocess.run(a,cwd=cwd,capture_output=True,text=True,timeout=t).stdout

def gt_files(task):
    out=set()
    for s in task["ground_truth"]:
        f=s.get("file") if isinstance(s,dict) else str(s).split(":")[0]
        if f: out.add(f.lstrip("./"))
    return out

def leaf(task):
    m=re.search(r"#(\w+)",task.get("pr","")) or re.search(r"\b(\w+)\.(\w+)\b",task["prompt"])
    return m.group(1) if m and m.lastindex==1 else (m.group(2) if m else None)

rows=[]
for tp in sys.argv[1:]:
    task=json.loads(Path(tp).read_text())
    repo=Path(task["workdir"]); name=leaf(task)
    if not repo.exists() or not name: continue
    gt=gt_files(task)
    if not gt: continue
    g=set()
    for line in sh("rg","--no-config","-l","--word-regexp","--fixed-strings","-e",name,"--",".",cwd=str(repo)).splitlines():
        f=line.lstrip("./")
        if not TEST.search(f): g.add(f)
    q=task["pr"].split(":")[-1].replace("#",".").split("(")[0].split(".")[-2:]
    try:
        d=json.loads(sh(PRISM,"change-impact",".".join(q),"--format","json",str(repo)))
        imp={s["filePath"].lstrip("./") for k in ("declarations","family","callers","declaringTypes") for s in (d.get(k) or []) if s.get("filePath") and not TEST.search(s["filePath"])}
    except Exception:
        imp=set()
    rows.append({"task":task["id"],"gt":len(gt),"grep_files":len(g),"impact_files":len(imp),
                 "grep_recall":round(len(g&gt)/len(gt),2),"impact_recall":round(len(imp&gt)/len(gt),2),
                 "grep_prec":round(len(g&gt)/len(g),2) if g else 0,
                 "impact_prec":round(len(imp&gt)/len(imp),2) if imp else 0})
    print(f"{rows[-1]['task']:34} gt={len(gt):3} grep={len(g):4}(R{rows[-1]['grep_recall']} P{rows[-1]['grep_prec']}) impact={len(imp):4}(R{rows[-1]['impact_recall']} P{rows[-1]['impact_prec']})")
Path("runs/impact-vs-grep.json").write_text(json.dumps(rows,indent=2))
if rows:
    print(f"\nmean grep:   recall {sum(r['grep_recall'] for r in rows)/len(rows):.2f}  precision {sum(r['grep_prec'] for r in rows)/len(rows):.2f}")
    print(f"mean impact: recall {sum(r['impact_recall'] for r in rows)/len(rows):.2f}  precision {sum(r['impact_prec'] for r in rows)/len(rows):.2f}")
