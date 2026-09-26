"""Offline test: can a simple rule predict which prism `search` bodies end up in a
file the agent later edits? guard-fix-run prism arm, 50 sessions. Base rate for
search bodies being in a never-edited file was 53%; break-even for demoting a body
to a locator is ~60% precision, clearly-worth-it ~75%."""
import json, re, datetime, time
from pathlib import Path
from collections import defaultdict
ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/archive-2026-09-tainted/guard-fix-run")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
files = sorted((f.stat().st_mtime, f) for d in ROOT.iterdir() if d.is_dir() and "e2e-run" in d.name
               for f in d.glob("*.jsonl") if start <= f.stat().st_mtime <= end)
results = json.loads((RESDIR/"results.json").read_text())

def ctext(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "\n".join(i.get("text","") for i in c if isinstance(i,dict) and "text" in i)
    return ""
MARK = re.compile(r"^(?:\*\*`(?P<a>[^`]+)`\*\*|// WINDOW (?P<b>\S+):\d+-\d+|// (?P<c>\S+) lines \d+-\d+ of \d+|file:\s*(?P<d>\S+)\s*$)")
TEST_RE = re.compile(r"(^|/)(tests?|testing|spec)(/|$)|_test\.|test_|Test\w*\.java|\.spec\.|\.test\.")

def bodies(text):
    segs=[]; cur=None; buf=[]; hdr=""
    for line in text.split("\n"):
        m=MARK.match(line.strip())
        if m:
            if cur is not None: segs.append((cur,hdr,"\n".join(buf)))
            cur=next(v for v in m.groupdict().values() if v); hdr=line; buf=[]
        elif cur is not None: buf.append(line)
    if cur is not None: segs.append((cur,hdr,"\n".join(buf)))
    return [(p,h,b) for p,h,b in segs if len(b)>200]  # bodies, not bare locators

rows=[]
for i in range(len(results)):
    f=files[2*i+1][1]; tool_use={}; res={}
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        typ=j.get("type"); msg=j.get("message") or {}
        if typ=="assistant":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_use": tool_use[c["id"]]=(c.get("name",""),c.get("input") or {})
        elif typ=="user":
            for c in (msg.get("content") or []):
                if isinstance(c,dict) and c.get("type")=="tool_result": res[c.get("tool_use_id")]=ctext(c.get("content"))
    edited={str(t.get("file_path","")) for n,t in tool_use.values() if n in ("Edit","Write")}
    for tid,(n,tin) in tool_use.items():
        if not n.startswith("mcp__prism") or not isinstance(tin,dict) or tin.get("op")!="search": continue
        args=tin.get("args") or {}
        if not isinstance(args, dict): args={}
        terms=args.get("terms") or []
        if isinstance(terms,str): terms=[terms]
        bs=bodies(res.get(tid,""))
        for rank,(path,hdr,body) in enumerate(bs,1):
            rows.append({
                "edited": any(e.endswith(path) or e.endswith(path.split("/")[-1]) for e in edited),
                "rank": rank, "nbodies": len(bs),
                "test": bool(TEST_RE.search(path)),
                "term_in_body": any(t and t in body for t in terms),
                "term_in_path": any(t and t.split(".")[-1] in path.split("/")[-1] for t in terms),
                "enclosing": "Full enclosing body" in hdr or "enclosing" in hdr,
                "bytes": len(body),
            })

n=len(rows); base=sum(r["edited"] for r in rows)/n
print(f"search bodies delivered: {n}; later-edited base rate: {base:.0%}  (never-edited {1-base:.0%})")
def ev(name, keep):
    k=[r for r in rows if keep(r)]; d=[r for r in rows if not keep(r)]
    if not k or not d: print(f"  {name:45s} (degenerate)"); return
    prec_keep=sum(r["edited"] for r in k)/len(k)           # of bodies we KEEP, how many were needed
    prec_demote=sum(not r["edited"] for r in d)/len(d)      # of bodies we DEMOTE, how many were truly unneeded
    saved=sum(r["bytes"] for r in d)
    print(f"  {name:45s} keep={len(k):3d} (edited {prec_keep:4.0%})  demote={len(d):3d} (correct {prec_demote:4.0%})  bytes demoted={saved/1024:5.0f}KB")
print("rule → keep body if ...; otherwise demote to locator")
ev("rank==1", lambda r:r["rank"]==1)
ev("single-body result", lambda r:r["nbodies"]==1)
ev("non-test file", lambda r:not r["test"])
ev("term in body", lambda r:r["term_in_body"])
ev("term in filename", lambda r:r["term_in_path"])
ev("rank==1 AND non-test", lambda r:r["rank"]==1 and not r["test"])
ev("rank==1 AND term in body", lambda r:r["rank"]==1 and r["term_in_body"])
ev("non-test AND term in body", lambda r:not r["test"] and r["term_in_body"])
ev("rank==1 AND non-test AND term in body", lambda r:r["rank"]==1 and not r["test"] and r["term_in_body"])
ev("term in filename AND non-test", lambda r:r["term_in_path"] and not r["test"])
print("\nfeature marginals (share edited):")
for feat in ("rank","nbodies","test","term_in_body","term_in_path","enclosing"):
    g=defaultdict(list)
    for r in rows: g[r[feat] if feat!="nbodies" else min(r[feat],3)].append(r["edited"])
    print(f"  {feat:13s} " + "  ".join(f"{k}:{sum(v)/len(v):.0%}(n={len(v)})" for k,v in sorted(g.items())))
