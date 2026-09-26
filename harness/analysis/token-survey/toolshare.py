import json, re, sys, datetime, time
from pathlib import Path
from collections import defaultdict

ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/archive-2026-09-tainted/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())

def content_len(c):
    if isinstance(c, str): return len(c)
    if isinstance(c, list):
        n=0
        for item in c:
            if isinstance(item, dict) and item.get("type")=="text": n += len(item.get("text",""))
            else: n += len(json.dumps(item))
        return n
    return len(json.dumps(c)) if c is not None else 0

def scan(f):
    tool_use = {}
    by_tool_bytes = defaultdict(int)
    by_tool_calls = defaultdict(int)
    out_tokens = 0
    empty_search = 0; search_n = 0
    for line in f.read_text(errors="ignore").splitlines():
        try: j = json.loads(line)
        except Exception: continue
        typ = j.get("type"); msg = j.get("message") or {}
        if typ == "assistant":
            out_tokens += (msg.get("usage") or {}).get("output_tokens",0) or 0
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type")=="tool_use":
                    tool_use[c["id"]] = (c.get("name",""), c.get("input") or {})
        elif typ == "user":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type")=="tool_result":
                    tid = c.get("tool_use_id")
                    if tid in tool_use:
                        name, tin = tool_use[tid]
                        if name.startswith("mcp__prism"):
                            op = tin.get("op","?") if isinstance(tin, dict) else "?"
                            key = f"prism:{op}"
                        else:
                            key = name
                        n = content_len(c.get("content"))
                        by_tool_bytes[key] += n; by_tool_calls[key] += 1
    return by_tool_bytes, by_tool_calls, out_tokens

files = []
for d in ROOT.iterdir():
    if not d.is_dir() or "e2e-run" not in d.name: continue
    for f in d.glob("*.jsonl"):
        mt = f.stat().st_mtime
        if start <= mt <= end: files.append((mt, f))
files.sort()
results = json.loads((RESDIR/"results.json").read_text())

for arm, idx in (("NATIVE", 0), ("PRISM", 1)):
    tot_b = defaultdict(int); tot_c = defaultdict(int)
    for i in range(len(results)):
        b, c, _ = scan(files[2*i+idx][1])
        for k,v in b.items(): tot_b[k]+=v
        for k,v in c.items(): tot_c[k]+=v
    grand = sum(tot_b.values())
    print(f"\n=== {arm} arm, 50 sessions: tool_result bytes by tool (total {grand/1024:,.0f} KB) ===")
    for k,v in sorted(tot_b.items(), key=lambda kv:-kv[1])[:12]:
        print(f"  {k:22s} {v/1024:9,.0f} KB  {100*v/grand:5.1f}%   calls={tot_c[k]:4d}  avg={v/tot_c[k]:8,.0f} B")
