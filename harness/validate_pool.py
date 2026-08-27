#!/usr/bin/env python3
"""Gold-validate unused phase1 candidates: a task is usable only if its GOLD
patch scores RESOLVED in the official image (and the empty patch does not).
Same two-sided check gold-scoreable.json used for the current bed."""
import json, sys
sys.path.insert(0, '.')
import docker_eval
from pathlib import Path
docker_eval.CLONE_ROOT = Path.home() / ".cache" / "prism-research" / "swebench-repos"

cands = json.load(open('runs/swebench-live/phase1/candidates-with-images.json'))
valid = {t['instance_id'] for t in json.load(open('runs/swebench-live/phase1/valid-instances.json'))}
todo = [c for c in cands if c['instance_id'] not in valid]
OUT = Path('runs/swebench-live/pool-validation.json')
done = json.load(open(OUT)) if OUT.exists() else {}

for i, t in enumerate(todo, 1):
    tid = t['instance_id']
    if tid in done:
        continue
    gold = t.get('patch','')
    rec = {}
    try:
        g = docker_eval.score_official(t, gold)
        rec['gold'] = {k: g.get(k) for k in ('resolved','f2p_ok','p2p_ok','n_run')}
        if g.get('resolved'):
            e = docker_eval.score_official(t, "")
            rec['empty'] = {k: e.get(k) for k in ('resolved','n_run')}
            rec['scoreable'] = bool(g.get('resolved') and not e.get('resolved'))
        else:
            rec['scoreable'] = False
    except Exception as ex:
        rec = {'error': str(ex)[:120], 'scoreable': False}
    done[tid] = rec
    json.dump(done, open(OUT,'w'), indent=1)
    print(f"[{i}/{len(todo)}] {tid[:44]:44} scoreable={rec.get('scoreable')} {rec.get('error','')[:50]}", flush=True)

n_ok = sum(1 for v in done.values() if v.get('scoreable'))
print(f"\nPOOL VALIDATION: {n_ok} newly scoreable of {len(done)} checked")
