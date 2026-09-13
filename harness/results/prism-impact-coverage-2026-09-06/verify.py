"""Read-only verification of free replay artifacts; no temporary binary needed."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = ['declarations', 'supers', 'family', 'callers', 'declaringTypes']


def read(path):
    return json.loads(path.read_text())


def tool_text(path):
    return '\n'.join(c['text'] for c in read(path)['content'] if c['type'] == 'text')


def verify():
    checks = 0
    for directory in ['failed-sandbox', 'results']:
        root = HERE / directory
        for name, digest in read(root / 'SHA256SUMS.json').items():
            assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
            checks += 1
    root = HERE / 'results'
    result = read(root / 'results.json')
    assert result['status'] == 'pass' and result['model_runs'] == 0
    assert result['session_token_saving'] is None and result['autonomous_accuracy'] is None
    assert read(HERE / 'failed-sandbox/results.json')['status'] == 'failed'
    for task, identities in [('gin-4645', ['impact-close', 'impact-hijack']),
                             ('django-connparams', ['impact'])]:
        before, after = root / (task + '.before'), root / (task + '.after')
        assert tool_text(before / 'bodies.response.json') == tool_text(after / 'bodies.response.json')
        for identity in identities:
            a, b = read(before / (identity + '.payload.json')), read(after / (identity + '.payload.json'))
            assert all(a.get(k, []) == b.get(k, []) for k in GROUPS)
            if task == 'gin-4645':
                assert a['completeness'] == 'closed' and b['completeness'] == 'partial'
                assert b['coverageNote'] in tool_text(after / (identity + '.response.json'))
                assert a == {**{k: v for k, v in b.items() if k != 'coverageNote'}, 'completeness': 'closed'}
            else:
                assert a == b
                assert tool_text(before / (identity + '.response.json')) == tool_text(after / (identity + '.response.json'))
                expected = set(read(root / (task + '.task.json'))['ground_truth'])
                supplied = {s['filePath'] + ':' + s['name'] for k in GROUPS for s in b.get(k, [])}
                assert expected <= supplied and len(expected) == 8
    return dict(checksum_checks=checks, model_runs=0, coverage_claim_corrected=True,
                engine_recall_repaired=False, session_savings_measured=False)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
