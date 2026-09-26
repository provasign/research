import json, re, sys, datetime, time
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/archive-2026-09-tainted/guard-fix-run")
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

def prism_search_sizes(f):
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
                    if tid:
                        tool_result_len[tid] = content_len(c.get("content"))
    sizes = []
    for tid,(name,tin) in tool_use.items():
        if PRISM_NAME_RE.match(name) and op_of(tin,name)=="search":
            sizes.append(tool_result_len.get(tid,0))
    return sizes

files = []
for d in ROOT.iterdir():
    if not d.is_dir() or "e2e-run" not in d.name: continue
    for f in d.glob("*.jsonl"):
        mt = f.stat().st_mtime
        if start <= mt <= end:
            files.append((mt, f))
files.sort()

results = json.loads((RESDIR/"results.json").read_text())
rows = []
for i, task in enumerate(results):
    _, pri_f = files[2*i+1]
    sizes = prism_search_sizes(pri_f)
    exp_nat, exp_pri = task["native"]["tokens"] or 0, task["prism"]["tokens"] or 0
    ratio = (exp_pri/exp_nat) if exp_nat else None
    ratio_flag = ratio is not None and (ratio > 1.5 or ratio < 1/1.5)
    resolve_mismatch = task["native"]["resolved"] != task["prism"]["resolved"]
    rows.append({
        "task": task["task"], "ratio": ratio, "flagged": ratio_flag or resolve_mismatch,
        "resolve_mismatch": resolve_mismatch,
        "native_resolved": task["native"]["resolved"], "prism_resolved": task["prism"]["resolved"],
        "sizes": sizes, "max_search": max(sizes) if sizes else 0,
        "n_ge8k": sum(1 for s in sizes if s>=8000),
    })

print(f"{'task':38s} {'ratio':>6s} {'flag':>5s} {'max_search':>10s} {'n>=8K':>6s}")
for r in rows:
    print(f"{r['task']:38s} {r['ratio'] or 0:6.2f} {str(r['flagged']):>5s} {r['max_search']:10d} {r['n_ge8k']:6d}")

flagged_rows = [r for r in rows if r["flagged"]]
big_rows = [r for r in rows if r["n_ge8k"] > 0]
both = [r for r in rows if r["flagged"] and r["n_ge8k"] > 0]
print(f"\nflagged tasks (resolve-mismatch or |ratio| outside [0.67,1.5]): {len(flagged_rows)}/50")
print(f"tasks with >=1 search call >=8KB: {len(big_rows)}/50")
print(f"tasks that are BOTH flagged AND have a big search call: {len(both)}")
for r in both:
    print(f"  {r['task']}: ratio={r['ratio']:.2f} max_search={r['max_search']}B resolve n/p={r['native_resolved']}/{r['prism_resolved']}")

# among tasks NOT flagged, how many still had big search calls (i.e. big search did NOT hurt them)?
unflagged_but_big = [r for r in rows if not r["flagged"] and r["n_ge8k"] > 0]
print(f"\ntasks with a big (>=8KB) search call that were NOT flagged (i.e. no visible harm): {len(unflagged_but_big)}")
for r in unflagged_but_big:
    print(f"  {r['task']}: ratio={r['ratio']:.2f} max_search={r['max_search']}B resolved={r['prism_resolved']}")

print('\n--- naive cap-at-8KB byte savings estimate ---')
total_search_bytes = sum(sum(r['sizes']) for r in rows)
capped_bytes = sum(sum(min(s,8000) for s in r['sizes']) for r in rows)
saved = total_search_bytes - capped_bytes
print(f"total search response bytes across all 50 tasks' prism arm: {total_search_bytes:,}")
print(f"if every search call capped at 8000B: {capped_bytes:,}  (saved {saved:,}, {100*saved/total_search_bytes:.1f}% of search bytes)")
n_calls_over = sum(1 for r in rows for s in r['sizes'] if s > 8000)
print(f"calls that would actually be truncated: {n_calls_over} of {sum(len(r['sizes']) for r in rows)} total search calls")
