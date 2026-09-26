"""Read-only, relocation-aware checks of frozen evidence; never launches models."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'artifacts'


def load(path):
    return json.loads(path.read_text())


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def check_hashes():
    expected = load(ROOT / 'archive-manifest.json')['files']
    actual = {str(p.relative_to(ROOT)) for folder in ['artifacts', 'source-reports']
              for p in (ROOT / folder).rglob('*') if p.is_file()
              and '__pycache__' not in p.parts}
    require(actual == set(expected), 'Archive file inventory differs')
    checks = 0
    inventories = [(ROOT, expected)]
    for path in ARTIFACTS.rglob('SHA256SUMS.json'):
        inventories.append((path.parent, load(path)))
    for base, inventory in inventories:
        for name, digest in inventory.items():
            path = (base / name).resolve()
            require(path.is_relative_to(ROOT), f'Out-of-archive path: {path}')
            require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                    f'Checksum mismatch: {path}')
        if base != ROOT:
            checks += len(inventory)
    return len(expected), checks


def replay():
    panel = ARTIFACTS / 'panel-2026-09-06'
    comparison = ARTIFACTS / 'evidence-delivery-2026-09-06/comparison'
    guidance = ARTIFACTS / 'routing-2026-09-06/comparison/results'
    panel_analysis = module('frozen_panel_analysis', panel / 'analyze_panel.py')
    analysis = module('frozen_comparison_analysis', comparison / 'analyze.py')
    snapshot = panel / 'harness-snapshot'
    schema = module('schema', snapshot / 'schema.py')
    scorer = module('score', snapshot / 'score.py')
    summaries, answers = 0, 0
    decisions = {}
    for root in [panel, comparison, guidance]:
        summary = load(root / 'summary.json')
        expected = load(root / 'analysis.json')
        computed = (panel_analysis if root == panel else analysis).analyze(summary['rows'])
        if root == panel:
            computed['estimated_spend_usd'] = summary.get('estimated_spend_usd')
        require(not summary.get('unmeasured_attempts'), f'Unmeasured attempts: {root}')
        require(computed == expected, f'Summary replay differs: {root}')
        summaries += len(summary['rows'])
        decisions[str(root.relative_to(ARTIFACTS))] = computed['decision']
        if root == panel:
            continue
        for row in summary['rows']:
            out = root / row['evidence_path']
            task = schema.Task.load(root / (row['task'] + '.task.json'))
            answer = schema.Answer.parse((out / 'final.txt').read_text())
            scored = scorer.score(task, answer, row['arm'], row['trial']).to_dict()
            require(scored == row['score'], f'Score differs: {out}')
            require(analysis.diagnostics(row['calls']) == row['diagnostics'],
                    f'Diagnostics differ: {out}')
            events = [json.loads(line) for line in (out / 'stdout.jsonl').read_text().splitlines()
                      if line.strip()]
            usage = [event['usage'] for event in events if event.get('type') == 'turn.completed']
            require(usage and row['measurement_complete'], f'Missing usage: {out}')
            tokens = sum(u['input_tokens'] + u['output_tokens'] for u in usage)
            cost = sum((u['input_tokens'] - u['cached_input_tokens']) * 5e-6
                       + u['cached_input_tokens'] * .5e-6 + u['output_tokens'] * 30e-6
                       for u in usage)
            require(tokens == row['audited_total_tokens'], f'Tokens differ: {out}')
            require(abs(cost - row['cost_usd']) < 1e-9, f'Cost differs: {out}')
            answers += 1
    return dict(summary_cells=summaries, raw_answers_and_usage=answers, decisions=decisions)


def main():
    files, checks = check_hashes()
    result = replay()
    print(json.dumps(dict(copied_files=files, original_checksum_checks=checks, **result), indent=2))


if __name__ == '__main__':
    main()
