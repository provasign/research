import json, datetime, time
from pathlib import Path
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

def scan(f):
    turns=0; cr=0; cw=0; inp=0; out=0
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        if j.get("type")!="assistant": continue
        u=(j.get("message") or {}).get("usage") or {}
        if not u: continue
        turns+=1
        cr+=u.get("cache_read_input_tokens",0) or 0
        cw+=u.get("cache_creation_input_tokens",0) or 0
        inp+=u.get("input_tokens",0) or 0
        out+=u.get("output_tokens",0) or 0
    return turns,cr,cw,inp,out

for arm,idx in (("NATIVE",0),("PRISM",1)):
    T=CR=CW=IN=OUT=0
    rec=0
    for i,r in enumerate(results):
        t,cr,cw,inp,out=scan(files[2*i+idx][1])
        T+=t;CR+=cr;CW+=cw;IN+=inp;OUT+=out
        rec+= (r["native"] if idx==0 else r["prism"])["tokens"] or 0
    tot=CR+CW+IN+OUT
    print(f"{arm}: recorded total tokens (harness) = {rec:,}")
    print(f"  API turns (assistant msgs w/ usage) = {T:,}  avg/session = {T/50:.1f}")
    print(f"  transcript sum: cache_read={CR:,} ({100*CR/tot:.1f}%)  cache_write={CW:,} ({100*CW/tot:.1f}%)  fresh_input={IN:,}  output={OUT:,} ({100*OUT/tot:.1f}%)")
    print(f"  avg context re-billed per turn (cache_read/turns) = {CR/T:,.0f} tokens")
