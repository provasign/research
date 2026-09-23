import json, re, datetime, time
from pathlib import Path
from collections import defaultdict
ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
files = []
for d in ROOT.iterdir():
    if not d.is_dir() or "e2e-run" not in d.name: continue
    for f in d.glob("*.jsonl"):
        mt = f.stat().st_mtime
        if start <= mt <= end: files.append((mt, f))
files.sort()
results = json.loads((RESDIR/"results.json").read_text())

def clen(c):
    if isinstance(c, str): return len(c)
    if isinstance(c, list):
        return sum(len(i.get("text","")) if isinstance(i,dict) and i.get("type")=="text" else len(json.dumps(i)) for i in c)
    return len(json.dumps(c)) if c is not None else 0
def ctext(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(i.get("text","") for i in c if isinstance(i,dict) and "text" in i)
    return ""

def classify_bash(cmd):
    c = cmd.strip()
    first = re.split(r"[\s|;&]", c, 1)[0] if c else ""
    if re.search(r"\b(mvn|gradle|gradlew|go test|go build|go vet|pytest|python -m pytest|python3 -m pytest|npm (test|run)|make|cargo|tox|unittest|ctest|cmake)\b", c): return "build/test"
    if first in ("cat","sed","head","tail","less","awk","wc"): return "file-read(cat/sed/head)"
    if first in ("ls","find","tree"): return "listing(ls/find)"
    if first in ("grep","rg","ag"): return "grep/rg"
    if first == "git": return "git"
    if first in ("cd","pwd","echo","true","which","env","export"): return "shell-misc"
    if first in ("python","python3","node","java"): return "run-script"
    return "other"

PATH_RE = re.compile(r"[\w./-]+\.(?:java|py|go|js|ts|c|h|cpp|rb|rs|php|kt|swift|m)\b")

def analyze(f):
    events = []  # ordered: (kind, name, input, result_len, result_text)
    tool_use = {}
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        typ=j.get("type"); msg=j.get("message") or {}
        if typ=="assistant":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_use":
                    tool_use[c["id"]]=len(events)
                    events.append({"name":c.get("name",""),"input":c.get("input") or {},"len":0,"text":""})
        elif typ=="user":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_result" and c.get("tool_use_id") in tool_use:
                    e=events[tool_use[c["tool_use_id"]]]
                    e["len"]=clen(c.get("content")); e["text"]=ctext(c.get("content"))
    return events

for arm,idx in (("NATIVE",0),("PRISM",1)):
    bash_cat_calls=defaultdict(int); bash_cat_bytes=defaultdict(int)
    prism_before=prism_after=0; tools_before=tools_after=0; sessions_with_edit=0
    followup_reads=0; prism_calls=0; reads_total=0
    for i in range(len(results)):
        ev=analyze(files[2*i+idx][1])
        first_edit=next((k for k,e in enumerate(ev) if e["name"] in ("Edit","Write")),None)
        if first_edit is not None:
            sessions_with_edit+=1
            tools_before+=first_edit; tools_after+=len(ev)-first_edit
        for k,e in enumerate(ev):
            n=e["name"]
            if n=="Bash":
                cat=classify_bash(str(e["input"].get("command","")))
                bash_cat_calls[cat]+=1; bash_cat_bytes[cat]+=e["len"]
            if n=="Read": reads_total+=1
            if n.startswith("mcp__prism"):
                prism_calls+=1
                if first_edit is not None:
                    if k<first_edit: prism_before+=e["len"]
                    else: prism_after+=e["len"]
                paths=set(PATH_RE.findall(e["text"]))
                for nxt in ev[k+1:k+3]:
                    if nxt["name"]=="Read":
                        fp=str(nxt["input"].get("file_path",""))
                        if any(fp.endswith(p) for p in paths):
                            followup_reads+=1; break
    print(f"\n=== {arm} ===")
    print("Bash by category (calls / KB):")
    for cat in sorted(bash_cat_calls, key=lambda c:-bash_cat_calls[c]):
        print(f"  {cat:26s} calls={bash_cat_calls[cat]:4d}  {bash_cat_bytes[cat]/1024:7.0f} KB")
    if sessions_with_edit:
        print(f"tool calls before first Edit: {tools_before} ({tools_before/sessions_with_edit:.1f}/session); after: {tools_after} ({tools_after/sessions_with_edit:.1f}/session)")
    if idx==1:
        print(f"prism bytes delivered BEFORE first edit: {prism_before/1024:.0f} KB; AFTER: {prism_after/1024:.0f} KB")
        print(f"prism calls: {prism_calls}; followed within 2 tools by a native Read of a file the prism result mentioned: {followup_reads}  (native Reads total: {reads_total})")
