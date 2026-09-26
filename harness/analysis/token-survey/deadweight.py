import json, re, datetime, time
from pathlib import Path
from collections import defaultdict
ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/archive-2026-09-tainted/guard-fix-run")
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

def ctext(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(i.get("text","") for i in c if isinstance(i,dict) and "text" in i)
    return json.dumps(c) if c is not None else ""

MARK = re.compile(r"^(?:\*\*`(?P<a>[^`]+)`\*\*|// WINDOW (?P<b>\S+):\d+-\d+|// (?P<c>\S+) lines \d+-\d+ of \d+|file:\s*(?P<d>\S+)\s*$|(?P<e>\S+\.(?:java|py|go|js|ts|c|h|cpp|rs|php|kt|swift|m)):)")

def segments(text):
    """attribute bytes of a prism result to file paths by marker lines."""
    out = defaultdict(int); cur = None
    for line in text.split("\n"):
        m = MARK.match(line.strip())
        if m:
            cur = next(v for v in m.groupdict().values() if v)
        out[cur] += len(line)+1
    return out

tot = defaultdict(int)  # category -> bytes
per_op = defaultdict(lambda: defaultdict(int))
for i in range(len(results)):
    f = files[2*i+1][1]
    tool_use = {}; res = {}
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        typ=j.get("type"); msg=j.get("message") or {}
        if typ=="assistant":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_use":
                    tool_use[c["id"]]=(c.get("name",""), c.get("input") or {})
        elif typ=="user":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_result":
                    res[c.get("tool_use_id")] = ctext(c.get("content"))
    edited = {str(tin.get("file_path","")) for n,tin in tool_use.values() if n in ("Edit","Write")}
    for tid,(n,tin) in tool_use.items():
        if not n.startswith("mcp__prism"): continue
        op = tin.get("op","?") if isinstance(tin,dict) else "?"
        for path, b in segments(res.get(tid,"")).items():
            if path is None: cat="unattributed(headers/locators)"
            elif any(e.endswith(path) or path.endswith(e.split("/")[-1]) and e.endswith(path.split("/")[-1]) for e in edited): cat="bodies in files LATER EDITED"
            else: cat="bodies in files NEVER edited"
            tot[cat]+=b; per_op[op][cat]+=b
grand=sum(tot.values())
print(f"prism-arm result bytes, 50 sessions: {grand/1024:.0f} KB")
for k,v in sorted(tot.items(), key=lambda kv:-kv[1]): print(f"  {k:34s} {v/1024:6.0f} KB  {100*v/grand:5.1f}%")
print("\nby op:")
for op,d in sorted(per_op.items(), key=lambda kv:-sum(kv[1].values())):
    s=sum(d.values()); print(f"  {op:14s} {s/1024:6.0f} KB :: " + ", ".join(f"{k.split(' ')[0]}{'-edited' if 'LATER' in k else '-never' if 'NEVER' in k else ''}={100*v/s:.0f}%" for k,v in sorted(d.items())))
