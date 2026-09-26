"""Refinement: strict failure detection + what the back-to-back test chains actually are."""
import json, re, datetime, time
from pathlib import Path
from collections import defaultdict, Counter
ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/archive-2026-09-tainted/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
files = sorted((f.stat().st_mtime, f) for d in ROOT.iterdir() if d.is_dir() and "e2e-run" in d.name
               for f in d.glob("*.jsonl") if start <= f.stat().st_mtime <= end)
results = json.loads((RESDIR/"results.json").read_text())
def ctext(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(i.get("text","") for i in c if isinstance(i,dict) and "text" in i)
    return json.dumps(c) if c is not None else ""
TEST_CMD = re.compile(r"\b(mvn|gradlew?|go test|pytest|python3? -m pytest|npm test|npm run test|cargo test|make (test|check)|ctest|tox|unittest|jest|mocha|go build|go vet|npm run build|cargo build)\b")
STRICT_FAIL = re.compile(r"(BUILD FAILURE|Tests run: \d+, Failures: [1-9]|Tests run: \d+, Failures: \d+, Errors: [1-9]|^FAIL\b|^--- FAIL|\b\d+ failed\b|FAILED \(|npm ERR!|error\[E\d+\]|test result: FAILED|\[ERROR\] .*COMPILATION ERROR|cannot find symbol|undefined: )", re.M)
def norm(cmd):
    return re.sub(r"\s+"," ",cmd.strip())[:90]
def events(f):
    tool_use={}; ev=[]
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        typ=j.get("type"); msg=j.get("message") or {}
        if typ=="assistant":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_use":
                    tool_use[c["id"]]=len(ev); ev.append({"name":c.get("name",""),"input":c.get("input") or {},"text":"","err":False})
        elif typ=="user":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_result" and c.get("tool_use_id") in tool_use:
                    e=ev[tool_use[c["tool_use_id"]]]; e["text"]=ctext(c.get("content")); e["err"]=bool(c.get("is_error"))
    return ev
agg=Counter(); chain_kinds=Counter(); examples=[]; between=Counter()
outcome=defaultdict(Counter)
for i,task in enumerate(results):
    ev=events(files[2*i+1][1]); resolved=task["prism"]["resolved"]
    o="resolved" if resolved else "FAILED"
    prev=None; prev_k=None
    for k,e in enumerate(ev):
        if e["name"] in ("Edit","Write"): prev=None; continue
        if e["name"]!="Bash": continue
        cmd=str(e["input"].get("command",""))
        if not TEST_CMD.search(cmd): continue
        agg["runs"]+=1; outcome[o]["runs"]+=1
        fail=e["err"] or bool(STRICT_FAIL.search(e["text"]))
        if e["err"]: agg["is_error"]+=1
        if fail:
            agg["fail"]+=1; outcome[o]["fail"]+=1
            nxt=ev[k+1:]; d=0; edited=False
            for x in nxt:
                if x["name"] in ("Edit","Write"): edited=True; break
                d+=1
            if edited: agg["fail_then_edit"]+=1; agg["diag_turns"]+=d
            else: agg["fail_no_edit_after"]+=1
        if prev is not None:
            agg["chain"]+=1
            same = norm(cmd)==norm(prev)
            kind = "same-command rerun" if same else ("passing→another" if not prev_fail else "failing→another")
            chain_kinds[kind]+=1
            gap=k-prev_k-1; between[min(gap,5)]+=1
            if len(examples)<14 and not same: examples.append((o, norm(prev)[:60], "→", norm(cmd)[:60], f"gap={gap}", "prevFAIL" if prev_fail else "prevPASS"))
        prev=cmd; prev_k=k; prev_fail=fail
print(f"build/test runs: {agg['runs']}  strict-failing: {agg['fail']} (is_error flag set on {agg['is_error']})")
print(f"failing → later edit: {agg['fail_then_edit']} (diagnostic tool turns between: {agg['diag_turns']}, {agg['diag_turns']/max(agg['fail_then_edit'],1):.1f} each); failing with NO edit afterwards: {agg['fail_no_edit_after']}")
print(f"back-to-back runs (no edit between): {agg['chain']}  by kind: {dict(chain_kinds)}")
print(f"tool turns between the two runs of a chain: {dict(sorted(between.items()))}  (5 = 5+)")
for o,c in outcome.items(): print(f"  {o}: runs={c['runs']} failing={c['fail']}")
print("\nexamples of different-command chains (outcome, prev → next):")
for ex in examples: print("  ", " ".join(ex))
