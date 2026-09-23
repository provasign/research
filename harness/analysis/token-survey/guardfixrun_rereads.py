import json, re, sys, datetime, time
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
PRISM_NAME_RE = re.compile(r"^mcp__prism__")

WINDOW_RE = re.compile(r"WINDOW\s+(\S+):(\d+)-(\d+)")
READ_HDR_RE = re.compile(r"^// (\S+) lines (\d+)-(\d+) of \d+", re.M)
LOOKUP_BLOCK_RE = re.compile(
    r"file:\s*(?P<file>\S+)\s*\nline:\s*(?P<line>\d+)\s*\nbody:\s*(?P<body>.*?)"
    r"(?=\nname:\s|\Z)", re.S)

def _int(v, d=0):
    try: return int(v)
    except (TypeError, ValueError): return d

def overlap_frac(a_from, a_to, b_from, b_to):
    lo, hi = max(a_from, b_from), min(a_to, b_to)
    if hi < lo or a_to < a_from: return 0.0
    return (hi - lo + 1) / (a_to - a_from + 1)

def op_of(tin, name):
    if isinstance(tin, dict) and "op" in tin: return tin["op"]
    return name.replace("mcp__prism__prism_","").replace("mcp__prism__","")

def response_text(c):
    if isinstance(c, str): return c
    if isinstance(c, list):
        return "\n".join(item.get("text","") for item in c if isinstance(item, dict) and "text" in item)
    return ""

def analyze(f):
    data = f.read_text(errors="ignore")
    tool_use = {}
    tool_result_text = {}
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
                        tool_result_text[tid] = response_text(c.get("content"))

    delivered = []
    n_reads = 0
    full_re = []   # (file, offset, best_frac, best_src)
    partial_re = []
    for tid,(name,tin) in tool_use.items():
        if name == "Read":
            ti = tin if isinstance(tin, dict) else {}
            f_path = ti.get("file_path","")
            offset = _int(ti.get("offset"),1)
            limit = _int(ti.get("limit"),0) or None
            req_to = (offset+limit-1) if limit else offset+1999
            n_reads += 1
            best, best_src = 0.0, None
            for df,dfrom,dto,src in delivered:
                if not f_path.endswith(df) and not df.endswith(f_path): continue
                frac = overlap_frac(offset, req_to, dfrom, dto)
                if frac > best: best, best_src = frac, src
            if best >= 0.7:
                full_re.append((f_path, offset, best, best_src))
            elif best >= 0.3:
                partial_re.append((f_path, offset, best, best_src))
            continue
        if not PRISM_NAME_RE.match(name): continue
        op = op_of(tin, name)
        text = tool_result_text.get(tid, "")
        if op == "read":
            args = tin.get("args", tin) if isinstance(tin, dict) else {}
            if isinstance(args, dict):
                fp, frm, to = args.get("file"), _int(args.get("from"),1), args.get("to")
                if fp and to: delivered.append((fp, frm, _int(to), "read"))
        elif op == "lookup" and text:
            for m in LOOKUP_BLOCK_RE.finditer(text):
                bl = m.group("body").count("\n")+1
                st = int(m.group("line"))
                delivered.append((m.group("file"), st, st+bl-1, "lookup"))
        elif op in ("search","query") and text:
            for m in WINDOW_RE.finditer(text):
                delivered.append((m.group(1), int(m.group(2)), int(m.group(3)), op))
            for m in READ_HDR_RE.finditer(text):
                delivered.append((m.group(1), int(m.group(2)), int(m.group(3)), op))
    return n_reads, full_re, partial_re

files = []
for d in ROOT.iterdir():
    if not d.is_dir() or "e2e-run" not in d.name: continue
    for f in d.glob("*.jsonl"):
        mt = f.stat().st_mtime
        if start <= mt <= end: files.append((mt, f))
files.sort()

results = json.loads((RESDIR/"results.json").read_text())
total_reads = 0
total_full = 0
total_partial = 0
per_task = []
for i, task in enumerate(results):
    _, pri_f = files[2*i+1]
    n_reads, full_re, partial_re = analyze(pri_f)
    total_reads += n_reads
    total_full += len(full_re)
    total_partial += len(partial_re)
    if full_re or partial_re:
        per_task.append((task["task"], n_reads, full_re, partial_re))

print(f"prism-arm native Read calls across all 50 tasks: {total_reads}")
print(f"  full re-reads (>=70% overlap with an earlier prism delivery): {total_full} ({100*total_full/total_reads:.1f}%)")
print(f"  partial re-reads (30-70% overlap): {total_partial} ({100*total_partial/total_reads:.1f}%)")
print(f"\ntasks with any re-read: {len(per_task)}/50")
for task, n_reads, full_re, partial_re in per_task:
    print(f"\n  {task}  (total Reads this session: {n_reads})")
    for fp, off, frac, src in full_re:
        print(f"    FULL    {fp} @offset {off}  overlap={frac:.0%}  (delivered earlier by {src})")
    for fp, off, frac, src in partial_re:
        print(f"    partial {fp} @offset {off}  overlap={frac:.0%}  (delivered earlier by {src})")
