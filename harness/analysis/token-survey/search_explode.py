import json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path.home() / ".claude" / "projects"
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

def is_bench(dirname):
    return ("e2e-run" in dirname or "ab-endtoend" in dirname or "-var-folders-" in dirname
            or "-private-tmp-" in dirname or "TestReadGuard" in dirname or "TestCmdInit" in dirname)

sizes = []  # (bytes, is_bench, session_dir)
candidates = []
for d in ROOT.iterdir():
    if not d.is_dir(): continue
    b = is_bench(d.name)
    for f in d.glob("*.jsonl"):
        candidates.append((f,b))

print(f"scanning {len(candidates)}...", file=sys.stderr)
done=0
for f,b in candidates:
    try:
        with open(f,"rb") as fh:
            data = fh.read()
        if b"mcp__prism" not in data:
            continue
    except Exception:
        continue
    try:
        lines = data.decode(errors="ignore").splitlines()
    except Exception:
        continue
    tool_use = {}
    tool_result_len = {}
    for line in lines:
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
    for tid,(name,tin) in tool_use.items():
        if not PRISM_NAME_RE.match(name): continue
        op = op_of(tin, name)
        if op != "search": continue
        plen = tool_result_len.get(tid, 0)
        sizes.append((plen, b, f.parent.name[:50]))
    done+=1
    if done % 300 == 0:
        print(f"  ...{done}", file=sys.stderr)

print(f"\ntotal search calls seen: {len(sizes)}")
thresholds = [8000, 10000, 15000, 20000, 30000, 40000]
for t in thresholds:
    n = sum(1 for s,_,_ in sizes if s >= t)
    print(f"  >= {t:6d} bytes: {n:5d} calls ({100*n/len(sizes):.2f}%)")

print("\nsearch calls >= 20000 bytes, by session:")
big = [(s,b,d) for s,b,d in sizes if s >= 20000]
big.sort(reverse=True)
for s,b,d in big:
    print(f"  {s:7d}B  {'bench' if b else 'LIVE ':5s}  {d}")
print(f"\ntotal >=20000B: {len(big)}  ({sum(1 for _,b,_ in big if not b)} live / {sum(1 for _,b,_ in big if b)} bench)")
