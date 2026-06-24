"""Quick test of the completeness-gate mechanism (2-turn loop).

Turn 1: agent answers with TEXT tools only (the T arm).
Gate:   query the real graph (prism) for the changed symbols, take the sites it
        found that the agent did NOT list, and feed them back.
Turn 2: agent revises, judging each graph-flagged site (include if it must
        change, else skip) -- so precision can suffer if the agent accepts noise.

Scores turn-1 vs turn-2 on recall AND precision vs the oracle ground truth.
This is the real mechanism: graph-detected misses surfaced at the stop, agent
keeps judgment. It can fail either way (no recall gain, or precision loss).
"""
import json, subprocess, statistics, sys
from schema import Task, Answer, Site
from score import score
from arms import ARMS

TASK = Task.load("tasks/grafana-126004.json")
WT = "/Users/tapabratapal/gvg-corpus/wt-126004"
MODEL = "haiku"
SYMS = ["toSnowflakeRV", "subtractDurationFromSnowflake"]
TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
T_TOOLS = ARMS["T"].allowed_tools
T_PROMPT = ARMS["T"].prompt(TASK.prompt)


def claude(prompt, tools):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--allowedTools", ",".join(tools), "--model", MODEL]
    out = subprocess.run(cmd, cwd=WT, capture_output=True, text=True, timeout=900).stdout
    res = ""
    for l in out.splitlines():
        try:
            o = json.loads(l)
        except Exception:
            continue
        if o.get("type") == "result":
            res = o.get("result", "")
    return res


def graph_candidates():
    sites, cur = [], None
    for sym in SYMS:
        out = subprocess.run(["/Users/tapabratapal/bin/prism", "references", sym,
                              "--format", "text"], cwd=WT, capture_output=True, text=True).stdout
        for l in out.splitlines():
            s = l.strip()
            if s.endswith(".go") and "_test.go" not in s:
                cur = s
            elif " in " in s and cur:
                fn = s.split(" in ")[-1].strip()
                if not fn.startswith(("Test", "test")):   # drop test funcs
                    sites.append(f"{cur}:{fn}")
    return sorted(set(sites))


GCANDS = graph_candidates()
print(f"graph candidate set ({len(GCANDS)} sites): {GCANDS}\n")

rows = {"turn1": [], "turn2": []}
for t in range(1, TRIALS + 1):
    a1 = Answer.parse(claude(T_PROMPT, T_TOOLS))
    listed = {str(s) for s in a1.sites}
    missing = [s for s in GCANDS if s not in listed]
    gate = (T_PROMPT +
            f"\n\nYou previously gave this answer:\n"
            f"{json.dumps({'sites':[str(s) for s in a1.sites],'complete':a1.complete})}\n\n"
            f"A call-graph analysis reports these additional sites reference the "
            f"changed symbol(s) and you did not list them:\n{json.dumps(missing)}\n\n"
            f"For EACH, verify in the code and include it in your final list ONLY if "
            f"it must change for this task; omit it otherwise. Output ONLY the final JSON.")
    a2 = Answer.parse(claude(gate, T_TOOLS))
    c1 = score(TASK, a1, "T", t)
    c2 = score(TASK, a2, "gate", t)
    rows["turn1"].append((c1.recall, c1.precision, c1.overconfident))
    rows["turn2"].append((c2.recall, c2.precision, c2.overconfident))
    print(f"trial {t}: turn1 r={c1.recall:.3f} p={c1.precision:.3f} oc={c1.overconfident} "
          f"| missed {len(missing)} -> turn2 r={c2.recall:.3f} p={c2.precision:.3f} oc={c2.overconfident}")

print()
for k, v in rows.items():
    oc = sum(1 for x in v if x[2])
    print(f"{k}: recall={statistics.mean(x[0] for x in v):.3f}  "
          f"precision={statistics.mean(x[1] for x in v):.3f}  overconfident={oc}/{len(v)}")
