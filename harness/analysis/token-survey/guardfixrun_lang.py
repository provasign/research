import json, re, sys, datetime, time
from pathlib import Path
from collections import defaultdict

ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
PRISM_NAME_RE = re.compile(r"^mcp__prism__")

def content_len(c):
    if isinstance(c, str): return len(c)
    if isinstance(c, list):
        n=0
        for item in c:
            if isinstance(item, dict) and item.get("type")=="text":
                n += len(item.get("text",""))
            else:
                n += len(json.dumps(item))
        return n
    return len(json.dumps(c)) if c is not None else 0

def op_of(tin, name):
    if isinstance(tin, dict) and "op" in tin: return tin["op"]
    return name.replace("mcp__prism__prism_","").replace("mcp__prism__","")

def per_op_sizes(f):
    data = f.read_text(errors="ignore")
    tool_use = {}
    tool_result_len = {}
    for line in data.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        typ = j.get("type")
        msg = j.get("message") or {}
        if typ == "assistant":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type")=="tool_use":
                    tool_use[c["id"]] = (c.get("name",""), c.get("input") or {})
        elif typ == "user":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type")=="tool_result":
                    tid = c.get("tool_use_id")
                    if tid: tool_result_len[tid] = content_len(c.get("content"))
    sizes = defaultdict(list)
    for tid,(name,tin) in tool_use.items():
        if not PRISM_NAME_RE.match(name): continue
        op = op_of(tin, name)
        sizes[op].append(tool_result_len.get(tid,0))
    return sizes

files = []
for d in ROOT.iterdir():
    if not d.is_dir() or "e2e-run" not in d.name: continue
    for f in d.glob("*.jsonl"):
        mt = f.stat().st_mtime
        if start <= mt <= end: files.append((mt, f))
files.sort()

results = json.loads((RESDIR/"results.json").read_text())
QUERY_BUDGET_BYTES = 32000  # ~8000 tokens * 4 chars/token
IMPACT_EVIDENCE_BYTES = 8192

by_lang = defaultdict(lambda: {"query_sizes": [], "impact_sizes": [], "search_sizes": [],
                                 "query_near_cap": 0, "query_total": 0,
                                 "impact_near_cap": 0, "impact_total": 0,
                                 "resolved": [], "n": 0})

for i, task in enumerate(results):
    _, pri_f = files[2*i+1]
    sizes = per_op_sizes(pri_f)
    lang = task["lang"]
    b = by_lang[lang]
    b["n"] += 1
    b["resolved"].append(task["prism"]["resolved"])
    for s in sizes.get("query", []):
        b["query_sizes"].append(s); b["query_total"] += 1
        if s >= QUERY_BUDGET_BYTES * 0.8: b["query_near_cap"] += 1
    for s in sizes.get("change_impact", []):
        b["impact_sizes"].append(s); b["impact_total"] += 1
        if s >= IMPACT_EVIDENCE_BYTES * 0.8: b["impact_near_cap"] += 1
    for s in sizes.get("search", []):
        b["search_sizes"].append(s)

print(f"{'lang':8s} {'n':>3s} {'resolved':>9s} {'query n/near-cap':>18s} {'impact n/near-cap':>19s} {'mean_query_B':>13s} {'mean_impact_B':>14s} {'mean_search_B':>14s}")
for lang, b in sorted(by_lang.items()):
    qmean = sum(b["query_sizes"])/len(b["query_sizes"]) if b["query_sizes"] else 0
    imean = sum(b["impact_sizes"])/len(b["impact_sizes"]) if b["impact_sizes"] else 0
    smean = sum(b["search_sizes"])/len(b["search_sizes"]) if b["search_sizes"] else 0
    res = sum(1 for r in b["resolved"] if r)
    print(f"{lang:8s} {b['n']:3d} {res:4d}/{b['n']:<4d} "
          f"{b['query_total']:4d}/{b['query_near_cap']:<10d} "
          f"{b['impact_total']:4d}/{b['impact_near_cap']:<12d} "
          f"{qmean:13.0f} {imean:14.0f} {smean:14.0f}")

print("\n--- the 2 query calls that hit near-cap (both Java) ---")
for i, task in enumerate(results):
    _, pri_f = files[2*i+1]
    sizes = per_op_sizes(pri_f)
    for s in sizes.get("query", []):
        if s >= QUERY_BUDGET_BYTES*0.8:
            print(f"  {task['task']}: query={s}B  resolved(n/p)={task['native']['resolved']}/{task['prism']['resolved']}  ratio={task['prism']['tokens']/task['native']['tokens']:.2f}")
