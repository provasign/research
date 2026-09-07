from __future__ import annotations
import importlib.util, json, statistics
from pathlib import Path

RO = Path('/private/tmp/prism-daytoday-readonly-20260907')
CO = Path('/private/tmp/prism-daytoday-code-20260907')
spec = importlib.util.spec_from_file_location('rr', '/private/tmp/prism-daytoday-readonly.py')
rr = importlib.util.module_from_spec(spec); spec.loader.exec_module(rr)

read_rows = json.loads((RO/'summary.json').read_text())['rows']
code_rows = json.loads((CO/'summary.json').read_text())['rows']

for row in code_rows:
    out = CO/'evidence'/row['cell_id']
    events = rr.read_events(out/'stdout.jsonl')
    if row['arm'].startswith('sonnet'):
        parsed, _, calls = rr.summarize_sonnet(events, out)
        prism = [c for c in calls if str(c.get('name','')).startswith('mcp__prism__')]
    else:
        parsed, _, calls = rr.summarize_codex(events, out)
        prism = [c for c in calls if c.get('type') == 'mcp_tool_call' and c.get('server') == 'prism']
    row['tool_calls_recounted'] = len(calls)
    row['prism_calls_recounted'] = len(prism)
    row['prism_result_bytes_recounted'] = parsed.get('prism_result_bytes', 0)

def median(vals):
    vals = [v for v in vals if isinstance(v, (int,float))]
    return round(statistics.median(vals), 3) if vals else None

def mean(vals):
    vals = [v for v in vals if isinstance(v, (int,float))]
    return round(sum(vals)/len(vals), 4) if vals else None

arms = ['sonnet_native','sonnet_prism','gpt55_native','gpt55_prism']
read = {}
for arm in arms:
    rows = [r for r in read_rows if r['arm']==arm]
    read[arm] = {
        'attempts': len(rows),
        'completed_valid': sum(bool(r.get('audited_valid')) for r in rows),
        'timeouts': sum(bool(r.get('timed_out')) for r in rows),
        'exact_answers': sum(r.get('score',{}).get('f1') == 1 for r in rows),
        'mean_recall_all_attempts': mean([r.get('score',{}).get('recall',0) for r in rows]),
        'mean_precision_all_attempts': mean([r.get('score',{}).get('precision',0) for r in rows]),
        'median_wall_s': median([r.get('wall_s') for r in rows]),
        'median_tokens_completed': median([r.get('total_tokens') for r in rows]),
        'total_tokens_completed': sum(r.get('total_tokens') or 0 for r in rows),
        'mean_tool_calls': mean([r.get('tool_calls') for r in rows]),
        'prism_adoption': sum(bool(r.get('prism_calls')) for r in rows),
        'prism_result_bytes': sum(r.get('prism_result_bytes') or 0 for r in rows),
    }

code = {}
for arm in arms:
    rows = [r for r in code_rows if r['arm']==arm]
    code[arm] = {
        'attempts': len(rows),
        'completed_valid': sum(bool(r.get('audited_valid')) for r in rows),
        'timeouts': sum(bool(r.get('timed_out')) for r in rows),
        'patches_produced': sum(bool(r.get('has_diff')) for r in rows),
        'test_resolved': sum(bool(r.get('resolved')) for r in rows),
        'completed_and_resolved': sum(bool(r.get('audited_valid') and r.get('resolved')) for r in rows),
        'median_wall_s': median([r.get('wall_s') for r in rows]),
        'median_tokens_completed': median([r.get('total_tokens') for r in rows]),
        'mean_tool_calls': mean([r.get('tool_calls_recounted') for r in rows]),
        'prism_adoption': sum(bool(r.get('prism_calls_recounted')) for r in rows),
    }

paired = {'read_only': {}, 'coding': {}}
for model in ('sonnet','gpt55'):
    n, p = read[f'{model}_native'], read[f'{model}_prism']
    paired['read_only'][model] = {
        'exact_delta_prism_minus_native': p['exact_answers']-n['exact_answers'],
        'median_wall_delta_s': round(p['median_wall_s']-n['median_wall_s'],3),
        'completed_token_delta': p['total_tokens_completed']-n['total_tokens_completed'],
    }
    n, p = code[f'{model}_native'], code[f'{model}_prism']
    paired['coding'][model] = {
        'test_resolved_delta': p['test_resolved']-n['test_resolved'],
        'completed_and_resolved_delta': p['completed_and_resolved']-n['completed_and_resolved'],
        'median_wall_delta_s': round(p['median_wall_s']-n['median_wall_s'],3),
    }

out = {
    'study': 'fast-day-to-day-screen-2026-09-07',
    'design': {'read_only_tasks': 6, 'coding_tasks': 2, 'arms': arms, 'trials': 1,
               'planned_cells': 32, 'hard_timeout_s': 120, 'retries': 0,
               'read_task_mix': {'test_coverage_call_chain': 5, 'bug_localization': 1},
               'coding_score': 'held-out fail-to-pass and pass-to-pass tests'},
    'read_only': read, 'coding': code, 'paired': paired,
    'limitations': [
        'Single trial: directional screen, not an inferential benchmark.',
        'Read-only mix is intentionally narrow: five test-coverage call-chain tasks and one localization task.',
        'Only two coding tasks; the harder Werkzeug task resolved in no arm.',
        'Prism was available but not forced; GPT-5.5 adopted it on 1/6 read-only tasks and 0/2 coding tasks, Sonnet on 5/6 and 0/2.',
        'Timed-out Sonnet+Prism Click produced a test-passing patch, but is not counted as a completed-and-resolved cell.',
    ],
}
Path('/private/tmp/daytoday-aggregate.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(out, indent=2))
