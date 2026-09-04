#!/usr/bin/env python3
"""Search-shape oracle: could the SEARCH payload have replaced the follow-up read?

Measured motivation (bed36-v5511 prism arms): 70% of prism_search calls are
followed by a read within two calls — the search->read ritual costs ~1.4
turns/cell, 3x the batching waste. This measures, offline and
deterministically, what result shape would let the agent skip that read:

For each gold-validated task (java12 bed, indexed worktrees):
  terms = realistic (title identifiers)
  shapes: default (locations), context=8, context=25
  metrics per shape: payload bytes; gold-region coverage (same probe as
  query_oracle — any stripped line within ±3 of a gold hunk anchor).

Coverage ~= "the read would have been unnecessary for the fix region".
"""
import json, re, subprocess, os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_oracle import gold_hunks, title_terms, show, run_capped

H = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser('~/.cache/prism-research/swebench-repos')
PRISM = sys.argv[1] if len(sys.argv) > 1 else '/tmp/prism-det'

def search(cwd, terms, ctx=None):
    cmd = [PRISM, 'search'] + terms + ['--format', 'text']
    if ctx: cmd += ['--context', str(ctx)]
    rc, out, err = run_capped(cmd, cwd=cwd, timeout=120)
    return out if rc == 0 else ''

def coverage(repo, sha, hunks, payload):
    cov = 0
    for f, ln in hunks:
        body = show(repo, sha, f).split('\n')
        probes = [l.strip() for l in body[max(0, ln-3):ln+4] if len(l.strip()) > 20]
        if any(p in payload for p in probes): cov += 1
    return cov / max(len(hunks), 1)

def main():
    tasks = json.load(open(os.path.join(H, 'runs/swebench-live/slice-java12.json')))
    agg = {s: {'cov': [], 'bytes': []} for s in ('default', 'ctx8', 'ctx25')}
    for t in tasks:
        hunks = gold_hunks(t)
        if not hunks: continue
        terms = title_terms(t)
        if not terms: continue
        repo = os.path.join(CACHE, t['repo'].replace('/', '__'))
        wt = tempfile.mkdtemp(prefix='sshape-')
        try:
            subprocess.run(['git','-C',repo,'worktree','add','--detach','--force',wt,t['base_commit']],
                           capture_output=True, check=True, timeout=120)
            run_capped([PRISM,'index','.'], cwd=wt, timeout=600)
            row = []
            for shape, ctx in (('default',None),('ctx8',8),('ctx25',25)):
                out = search(wt, terms, ctx)
                c = coverage(repo, t['base_commit'], hunks, out)
                agg[shape]['cov'].append(c); agg[shape]['bytes'].append(len(out))
                row.append(f"{shape}: cov={c:.2f} {len(out):,}B")
            # AUTO shape: default locations, plus each hit symbol's BODY —
            # but only when a term resolves to few hits (<=3). Simulated as
            # search + prism_lookup per small-hit-set symbol name.
            base = search(wt, terms, None)
            payload = base
            hits = re.findall(r'^// (\S+) — (\S+)$', base, re.M)
            names = []
            seen = set()
            for _f, nm in hits:
                if nm not in seen:
                    seen.add(nm); names.append(nm)
            if len(names) <= 3:
                for nm in names:
                    rc2, lout, _ = run_capped([PRISM, 'lookup', nm, '--format', 'text'], cwd=wt, timeout=120)
                    if rc2 == 0: payload += lout
            c = coverage(repo, t['base_commit'], hunks, payload)
            agg.setdefault('auto', {'cov': [], 'bytes': []})
            agg['auto']['cov'].append(c); agg['auto']['bytes'].append(len(payload))
            row.append(f"auto: cov={c:.2f} {len(payload):,}B")
            print(f"{t['instance_id'][:36]:36} " + '  '.join(row), flush=True)
        finally:
            subprocess.run(['git','-C',repo,'worktree','remove','--force',wt],capture_output=True,timeout=120)
            shutil.rmtree(wt, ignore_errors=True)
    import statistics
    print("\nAGGREGATE (12 tasks, realistic terms):")
    for s in agg:
        if agg[s]['cov']:
            print(f"  {s:8} mean coverage {statistics.mean(agg[s]['cov']):.2f}   mean bytes {statistics.mean(agg[s]['bytes']):,.0f}")

if __name__ == '__main__':
    main()
