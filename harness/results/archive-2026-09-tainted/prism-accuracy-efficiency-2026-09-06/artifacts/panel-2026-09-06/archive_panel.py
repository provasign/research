"""Archive a finished panel and independently replay its saved answers and usage."""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys

from analyze_panel import analyze

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[3] / 'research/harness'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    root = Path(sys.argv[1]).resolve()
    if root == HERE:
        raise ValueError('Use the original run directory, not the archive destination')
    manifest = json.loads((root / 'manifest.json').read_text())
    summary = json.loads((root / 'summary.json').read_text())
    analysis = analyze(summary['rows'])
    assert analysis['observed_cells'] == 24 and not analysis['missing'], 'Archive after all scheduled executions finish'
    assert sha(HERE / 'run_panel.py') == manifest['runner_sha256']
    assert sha(HERE.parent / 'four-way-2026-09-06/prism-four-way.py') == manifest['helper_sha256']
    assert sha(root / 'prism-candidate') == manifest['binary_sha256']
    for name, digest in manifest['harness_sha256'].items():
        assert sha(HARNESS / name) == digest, name
    sys.path.insert(0, str(HARNESS))
    schema = importlib.import_module('schema')
    scorer = importlib.import_module('score')
    tasks = {}
    for entry in manifest['tasks']:
        path = root / (entry['task'] + '.task.json')
        original = HARNESS / 'tasks' / (entry['task'] + '.json')
        assert sha(original) == entry['task_sha256'], str(original)
        assert json.loads(path.read_text()) == json.loads(original.read_text()), str(path)
        tasks[entry['task']] = schema.Task.load(path)
    audits = []
    for row in summary['rows']:
        out = root / 'evidence' / row['cell_id']
        saved = json.loads((out / 'audit.json').read_text())
        assert saved == row, row['cell_id']
        answer = schema.Answer.parse((out / 'final.txt').read_text())
        task = tasks[row['task']]
        replay = scorer.score(task, answer, row['arm'], row['trial']).to_dict()
        assert replay == row['score'], row['cell_id']
        expected = {str(site) for site in task.ground_truth}
        supplied = {str(site) for site in answer.sites}
        # This panel also supports exact normalized path/symbol matching, without
        # the scorer's suffix-path tolerance or neutral test-site exceptions.
        assert expected & supplied == set(replay['found']), row['cell_id']
        assert expected - supplied == set(replay['missed']), row['cell_id']
        assert supplied - expected == set(replay['extra']), row['cell_id']
        events = [json.loads(line) for line in (out / 'stdout.jsonl').read_text().splitlines() if line.strip()]
        if row['arm'].startswith('sonnet'):
            final = [event for event in events if event.get('type') == 'result'][-1]
            fields = ['inputTokens', 'cacheCreationInputTokens', 'cacheReadInputTokens', 'outputTokens']
            tokens = sum(model[key] for model in final['modelUsage'].values() for key in fields)
            cost = final['total_cost_usd']
        else:
            turns = [event['usage'] for event in events if event.get('type') == 'turn.completed']
            tokens = sum(u['input_tokens'] + u['output_tokens'] for u in turns)
            cost = sum((u['input_tokens'] - u['cached_input_tokens']) * 5e-6
                       + u['cached_input_tokens'] * .5e-6 + u['output_tokens'] * 30e-6 for u in turns)
        assert tokens == row['audited_total_tokens'], row['cell_id']
        assert abs(cost - row['cost_usd']) < 1e-9, row['cell_id']
        audits.append(dict(cell_id=row['cell_id'], score_replayed=True,
                           exact_normalized_sites_agree=True, raw_usage_agrees=True))
    assert abs(sum(row['cost_usd'] for row in summary['rows']) - summary['estimated_spend_usd']) < 1e-9
    analysis['estimated_spend_usd'] = summary['estimated_spend_usd']
    dump(root / 'analysis.json', analysis)
    dump(root / 'replay-audit.json', dict(cells=audits, checked_cells=len(audits)))
    names = ['manifest.json', 'summary.json', 'analysis.json', 'replay-audit.json',
             'protocol.md', 'preflight.json', 'preflight.stderr.txt', 'answer-schema.json']
    names += [task + '.task.json' for task in tasks]
    for name in names:
        shutil.copy2(root / name, HERE / name)
    shutil.copytree(root / 'evidence', HERE / 'evidence', dirs_exist_ok=True)
    snapshot = HERE / 'harness-snapshot'
    snapshot.mkdir(exist_ok=True)
    for name in manifest['harness_sha256']:
        shutil.copy2(HARNESS / name, snapshot / name)
    (snapshot / 'tasks').mkdir(exist_ok=True)
    for task in tasks:
        shutil.copy2(HARNESS / 'tasks' / (task + '.json'), snapshot / 'tasks' / (task + '.json'))
    shutil.copy2(HERE.parent / 'four-way-2026-09-06/prism-working-tree.patch', HERE / 'prism-working-tree.patch')
    hashes = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.rglob('*'))
              if p.is_file() and p.name != 'SHA256SUMS.json' and '__pycache__' not in p.parts}
    dump(HERE / 'SHA256SUMS.json', hashes)
    print(json.dumps(dict(archived_files=len(hashes), replayed_cells=len(audits),
                          decision=analysis['decision'], spend=summary['estimated_spend_usd']), indent=2))


if __name__ == '__main__':
    main()
