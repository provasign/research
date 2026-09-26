"""Does search-body-ab match the turn-economics theory? Compare baseline vs exp
per task on: API turns, tool calls, native Reads, locator->body follow-ups,
prism search full-body vs window deliveries, prism bytes, cache_read/turn."""
import json, re, sys
from pathlib import Path
from collections import defaultdict
ROOT = Path.home() / ".claude" / "projects"
RES = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/archive-2026-09-tainted/search-body-ab/results.json")
PATH_RE = re.compile(r"[\w./-]+\.(?:java|py|go|js|ts|c|h|cpp|rb|rs|php|kt|swift|m)\b")

def find(sid):
    hits = list(ROOT.glob(f"*/{sid}.jsonl"))
    return hits[0] if hits else None

def ctext(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(i.get("text","") for i in c if isinstance(i,dict) and "text" in i)
    return json.dumps(c) if c is not None else ""

def analyze(f):
    ev=[]; tu={}; turns=0; cr=0; cw=0; out=0
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        typ=j.get("type"); msg=j.get("message") or {}
        if typ=="assistant":
            u=msg.get("usage") or {}
            if u:
                turns+=1; cr+=u.get("cache_read_input_tokens",0) or 0
                cw+=u.get("cache_creation_input_tokens",0) or 0; out+=u.get("output_tokens",0) or 0
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_use":
                    tu[c["id"]]=len(ev); ev.append({"name":c.get("name",""),"input":c.get("input") or {},"text":""})
        elif typ=="user":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_result" and c.get("tool_use_id") in tu:
                    ev[tu[c["tool_use_id"]]]["text"]=ctext(c.get("content"))
    m=defaultdict(int)
    m["turns"]=turns; m["cache_read"]=cr; m["cache_write"]=cw; m["output"]=out; m["tools"]=len(ev)
    for k,e in enumerate(ev):
        n=e["name"]
        if n=="Read": m["reads"]+=1
        elif n=="Bash": m["bash"]+=1
        elif n in ("Edit","Write"): m["edits"]+=1
        if n.startswith("mcp__prism"):
            op=e["input"].get("op","?") if isinstance(e["input"],dict) else "?"
            m["prism"]+=1; m[f"prism_{op}"]+=1; m["prism_bytes"]+=len(e["text"]); m[f"prism_{op}_bytes"]+=len(e["text"])
            if op=="search":
                m["search_full"]+=e["text"].count("// Full enclosing body")
                m["search_window"]+=e["text"].count("// WINDOW ")
            paths=set(PATH_RE.findall(e["text"]))
            for nxt in ev[k+1:k+3]:
                if nxt["name"]=="Read" and any(str(nxt["input"].get("file_path","")).endswith(p) for p in paths):
                    m["followup_reads"]+=1; break
    return m

results=json.loads(RES.read_text())
agg={"base":defaultdict(int),"exp":defaultdict(int)}
paired=[]; missing=0
for r in results:
    fb=find(r["native"]["session_id"]); fe=find(r["prism"]["session_id"])
    if not fb or not fe: missing+=1; continue
    mb=analyze(fb); me=analyze(fe)
    for k,v in mb.items(): agg["base"][k]+=v
    for k,v in me.items(): agg["exp"][k]+=v
    paired.append((r["task"], mb, me, r["native"]["tokens"], r["prism"]["tokens"], r["native"]["resolved"], r["prism"]["resolved"]))

n=len(paired)
print(f"paired sessions: {n} (missing transcripts: {missing})")
b,e=agg["base"],agg["exp"]
def row(label,kb,fmt="{:,.0f}"):
    vb,ve=b[kb],e[kb]; d=ve-vb
    print(f"  {label:34s} base={fmt.format(vb):>12s}  exp={fmt.format(ve):>12s}  delta={d:+,.0f} ({100*d/vb:+.1f}%)" if vb else f"  {label:34s} base={vb} exp={ve}")
print("\n=== totals over 50 sessions ===")
row("API turns","turns"); row("tool calls","tools"); row("native Reads","reads"); row("Bash","bash"); row("Edits","edits")
row("prism calls","prism"); row("  search","prism_search"); row("  lookup","prism_lookup"); row("  read","prism_read"); row("  change_impact","prism_change_impact")
row("search: full bodies delivered","search_full"); row("search: windows delivered","search_window")
row("locator->body follow-up Reads","followup_reads")
row("prism bytes (all ops)","prism_bytes"); row("  search bytes","prism_search_bytes")
row("cache_read tokens (transcript sum)","cache_read"); row("cache_write tokens","cache_write"); row("output tokens","output")
print(f"  avg context re-billed/turn         base={b['cache_read']/b['turns']:,.0f}  exp={e['cache_read']/e['turns']:,.0f}")

# per-task: did turn delta explain token delta?
import statistics
dt=[me["turns"]-mb["turns"] for _,mb,me,_,_,_,_ in paired]
dtok=[pt-nt for _,_,_,nt,pt,_,_ in paired]
fewer=sum(1 for d in dt if d<0); more=sum(1 for d in dt if d>0); same=n-fewer-more
print(f"\n=== per-task ===")
print(f"exp had FEWER turns in {fewer}/{n}, MORE in {more}, same in {same}; median turn delta {statistics.median(dt):+.0f}")
cheaper=sum(1 for d in dtok if d<0)
print(f"exp cheaper in {cheaper}/{n} tasks; median token delta {statistics.median(dtok):+,.0f}")
mx,my=statistics.mean(dt),statistics.mean(dtok)
cov=sum((x-mx)*(y-my) for x,y in zip(dt,dtok))/n
sx,sy=statistics.pstdev(dt),statistics.pstdev(dtok)
print(f"corr(turn delta, token delta) = {cov/(sx*sy):.2f}" if sx and sy else "corr n/a")
# sessions where exp delivered more full bodies: did follow-up reads drop there?
sub=[(mb,me) for _,mb,me,_,_,_,_ in paired if me["search_full"]>mb["search_full"]]
if sub:
    fb_=sum(mb["followup_reads"] for mb,_ in sub); fe_=sum(me["followup_reads"] for _,me in sub)
    tb_=sum(mb["turns"] for mb,_ in sub); te_=sum(me["turns"] for _,me in sub)
    print(f"\n{len(sub)} tasks where exp delivered MORE full bodies than base: follow-up Reads {fb_}->{fe_}, turns {tb_}->{te_}")
sub2=[(mb,me) for _,mb,me,_,_,_,_ in paired if me["search_full"]==mb["search_full"]]
if sub2:
    tb_=sum(mb["turns"] for mb,_ in sub2); te_=sum(me["turns"] for _,me in sub2)
    print(f"{len(sub2)} tasks where full-body count was UNCHANGED (change didn't fire): turns {tb_}->{te_}  (pure noise floor)")
print("\nbiggest per-task token deltas (exp - base), with turn delta and full-body delta:")
for task,mb,me,nt,pt,rb,re_ in sorted(paired, key=lambda x: x[4]-x[3])[:5]+sorted(paired, key=lambda x: x[4]-x[3])[-5:]:
    print(f"  {task:36s} tok {pt-nt:+12,.0f}  turns {me['turns']-mb['turns']:+3d}  full {me['search_full']-mb['search_full']:+2d}  reads {me['reads']-mb['reads']:+2d}  resolved {rb}->{re_}")
