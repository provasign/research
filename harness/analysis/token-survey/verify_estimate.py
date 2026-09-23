"""Estimate for direction #2 (verify owns the test turn) from guard-fix-run transcripts."""
import json, re, datetime, time
from pathlib import Path
from collections import defaultdict
ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
files = sorted((f.stat().st_mtime, f) for d in ROOT.iterdir() if d.is_dir() and "e2e-run" in d.name
               for f in d.glob("*.jsonl") if start <= f.stat().st_mtime <= end)
results = json.loads((RESDIR/"results.json").read_text())

def ctext(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(i.get("text","") for i in c if isinstance(i,dict) and "text" in i)
    return json.dumps(c) if c is not None else ""

TEST_CMD = re.compile(r"\b(mvn|gradlew?|go test|pytest|python3? -m pytest|npm test|npm run test|cargo test|make (test|check)|ctest|tox|unittest|jest|mocha)\b")
BUILD_ONLY = re.compile(r"\b(mvn\s+(-q\s+)?(compile|clean compile|clean install -DskipTests|compile test-compile)|go build|go vet|npm run build|cargo build|make\b(?!.*test))")
TARGETED = re.compile(r"(-Dtest=|-run\s|::|\btests?/\S+\.(py|js|ts)\b|\s-k\s|--tests\s|\.java\b.*-Dtest|mvn.*-pl\s)")
FAIL_TXT = re.compile(r"(BUILD FAILURE|FAIL(ED|URE)?\b|Tests run:.*Failures: [1-9]|error:|Error:|Exception|assert(ion)?\s*(error|failed)|exit code [1-9]|panic:)", re.I)
TRUNC = re.compile(r"(truncated|lines? omitted|\.\.\. \d+ more)", re.I)

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

for arm,idx in (("PRISM",1),("NATIVE",0)):
    agg=defaultdict(int); per_outcome=defaultdict(lambda: defaultdict(list))
    for i,task in enumerate(results):
        ev=events(files[2*i+idx][1]); n=len(ev)
        resolved=(task["prism"] if idx else task["native"])["resolved"]
        runs=0; targeted=0; failing=0; build_only=0; out_bytes=0; rebilled=0; trunc=0
        chain=0; collapsible=0; last_was_test=False
        diag_turns_after_fail=0; fails_with_next_edit=0
        for k,e in enumerate(ev):
            is_test=False
            if e["name"]=="Bash":
                cmd=str(e["input"].get("command",""))
                if TEST_CMD.search(cmd) or BUILD_ONLY.search(cmd):
                    is_test=True; runs+=1
                    if BUILD_ONLY.search(cmd) and not TEST_CMD.search(cmd): build_only+=1
                    if TARGETED.search(cmd): targeted+=1
                    fail = e["err"] or bool(FAIL_TXT.search(e["text"][:4000]))
                    if fail:
                        failing+=1
                        # diagnostic tool turns between this failing run and the next Edit
                        d=0
                        for nxt in ev[k+1:]:
                            if nxt["name"] in ("Edit","Write"): fails_with_next_edit+=1; break
                            d+=1
                        else: d=0
                        diag_turns_after_fail+=d
                    out_bytes+=len(e["text"]); rebilled+=len(e["text"])*(n-k-1)
                    if TRUNC.search(e["text"]): trunc+=1
            if is_test:
                if last_was_test: collapsible+=1
                last_was_test=True
            elif e["name"] in ("Edit","Write"):
                last_was_test=False
            # other tools (Read/Grep/prism) between two test runs don't break the chain only if no edit — keep last_was_test
        agg["sessions"]+=1; agg["runs"]+=runs; agg["targeted"]+=targeted; agg["failing"]+=failing
        agg["build_only"]+=build_only; agg["out_bytes"]+=out_bytes; agg["rebilled"]+=rebilled; agg["trunc"]+=trunc
        agg["collapsible"]+=collapsible; agg["diag"]+=diag_turns_after_fail; agg["fails_edit"]+=fails_with_next_edit
        agg["tools"]+=n
        o="resolved" if resolved else "FAILED"
        per_outcome[o]["runs"].append(runs); per_outcome[o]["failing"].append(failing); per_outcome[o]["tools"].append(n)
    s=agg["sessions"]
    print(f"\n=== {arm} arm ({s} sessions, {agg['tools']} tool turns) ===")
    print(f"build/test Bash runs: {agg['runs']} ({agg['runs']/s:.1f}/session)  build-only: {agg['build_only']}  targeted tests: {agg['targeted']} ({100*agg['targeted']/max(agg['runs'],1):.0f}%)")
    print(f"failing runs: {agg['failing']} ({100*agg['failing']/max(agg['runs'],1):.0f}%)  followed by an edit: {agg['fails_edit']}  diagnostic tool turns between a failing run and the next edit: {agg['diag']} ({agg['diag']/max(agg['fails_edit'],1):.1f} per fail→edit)")
    print(f"back-to-back test/build runs with no edit between (collapsible): {agg['collapsible']} ({agg['collapsible']/s:.2f}/session)")
    print(f"test output bytes: {agg['out_bytes']/1024:.0f} KB total, {agg['out_bytes']/max(agg['runs'],1):,.0f} B/run; re-billed footprint (bytes × later turns): {agg['rebilled']/1024/1024:.1f} MB-turns; truncated outputs: {agg['trunc']}")
    for o,d in per_outcome.items():
        k=len(d["runs"])
        print(f"  {o:8s} n={k:2d}  runs/session={sum(d['runs'])/k:.1f}  failing/session={sum(d['failing'])/k:.1f}  tool turns/session={sum(d['tools'])/k:.1f}")
