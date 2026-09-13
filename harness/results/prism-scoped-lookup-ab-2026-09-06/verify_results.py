"""Read-only archived-result replay; no model, live checkout or binary required."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent / 'prism-accuracy-efficiency-2026-09-06/artifacts'
SNAPSHOT = EVIDENCE / 'panel-2026-09-06/harness-snapshot'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def inspect_calls(calls):
    scoped = []
    errors = []
    for call in calls:
        args = call.get('arguments') or {}
        if isinstance(args, str):
            args = json.loads(args)
        failed = (call.get('type') == 'mcp_tool_call' and
                  (call.get('status') != 'completed' or bool(call.get('error'))
                   or bool((call.get('result') or {}).get('isError'))))
        if failed:
            errors.append(dict(tool=call.get('tool'), arguments=args, error=call.get('error'),
                               result=call.get('result')))
        names = args.get('name')
        if call.get('tool') == 'prism_lookup' and isinstance(names, list):
            items = [item for item in names if isinstance(item, dict)]
            if items:
                scoped.append(dict(items=items, successful_response=not failed,
                                   call_id=call.get('id')))
    return dict(scoped_calls=scoped, mcp_errors=errors,
                native_commands=[c['command'] for c in calls if c.get('type') == 'command_execution'],
                sequence=[c.get('tool', c.get('type')) for c in calls])


def verify(root):
    hashes = json.loads((root / 'SHA256SUMS.json').read_text())
    for name, digest in hashes.items():
        assert sha(root / name) == digest, 'Archive changed: ' + name
    manifest = json.loads((root / 'manifest.json').read_text())
    for name, digest in manifest['harness_sha256'].items():
        assert sha(SNAPSHOT / name) == digest
    for name, digest in manifest['frozen_sha256'].items():
        assert sha(EVIDENCE / name) == digest
    for name, digest in manifest['local_sha256'].items():
        assert sha(HERE / name) == digest
    schema = module('schema', SNAPSHOT / 'schema.py')
    score = module('score', SNAPSHOT / 'score.py')
    analysis = module('scoped_analysis', EVIDENCE / 'evidence-delivery-2026-09-06/comparison/analyze.py')
    summary = json.loads((root / 'summary.json').read_text())
    assert summary['status'] not in ['prepared', 'running']
    replayed = []
    for row in summary['rows']:
        out = root / row['evidence_path']
        assert row == json.loads((out / 'comparison.json').read_text())
        original = {k: v for k, v in row.items() if k not in
                    ['variant', 'comparison_id', 'evidence_path', 'diagnostics']}
        assert original == json.loads((out / 'audit.json').read_text())
        events = [json.loads(line) for line in (out / 'stdout.jsonl').read_text().splitlines() if line.strip()]
        calls = [event['item'] for event in events if event.get('type') == 'item.completed'
                 and event['item'].get('type') in
                 ['command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call', 'file_change']]
        assert calls == row['calls']
        assert analysis.diagnostics(calls) == row['diagnostics']
        usage = [event['usage'] for event in events if event.get('type') == 'turn.completed']
        if row['measurement_complete']:
            assert usage
            for u in usage:
                assert all(type(u[k]) is int and u[k] >= 0 for k in
                           ['input_tokens', 'cached_input_tokens', 'output_tokens'])
                assert u['cached_input_tokens'] <= u['input_tokens']
            assert sum(u['input_tokens'] + u['output_tokens'] for u in usage) == row['audited_total_tokens']
            cost = sum(((u['input_tokens'] - u['cached_input_tokens']) * 5
                        + u['cached_input_tokens'] * .5 + u['output_tokens'] * 30) / 1e6 for u in usage)
            assert abs(cost - row['cost_usd']) < 1e-9
        else:
            assert row['audited_total_tokens'] is None and row.get('cost_usd') is None
        task = schema.Task.load(root / (row['task'] + '.task.json'))
        answer = schema.Answer.parse((out / 'final.txt').read_text())
        rescored = score.score(task, answer, row['arm'], row['trial']).to_dict()
        assert rescored == row['score']
        expected, supplied = {str(s) for s in task.ground_truth}, {str(s) for s in answer.sites}
        assert expected & supplied == set(rescored['found'])
        assert expected - supplied == set(rescored['missed'])
        assert supplied - expected == set(rescored['extra'])
        replayed.append(dict(comparison_id=row['comparison_id'], **inspect_calls(calls)))
    result = analysis.analyze(summary['rows'])
    if summary.get('unmeasured_attempts'):
        result.update(complete=False, decision='inconclusive', estimated_spend_usd=None,
                      unmeasured_attempts=summary['unmeasured_attempts'])
    assert result == json.loads((root / 'analysis.json').read_text())
    assert result['estimated_spend_usd'] == summary['estimated_spend_usd']
    return dict(checksum_checks=len(hashes), replayed_cells=len(replayed),
                decision=result['decision'], estimated_spend_usd=result['estimated_spend_usd'],
                diagnostics=replayed)


if __name__ == '__main__':
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results'), indent=2))
