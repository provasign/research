# Per change kind: pairs, solved, task cost @5m, tool calls, requests (native vs prism_cli).
import json,os,re,collections
H=os.path.expanduser("~/Projects/provasign/research/harness")
D=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(D+"/results.json"))
def kind(t):
    i=t["instance_id"]; ps=t.get("problem_statement","")
    if i.startswith("seed__"): return "signature change"
    if re.search(r"`\w+` (property|option)\b|\bproperty of\b|\boption of\b|internal `?\w+`? hook",ps[:200]): return "property/option rename"
    return "method rename (shared name)"
def tools(c):
    n=0
    for l in open(os.path.join(H,c["transcript"])):
        x=json.loads(l)
        if x.get("type")=="assistant": n+=sum(1 for u in x["message"]["content"] if u.get("type")=="tool_use")
    return n
S=collections.defaultdict(lambda:collections.Counter())
for k,r in d.items():
    if k.startswith("_"):continue
    a=r["cells"].get("prism_cli/nocache");b=r["cells"].get("prism_cli_b/nocache")
    if not(a and b) or a.get("resolved") is None or b.get("resolved") is None:continue
    t=json.load(open(f"{H}/tasks/e2e/{k}.json"))
    for g in (kind(t),"lang:"+t.get("lang",""),"ALL"):
        s=S[g];s["n"]+=1
        for arm,c in (("nat",a),("pri",b)):
            p=c["repriced"]["5m"];s[arm+"_task"]+=p["usd"]-p["startup_usd"];s[arm+"_start"]+=p["startup_usd"]
            s[arm+"_solved"]+=bool(c["resolved"]);s[arm+"_tools"]+=tools(c);s[arm+"_req"]+=c["api_calls"]-1
for g in sorted(S,key=lambda g:(g=="ALL",g)):
    s=S[g];n=s["n"]
    print(f"{g:28s} n={n:2d} solved {s['nat_solved']}/{s['pri_solved']}  task$/task {s['nat_task']/n:.4f}->{s['pri_task']/n:.4f} ({s['pri_task']/s['nat_task']:.2f}x)  tools {s['nat_tools']/n:.1f}->{s['pri_tools']/n:.1f} ({s['pri_tools']/s['nat_tools']:.2f}x)  req {s['nat_req']/n:.1f}->{s['pri_req']/n:.1f}")
