import json,os,sys,statistics as st
sys.path.insert(0,'scoring'); import tool_usage
man=json.load(open('results/s55-bugfix30-manifest.json'))
py=set(json.load(open('results/s55-bugfix30-python.json')))
def L(d,t,a):
    p=f'{d}/{t}.claude-sonnet-5-5.{a}.json'
    return json.load(open(p)) if os.path.exists(p) else None
rows=[]
for t in man:
    f=L('results/e2e-forced30',t,'prism_body_exp'); n=L('results/e2e',t,'native')
    pd='results/e2e-venv' if t in py else 'results/e2e'; p=L(pd,t,'prism_init')
    rows.append((t,f,n,p))
done=[r for r in rows if r[1]]
out=[]
out.append(f"FORCED graph-op run (prism exp build capsteer5, 'Required steps: change_impact before editing, verify after'): {len(done)}/30 tasks done\n")
for name,idx in [('prism, forced change_impact+verify',1),('native (plain prompt)',2),('prism (released, no forcing)',3)]:
    rs=[r[idx] for r in done if r[idx]]
    if rs: out.append(f"  {name:36} resolved {sum(x['resolved'] for x in rs):2}/{len(rs)}  turns {st.mean(x['turns'] for x in rs):5.1f}  cost ${sum(x['cost_usd'] for x in rs):.2f}")
ci=vf=0
for r in done:
    u=r[1].get('tool_usage') or tool_usage.usage(r[1]['session_id'])
    ci+= 'change_impact' in u['prism_ops']; vf+= 'verify' in u['prism_ops']
out.append(f"\n  forced run actually called change_impact in {ci}/{len(done)}, verify in {vf}/{len(done)}")
out.append("\n  per task: forced | native | prism")
for t,f,n,p in done:
    g=lambda r: '-' if not r else (('PASS' if r['resolved'] else 'fail')+f" {r['turns']}t")
    out.append(f"   {t[:42]:42} {g(f):10} {g(n):10} {g(p)}")
out.append("\n  NOTE: forced run uses a minimal prompt + required steps; native/prism baselines used the default prompt (Python baselines with the ready env).")
open('results/forced30-SUMMARY.txt','w').write('\n'.join(out)+'\n'); print('\n'.join(out))
