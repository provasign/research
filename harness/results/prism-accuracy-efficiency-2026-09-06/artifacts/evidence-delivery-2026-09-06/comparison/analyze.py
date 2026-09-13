"""Frozen acceptance and descriptive tool-use counts for four Codex pairs."""
import json
import math
from pathlib import Path
import statistics
import sys

TASKS = ['gin-4645', 'django-connparams']


def known(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def diagnostics(calls):
    result = dict(successful_impact_calls=0, searches_after_impact=0,
                  lookups_after_impact=0, native_commands_after_impact=0,
                  successful_batch_calls=0, batch_names_requested=0)
    seen_impact = False
    for call in calls:
        tool = call.get('tool')
        success = (call.get('status') == 'completed' and not call.get('error')
                   and not (call.get('result') or {}).get('isError'))
        if seen_impact:
            result['searches_after_impact'] += int(tool == 'prism_search')
            result['lookups_after_impact'] += int(tool == 'prism_lookup')
            result['native_commands_after_impact'] += int(call.get('type') == 'command_execution')
        if tool == 'prism_change_impact' and success:
            seen_impact = True
            result['successful_impact_calls'] += 1
        args = call.get('arguments') or {}
        if isinstance(args, str):
            args = json.loads(args)
        if tool == 'prism_lookup' and isinstance(args.get('name'), list) and success:
            result['successful_batch_calls'] += 1
            result['batch_names_requested'] += len(args['name'])
    return result


def analyze(rows):
    expected = {(task, repeat, variant) for task in TASKS for repeat in [1, 2]
                for variant in ['before', 'after']}
    keys = [(r['task'], r['trial'], r['variant']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate comparison identity')
    lookup = dict(zip(keys, rows))
    eligible = lambda r: bool(r['audited_valid'] and known(r.get('audited_total_tokens'))
                             and known(r.get('cost_usd')))
    complete = set(keys) == expected and all(eligible(r) for r in rows)
    result = dict(complete=complete, observed_cells=len(rows), expected_cells=8,
                  missing=[list(k) for k in sorted(expected-set(keys))],
                  invalid=[r['comparison_id'] for r in rows if not eligible(r)], pairs=[])
    costs = [r.get('cost_usd') for r in rows]
    result['estimated_spend_usd'] = sum(costs) if all(known(c) for c in costs) else None
    for task in TASKS:
        for repeat in [1, 2]:
            before, after = [lookup.get((task, repeat, v)) for v in ['before', 'after']]
            if before is None or after is None:
                continue
            valid = eligible(before) and eligible(after)
            saving = (1-after['audited_total_tokens']/before['audited_total_tokens']
                      if valid and before['audited_total_tokens'] > 0 else None)
            result['pairs'].append(dict(task=task, trial=repeat, valid=valid,
                                        before=before, after=after, token_saving=saving))
    result['decision'] = 'inconclusive'
    if complete:
        for variant in ['before', 'after']:
            cells = [r for r in rows if r['variant'] == variant]
            result[variant] = dict(tokens=sum(r['audited_total_tokens'] for r in cells),
                cost=sum(r['cost_usd'] for r in cells),
                mean_recall=statistics.mean(r['score']['recall'] for r in cells),
                mean_precision=statistics.mean(r['score']['precision'] for r in cells),
                false_complete=sum(r['score']['overconfident'] for r in cells))
        if not result['before']['cost'] or any(p['token_saving'] is None for p in result['pairs']):
            return result
        result['median_paired_token_saving'] = statistics.median(p['token_saving'] for p in result['pairs'])
        result['aggregate_token_saving'] = 1-result['after']['tokens']/result['before']['tokens']
        result['aggregate_cost_saving'] = 1-result['after']['cost']/result['before']['cost']
        checks = dict(no_paired_recall_loss=all(p['after']['score']['recall'] >= p['before']['score']['recall'] for p in result['pairs']),
            no_added_false_complete=all(not p['after']['score']['overconfident'] or p['before']['score']['overconfident'] for p in result['pairs']),
            absolute_recall=result['after']['mean_recall'] >= .95,
            absolute_precision=result['after']['mean_precision'] >= .95,
            median_tokens_25_percent=result['median_paired_token_saving'] >= .25,
            aggregate_cost_30_percent=result['aggregate_cost_saving'] >= .30)
        result['checks'] = checks
        result['decision'] = 'pass' if all(checks.values()) else 'fail'
    return result


def main():
    root = Path(sys.argv[1])
    result = analyze(json.loads((root/'summary.json').read_text())['rows'])
    (root/'analysis.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'pairs'}, indent=2))


if __name__ == '__main__':
    main()
