"""Score the complete fixed panel without dropping failures or pooling the old pilot."""
import json
from pathlib import Path
import statistics
import sys

TASKS = ['gin-4645', 'django-connparams', 'typeorm-driver-escape']


def saved_fraction(base, candidate):
    return 1-candidate/base if base and candidate is not None else None


def analyze(rows):
    expected = {(task, trial, model+'_'+arm) for task in TASKS for trial in [1,2]
                for model in ['sonnet','codex'] for arm in ['baseline','prism']}
    keys = [(r['task'],r['trial'],r['arm']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate cell identity')
    lookup = dict(zip(keys,rows))
    complete = set(keys)==expected and all(r['audited_valid'] for r in rows)
    result = dict(complete=complete,expected_cells=24,observed_cells=len(rows),
                  missing=[list(k) for k in sorted(expected-set(keys))],
                  invalid=[r['cell_id'] for r in rows if not r['audited_valid']],providers={})
    for model in ['sonnet','codex']:
        pairs = []
        for task in TASKS:
            for trial in [1,2]:
                b, p = lookup.get((task,trial,model+'_baseline')), lookup.get((task,trial,model+'_prism'))
                if b is None or p is None:
                    continue
                pairs.append(dict(task=task,trial=trial,valid=b['audited_valid'] and p['audited_valid'],
                                  baseline=b,candidate=p,
                                  token_saved_fraction=saved_fraction(b.get('audited_total_tokens'),p.get('audited_total_tokens')),
                                  cost_saved_fraction=saved_fraction(b.get('cost_usd'),p.get('cost_usd')),
                                  recall_delta=p['score']['recall']-b['score']['recall'],
                                  precision_delta=p['score']['precision']-b['score']['precision']))
        measured = len(pairs)==6 and all(p['valid'] for p in pairs)
        provider = dict(pairs=pairs,measured=measured)
        if measured:
            for arm,key in [('baseline','baseline'),('prism','candidate')]:
                cells = [p[key] for p in pairs]
                provider[arm] = dict(mean_recall=statistics.mean(r['score']['recall'] for r in cells),
                                     mean_precision=statistics.mean(r['score']['precision'] for r in cells),
                                     false_complete=sum(r['score']['overconfident'] for r in cells),
                                     tokens=sum(r['audited_total_tokens'] for r in cells),
                                     cost=sum(r['cost_usd'] for r in cells))
            provider['median_paired_token_saving'] = statistics.median(p['token_saved_fraction'] for p in pairs)
            provider['aggregate_token_saving'] = saved_fraction(provider['baseline']['tokens'],provider['prism']['tokens'])
            provider['aggregate_cost_saving'] = saved_fraction(provider['baseline']['cost'],provider['prism']['cost'])
            checks = dict(no_paired_recall_loss=all(p['recall_delta']>=0 for p in pairs),
                          no_added_false_complete=all(not p['candidate']['score']['overconfident'] or p['baseline']['score']['overconfident'] for p in pairs),
                          absolute_recall=provider['prism']['mean_recall']>=.95,
                          absolute_precision=provider['prism']['mean_precision']>=.95,
                          median_tokens_25_percent=provider['median_paired_token_saving']>=.25,
                          aggregate_cost_30_percent=provider['aggregate_cost_saving']>=.30)
            provider['checks'] = checks
            provider['pass'] = all(checks.values())
        result['providers'][model] = provider
    result['decision'] = 'inconclusive' if not complete else ('pass' if all(p.get('pass') for p in result['providers'].values()) else 'fail')
    return result


def main():
    root = Path(sys.argv[1])
    raw = json.loads((root/'summary.json').read_text())
    result = analyze(raw['rows'])
    result['estimated_spend_usd'] = raw.get('estimated_spend_usd')
    (root/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='providers'},indent=2))
    for model, p in result['providers'].items():
        print(model,json.dumps({k:v for k,v in p.items() if k!='pairs'},indent=2))


if __name__=='__main__':
    main()
