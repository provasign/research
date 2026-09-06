"""Audit raw answers and usage, then archive a completed guidance run offline."""
import json
from pathlib import Path
import shutil
import sys

import run_guidance as run


def audit(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    summary = json.loads((root / 'summary.json').read_text())
    assert summary['status'] not in ['running', 'prepared']
    run.verify_identities(root, manifest)
    snapshot = run.PANEL / 'harness-snapshot'
    for name, digest in manifest['harness_sha256'].items():
        assert run.sha(snapshot / name) == digest
    sys.path.insert(0, str(snapshot))
    import schema
    import score
    replayed = []
    for row in summary['rows']:
        out = root / row['evidence_path']
        original = json.loads((out / 'audit.json').read_text())
        assert {k: v for k, v in row.items() if k not in ['variant', 'comparison_id', 'evidence_path', 'diagnostics']} == original
        assert row == json.loads((out / 'comparison.json').read_text())
        task = schema.Task.load(root / (row['task'] + '.task.json'))
        answer = schema.Answer.parse((out / 'final.txt').read_text())
        scored = score.score(task, answer, row['arm'], row['trial']).to_dict()
        assert scored == row['score']
        expected, supplied = {str(s) for s in task.ground_truth}, {str(s) for s in answer.sites}
        assert expected & supplied == set(scored['found'])
        assert expected - supplied == set(scored['missed'])
        assert supplied - expected == set(scored['extra'])
        assert run.analysis.diagnostics(row['calls']) == row['diagnostics']
        events = [json.loads(line) for line in (out / 'stdout.jsonl').read_text().splitlines() if line.strip()]
        usage = [event['usage'] for event in events if event.get('type') == 'turn.completed']
        if row['measurement_complete']:
            assert usage
            total = sum(u['input_tokens'] + u['output_tokens'] for u in usage)
            cost = sum((u['input_tokens'] - u['cached_input_tokens']) * 5e-6
                       + u['cached_input_tokens'] * .5e-6 + u['output_tokens'] * 30e-6 for u in usage)
            assert total == row['audited_total_tokens']
            assert run.analysis.known(row['cost_usd']) and abs(cost - row['cost_usd']) < 1e-9
        else:
            assert row['audited_total_tokens'] is None
        replayed.append(dict(comparison_id=row['comparison_id'], score_replayed=True,
             exact_normalized_sites_agree=True, raw_usage_checked=row['measurement_complete']))
    result = run.readout(summary['rows'], summary.get('unmeasured_attempts', []))
    assert result['estimated_spend_usd'] == summary['estimated_spend_usd']
    assert result == json.loads((root / 'analysis.json').read_text())
    run.dump(root / 'replay-audit.json', dict(cells=replayed, replayed_cells=len(replayed)))
    return manifest, result


def main():
    root = Path(sys.argv[1]).resolve()
    target = run.HERE / 'results'
    assert not target.exists(), 'Never overwrite archived results'
    manifest, result = audit(root)
    target.mkdir()
    for name in ['manifest.json', 'summary.json', 'analysis.json', 'replay-audit.json',
                 'PROTOCOL.md', 'dry-run.json', 'cells.json']:
        shutil.copy2(root / name, target / name)
    for task in manifest['tasks']:
        shutil.copy2(root / (task['task'] + '.task.json'), target / (task['task'] + '.task.json'))
    for directory in manifest['variant_directories'].values():
        base = target / directory
        base.mkdir()
        shutil.copytree(root / directory / 'evidence', base / 'evidence')
        for name in ['preflight.json', 'preflight.stderr.txt', 'answer-schema.json']:
            shutil.copy2(root / directory / name, base / name)
    run.dump(target / 'SHA256SUMS.json', {str(p.relative_to(target)): run.sha(p)
                                        for p in sorted(target.rglob('*')) if p.is_file()})
    print(json.dumps({k: v for k, v in result.items() if k != 'pairs'}, indent=2))


if __name__ == '__main__':
    main()
