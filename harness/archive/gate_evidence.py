"""Evidence run: the completeness gate as a capability equalizer.

For each task, run 2 turns for a weak model (Haiku):
  turn1: text tools only (the T arm).
  gate:  prism references for the changed symbol(s), production sites, scoped to
         the interface's subsystem (auto-derived modal path prefix of the GT) --
         a stand-in for a type-resolved gate. Feed back the ones the agent missed.
  turn2: agent revises, judging each (include only if it must change).

Reports turn1 vs turn2 recall/precision/over-confidence per task, then a
Haiku-gate vs Opus-text comparison (does a cheap model + gate reach frontier
quality?). Ambiguous names (Set, Cleanup) stress precision on purpose.
"""
import json, subprocess, statistics, collections
from pathlib import Path
from schema import Task, Answer, Site
from score import score
from arms import ARMS

MODEL = "haiku"
TRIALS = 5
CFG = [
    ("grafana-126004", "wt-126004", ["toSnowflakeRV", "subtractDurationFromSnowflake"]),
    ("grafana-122750", "wt-122750", ["GetById", "GetByLabel", "Set", "RemoveExpired", "Flush"]),
    ("grafana-120119", "wt-120119", ["GetManagedRoute", "GetManagedRoutes",
                                      "CreateManagedRoute", "UpdateManagedRoute", "DeleteManagedRoute"]),
    ("grafana-cleanup-impact", "wt-cleanup", ["Cleanup"]),
]
CORPUS = "/Users/tapabratapal/gvg-corpus"
PRISM = "/Users/tapabratapal/bin/prism"


def claude(prompt, tools, wt):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--allowedTools", ",".join(tools), "--model", MODEL]
    out = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=900).stdout
    res = ""
    for l in out.splitlines():
        try:
            o = json.loads(l)
        except Exception:
            continue
        if o.get("type") == "result":
            res = o.get("result", "")
    return res


def subsystem(task):  # modal 4-level path prefix of the GT sites (the interface's home)
    pref = collections.Counter("/".join(str(s).split(":")[0].split("/")[:4]) for s in task.ground_truth)
    return pref.most_common(1)[0][0]


def candidates(syms, wt, scope):
    sites, cur = [], None
    for sym in syms:
        out = subprocess.run([PRISM, "references", sym, "--format", "text"],
                             cwd=wt, capture_output=True, text=True).stdout
        for l in out.splitlines():
            s = l.strip()
            if s.endswith(".go") and "_test.go" not in s and "_mock" not in s and "/mock" not in s:
                cur = s
            elif " in " in s and cur and cur.startswith(scope):
                fn = s.split(" in ")[-1].strip()
                if not fn.startswith(("Test", "test")):
                    sites.append(f"{cur}:{fn}")
    return sorted(set(sites))


def opus_text(task_id):  # existing Opus-text data on disk
    p = Path(f"runs/{task_id}/summary.json")
    if not p.exists():
        return None
    s = json.loads(p.read_text())
    rs = [c["recall"] for c in s["ok"] if c["arm"] == "T"]
    return statistics.mean(rs) if rs else None


summary = {}
for tid, wtname, syms in CFG:
    task = Task.load(f"tasks/{tid}.json")
    wt = f"{CORPUS}/{wtname}"
    subprocess.run([PRISM, "index", "."], cwd=wt, capture_output=True)
    scope = subsystem(task)
    cands = candidates(syms, wt, scope)
    tprompt = ARMS["T"].prompt(task.prompt)
    t1s, t2s = [], []
    print(f"\n### {tid}  scope={scope}  gate-candidates={len(cands)}")
    for t in range(1, TRIALS + 1):
        a1 = Answer.parse(claude(tprompt, ARMS["T"].allowed_tools, wt))
        listed = {str(s) for s in a1.sites}
        missing = [s for s in cands if s not in listed]
        gate = (tprompt + f"\n\nYou previously answered:\n"
                f"{json.dumps({'sites':[str(s) for s in a1.sites],'complete':a1.complete})}\n\n"
                f"A call-graph analysis flags these sites referencing the changed "
                f"symbol(s), which you did not list:\n{json.dumps(missing)}\n\n"
                f"Verify each in the code; include it in your FINAL list only if it must "
                f"change for this task, else omit it. Output ONLY the final JSON.")
        a2 = Answer.parse(claude(gate, ARMS["T"].allowed_tools, wt))
        c1, c2 = score(task, a1, "T", t), score(task, a2, "gate", t)
        t1s.append((c1.recall, c1.precision, c1.overconfident))
        t2s.append((c2.recall, c2.precision, c2.overconfident))
        print(f"  t{t}: text r={c1.recall:.2f} p={c1.precision:.2f} oc={c1.overconfident}"
              f" | miss {len(missing)} -> gate r={c2.recall:.2f} p={c2.precision:.2f} oc={c2.overconfident}")
    summary[tid] = (t1s, t2s)

print("\n==== SUMMARY: Haiku text vs Haiku+gate vs Opus text ====")
print(f"{'task':24} {'Hk-text r/p/oc':18} {'Hk-gate r/p/oc':18} {'Opus-text r':10}")
for tid, (t1s, t2s) in summary.items():
    def agg(v):
        return (f"{statistics.mean(x[0] for x in v):.2f}/"
                f"{statistics.mean(x[1] for x in v):.2f}/"
                f"{sum(1 for x in v if x[2])}")
    ot = opus_text(tid)
    print(f"{tid:24} {agg(t1s):18} {agg(t2s):18} {('%.2f'%ot) if ot else 'n/a':10}")
