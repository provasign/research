from __future__ import annotations
import json
from pathlib import Path

BASE = Path('/Users/tapabratapal/Projects/provasign/research/harness/runs/daytoday-four-head-2026-09-07')
FR = Path('/private/tmp/prism-daytoday-forced-readonly-20260907')
FC = Path('/private/tmp/prism-daytoday-forced-code-20260907')

base_read = json.loads((BASE/'read-only/summary.json').read_text())['rows']
base_code = json.loads((BASE/'code/summary.json').read_text())['rows']
forced_read = json.loads((FR/'summary.json').read_text())['rows']
forced_code = json.loads((FC/'summary.json').read_text())['rows']

def pick(rows, task, arm):
    return next(r for r in rows if r['task'] == task and r['arm'] == arm)

def read_view(r):
    return {'exact': r.get('score',{}).get('f1') == 1, 'recall': r.get('score',{}).get('recall'),
            'precision': r.get('score',{}).get('precision'), 'wall_s': r.get('wall_s'),
            'tokens': r.get('total_tokens'), 'timed_out': r.get('timed_out'),
            'prism_calls': len(r.get('prism_calls') or []), 'audited_valid': r.get('audited_valid'),
            'violations': r.get('violations') or []}

def code_view(r):
    return {'resolved': r.get('resolved'), 'patch_produced': r.get('has_diff'),
            'wall_s': r.get('wall_s'), 'tokens': r.get('total_tokens'),
            'timed_out': r.get('timed_out'), 'prism_calls': len(r.get('prism_calls') or []),
            'audited_valid': r.get('audited_valid'), 'violations': r.get('violations') or []}

comparisons = {'read_only': {}, 'coding': {}}
for task in ('flaskcov-frompyfile','flaskcov-tag'):
    comparisons['read_only'][task] = {}
    for model in ('sonnet','gpt55'):
        comparisons['read_only'][task][model] = {
            'native_baseline': read_view(pick(base_read,task,f'{model}_native')),
            'natural_prism': read_view(pick(base_read,task,f'{model}_prism')),
            'forced_first_call': read_view(pick(forced_read,task,f'{model}_prism')),
        }
for task in ('pallets__click__pr3244','pallets__werkzeug__pr3081'):
    comparisons['coding'][task] = {}
    for model in ('sonnet','gpt55'):
        comparisons['coding'][task][model] = {
            'native_baseline': code_view(pick(base_code,task,f'{model}_native')),
            'natural_prism': code_view(pick(base_code,task,f'{model}_prism')),
            'forced_first_call': code_view(pick(forced_code,task,f'{model}_prism')),
        }

out = {
  'study': 'forced-first-call-prism-isolation-2026-09-07',
  'release_under_test': 'Prism v0.72.0, unmodified',
  'design': {'new_cells': 8, 'models': ['claude-sonnet-5','gpt-5.5'],
             'search_tasks': 2, 'coding_tasks': 2, 'search_timeout_s': 90,
             'coding_timeout_s': 180, 'retries': 0,
             'treatment': 'Exactly one appropriate Prism call before any native tool; prompt-only, no product changes',
             'comparison': 'Reused matching native and natural-Prism cells from c40cec8'},
  'treatment_compliance': {
      'exactly_one_prism_call': sum(len(r.get('prism_calls') or []) == 1 for r in forced_read + forced_code),
      'attempts': 8,
      'noncompliant': [r['cell_id'] for r in forced_read + forced_code if len(r.get('prism_calls') or []) != 1],
      'timeouts': [r['cell_id'] for r in forced_read + forced_code if r.get('timed_out')],
  },
  'comparisons': comparisons,
  'decision': {
      'change_v0_72_release_steering': False,
      'reason': 'Mixed task-specific effects, no search accuracy gain, Sonnet search noncompliance, and no improvement on Werkzeug do not support a blanket steering change.',
      'positive_signal': 'On Click, forced-first-query produced completed held-out-passing patches in 75.9s (GPT-5.5) and 88.1s (Sonnet), versus 112.2s completed / 120.4s timed out in natural-Prism cells.',
      'next_safe_step': 'Preserve v0.72.0 and build the balanced permanent suite; treat natural Prism adoption as an outcome. Investigate a narrowly scoped coding-routing experiment separately before any release change.'
  }
}
Path('/private/tmp/forced-isolation-aggregate.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out['treatment_compliance'],indent=2))
print(json.dumps(out['decision'],indent=2))
