"""Gold-fix leak audit (2026-09-24). No LLM cost.

run_e2e used `git worktree add` from corpus clones made after each task's fix merged, so
`git log --all` exposed the gold commit. This finds cells whose agent ran `git show/diff/
checkout/cherry-pick/log -p` on a commit that is NOT an ancestor of base_commit and touches
the task's src_files, and reports resolve rates with those cells removed.
Result: 32/366 cells opened the fix, 27 resolved. guard-fix-run clean: prism 32/45 vs
native 27/46 (headline holds); search-body-ab clean: 27/44 vs 27/46 (the +2 was leak).
Fixed in run_e2e._worktree (per-cell local clone, refs stripped).
"""
import json,re,sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import verify_replay as v
from collections import Counter,defaultdict

def load(path):
    """turns: list of dict(ctx, uses=[(id,name,input)]), results id->(is_error,text)"""
    order,by,res=[],{},{}
    for line in path.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        m=j.get("message") or {}
        if j.get("type")=="assistant":
            mid=m.get("id")
            if mid not in by:
                u=m.get("usage") or {}
                by[mid]=dict(ctx=(u.get("input_tokens") or 0)+(u.get("cache_read_input_tokens") or 0)+(u.get("cache_creation_input_tokens") or 0),uses=[],text=0)
                order.append(mid)
            for c in m.get("content") or []:
                if not isinstance(c,dict): continue
                if c.get("type")=="tool_use": by[mid]["uses"].append((c["id"],c["name"],c.get("input") or {}))
                elif c.get("type")=="text": by[mid]["text"]+=len(c.get("text",""))
        elif j.get("type")=="user":
            for c in m.get("content") or [] if isinstance(m.get("content"),list) else []:
                if isinstance(c,dict) and c.get("type")=="tool_result":
                    cont=c.get("content"); s=cont if isinstance(cont,str) else " ".join(x.get("text","") for x in cont or [] if isinstance(x,dict))
                    res[c["tool_use_id"]]=(bool(c.get("is_error")),s)
    return [by[m] for m in order],res

def sessions():
    for d,arms in v.SETS:
        for t in json.loads((v.RES/d/"results.json").read_text()):
            for a in arms:
                c=t.get(a) or {}; sid=c.get("session_id")
                if not sid or c.get("error"): continue
                p=v.transcript(sid)
                if p: yield t,c,p
import subprocess, os
sys.path.insert(0, str(v.RES.parent / "runners"))
os.chdir(v.RES.parent)
import run_e2e
TASKS=v.RES.parent/"tasks"/"e2e"
def g(repo,*a):
    r=subprocess.run(["git","-C",str(repo),*a],capture_output=True,text=True); return r.returncode,r.stdout.strip()
def opened_gold(p,tj,repo):
    turns,res=load(p)
    for tu in turns:
        for uid,n,inp in tu["uses"]:
            cmd=str(inp.get("command","")) if n=="Bash" else ""
            if not re.search(r"git (show|diff|checkout|cherry-pick|log -p)",cmd): continue
            for sha in re.findall(r"\b[0-9a-f]{7,40}\b",cmd):
                rc,full=g(repo,"rev-parse","--verify","-q",sha+"^{commit}")
                if rc or g(repo,"merge-base","--is-ancestor",full,tj["base_commit"])[0]==0: continue
                files=set(g(repo,"show","--name-only","--format=",full)[1].split())
                if files & set(tj.get("src_files") or []): return True
    return False
SETS=[("search-body-ab",("native","prism")),("guard-hook-ab",("native","prism")),("residency-ab",("native","prism")),
      ("h3-ab/pass1",("native","prism")),("h3-ab/pass2",("native","prism")),("h3-ab/pass3",("native","prism"))]
for d,arms in SETS:
    r=json.loads((v.RES/d/"results.json").read_text())
    tally={a:Counter() for a in arms}
    for t in r:
        tj=json.loads((TASKS/f"{t['task']}.json").read_text()); repo=run_e2e._repo_for(tj)
        for a in arms:
            c=t.get(a) or {}; sid=c.get("session_id"); p=v.transcript(sid) if sid else None
            if not p: continue
            L=opened_gold(p,tj,repo)
            tally[a]["n"]+=1; tally[a]["res"]+=bool(c.get("resolved"))
            if L: tally[a]["leak"]+=1; tally[a]["leak_res"]+=bool(c.get("resolved")); tally[a].setdefault
            if L: print(f"   {d} {a} {t['task']} resolved={c.get('resolved')}")
    print(d, {a:f"resolved {x['res']}/{x['n']}, opened-fix {x['leak']} (resolved {x['leak_res']}), clean resolved {x['res']-x['leak_res']}/{x['n']-x['leak']}" for a,x in tally.items()})
