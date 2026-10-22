import json,os
d=json.load(open(os.path.expanduser("~/Projects/provasign/research/harness/results/v0837-vs-native41-2026-10-20/results.json")))
n=p=0;rn=rp=0;tn=tp=0;cn=cp=0;pairs=0
for k,r in d.items():
    if k.startswith("_"):continue
    a=r["cells"].get("native/nocache");b=r["cells"].get("prism_cli/nocache")
    if not a or not b: continue
    pairs+=1
    rn+=bool(a["resolved"]);rp+=bool(b["resolved"])
    A=a["repriced"]["5m"];B=b["repriced"]["5m"]
    tn+=A["usd"]-A["startup_usd"];tp+=B["usd"]-B["startup_usd"];n+=A["usd"];p+=B["usd"]
    cn+=a["api_calls"];cp+=b["api_calls"]
print(f"pairs {pairs}: solved native {rn} cli {rp}; 5m task ${tn:.3f} vs ${tp:.3f} = {tp/tn:.3f}x; total {p/n:.3f}x; requests {cn} vs {cp}")
