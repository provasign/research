import json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path.home() / ".claude" / "projects"
PRISM_NAME_RE = re.compile(r"^mcp__prism__")

def op_of(tin, name):
    if isinstance(tin, dict) and "op" in tin: return tin["op"]
    return name.replace("mcp__prism__prism_","").replace("mcp__prism__","")
def args_of(tin):
    if not isinstance(tin, dict): return {}
    a = tin.get("args", tin)
    return a if isinstance(a, dict) else {}
def _int(v,d=0):
    try: return int(v)
    except (TypeError,ValueError): return d

extend_events = 0
repeat_same_range = 0
total_read_calls = 0
sessions_scanned = 0

candidates = []
for d in ROOT.iterdir():
    if not d.is_dir(): continue
    for f in d.glob("*.jsonl"):
        candidates.append(f)

print(f"scanning {len(candidates)}...", file=sys.stderr)
done=0
for f in candidates:
    try:
        with open(f,"rb") as fh:
            data = fh.read()
        if b"mcp__prism" not in data: continue
    except Exception:
        continue
    try:
        text = data.decode(errors="ignore")
    except Exception:
        continue
    tool_use_ordered = []
    for line in text.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("type") != "assistant": continue
        msg = j.get("message") or {}
        for c in (msg.get("content") or []):
            if isinstance(c, dict) and c.get("type")=="tool_use":
                name = c.get("name","")
                if PRISM_NAME_RE.match(name):
                    tool_use_ordered.append((name, c.get("input") or {}))
    per_file_calls = defaultdict(list)  # file -> [(from,to)]
    for name, tin in tool_use_ordered:
        if op_of(tin, name) != "read": continue
        args = args_of(tin)
        fp = args.get("file")
        frm, to = _int(args.get("from"),1), args.get("to")
        if not fp or not to: continue
        total_read_calls += 1
        per_file_calls[fp].append((frm, _int(to)))
    any_extend = False
    for fp, calls in per_file_calls.items():
        if len(calls) < 2: continue
        for i in range(1, len(calls)):
            prev_from, prev_to = calls[i-1]
            cur_from, cur_to = calls[i]
            if cur_from == prev_from and cur_to == prev_to:
                repeat_same_range += 1
                any_extend = True
            elif cur_from <= prev_to and cur_to > prev_to:
                # overlaps and extends past the previous end
                extend_events += 1
                any_extend = True
    if any_extend:
        sessions_scanned += 1
    done += 1
    if done % 400 == 0:
        print(f"  ...{done}", file=sys.stderr)

print(f"\ntotal op=read calls (file+from+to specified) across corpus: {total_read_calls}")
print(f"exact-repeat same range (file,from,to identical to a prior call): {repeat_same_range}")
print(f"extend pattern (overlaps prior range and asks for MORE): {extend_events}")
print(f"sessions with at least one such event: {sessions_scanned}")
