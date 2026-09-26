"""Preserve the comparison and replay raw answers/usage without running models."""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys

from analyze import analyze, diagnostics, known

HERE = Path(__file__).resolve().parent
PANEL = HERE.parents[1]/'panel-2026-09-06'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def main():
    root = Path(sys.argv[1]).resolve()
    assert root != HERE, 'Use the original run directory'
    manifest = json.loads((root/'manifest.json').read_text())
    summary = json.loads((root/'summary.json').read_text())
    assert summary['status'] != 'running', 'Wait until the run finishes'
    for name, digest in manifest['local_sha256'].items():
        assert sha(HERE/name) == digest, 'Changed during execution: '+name
    for name, digest in manifest['harness_sha256'].items():
        assert sha(PANEL/'harness-snapshot'/name) == digest, name
    for variant, directory in manifest['variant_directories'].items():
        assert sha(root/directory/'prism-candidate') == manifest['binaries'][variant], variant
    sys.path.insert(0, str(PANEL/'harness-snapshot'))
    schema, scorer = importlib.import_module('schema'), importlib.import_module('score')
    replayed = []
    for row in summary['rows']:
        evidence = root/row['evidence_path']
        original = json.loads((evidence/'audit.json').read_text())
        assert {k:v for k,v in row.items() if k not in ['variant','comparison_id','evidence_path','diagnostics']} == original
        assert row == json.loads((evidence/'comparison.json').read_text())
        task_path = root/(row['task']+'.task.json')
        assert task_path.read_bytes() == (PANEL/task_path.name).read_bytes()
        task = schema.Task.load(task_path)
        answer = schema.Answer.parse((evidence/'final.txt').read_text())
        score = scorer.score(task, answer, row['arm'], row['trial']).to_dict()
        assert score == row['score'], row['comparison_id']
        expected, supplied = {str(s) for s in task.ground_truth}, {str(s) for s in answer.sites}
        assert expected & supplied == set(score['found'])
        assert expected - supplied == set(score['missed'])
        assert supplied - expected == set(score['extra'])
        assert diagnostics(row['calls']) == row['diagnostics']
        events = [json.loads(line) for line in (evidence/'stdout.jsonl').read_text().splitlines() if line.strip()]
        usage = [e['usage'] for e in events if e.get('type')=='turn.completed']
        usage_checked = False
        if row['measurement_complete']:
            assert usage
            total = sum(u['input_tokens']+u['output_tokens'] for u in usage)
            cost = sum((u['input_tokens']-u['cached_input_tokens'])*5e-6
                       +u['cached_input_tokens']*.5e-6+u['output_tokens']*30e-6 for u in usage)
            assert total == row['audited_total_tokens']
            assert known(row['cost_usd']) and abs(cost-row['cost_usd']) < 1e-9
            usage_checked = True
        replayed.append(dict(comparison_id=row['comparison_id'], score_replayed=True,
                             exact_normalized_sites_agree=True, raw_usage_checked=usage_checked))
    result = analyze(summary['rows'])
    assert result['estimated_spend_usd'] == summary['estimated_spend_usd']
    dump(root/'analysis.json', result)
    dump(root/'replay-audit.json', dict(cells=replayed, replayed_cells=len(replayed)))
    for name in ['manifest.json','summary.json','analysis.json','replay-audit.json','PROTOCOL.md']:
        shutil.copy2(root/name, HERE/name)
    for entry in manifest['tasks']:
        shutil.copy2(root/(entry['task']+'.task.json'), HERE/(entry['task']+'.task.json'))
    for directory in manifest['variant_directories'].values():
        target = HERE/directory
        target.mkdir(exist_ok=True)
        shutil.copytree(root/directory/'evidence', target/'evidence', dirs_exist_ok=True)
        for name in ['preflight.json','preflight.stderr.txt','answer-schema.json']:
            shutil.copy2(root/directory/name, target/name)
    checksums = {str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*'))
                 if p.is_file() and p.name!='SHA256SUMS.json' and '__pycache__' not in p.parts}
    dump(HERE/'SHA256SUMS.json', checksums)
    print(json.dumps(dict(replayed_cells=len(replayed), archived_files=len(checksums),
                          decision=result['decision'], estimated_spend_usd=result['estimated_spend_usd']), indent=2))


if __name__=='__main__':
    main()
