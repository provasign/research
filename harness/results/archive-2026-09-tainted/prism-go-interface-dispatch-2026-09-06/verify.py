"""Read-only artifact and result replay. No models, binaries or corpora needed."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = ['declarations', 'supers', 'family', 'callers', 'declaringTypes']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(value):
    return {g: {(s['filePath'], s.get('qualifiedName') or s['name'])
                for s in value.get(g, [])} for g in GROUPS}


def main():
    checked = 0
    for name in ['failed-sandbox', 'initial-pass', 'import-hardening-pass', 'results']:
        base = HERE / name
        sums = read(base / 'SHA256SUMS.json')
        for path, digest in sums.items():
            assert sha(base / path) == digest, (name, path)
            checked += 1
        manifest = read(base / 'manifest.json')
        for path, digest in manifest['grove_source_sha256'].items():
            assert sha(base / 'grove-source' / path) == digest
        assert manifest['probe_sha256'] == sha(HERE / 'probe.py')
        assert manifest['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
        result = read(base / 'results.json')
        assert result['model_runs'] == result['estimated_model_cost_usd'] == 0
        assert result['session_token_saving'] is result['autonomous_accuracy'] is None
        if name == 'failed-sandbox':
            assert result['status'] == 'failed'
            assert 'operation not permitted' in (base / 'before/CloseNotify.stderr.txt').read_text()
            continue
        assert result['status'] == 'pass'
        for method in ['CloseNotify', 'Hijack']:
            before = read(base / 'before' / (method + '.payload.json'))
            after = read(base / 'after' / (method + '.payload.json'))
            a, b = inventory(before), inventory(after)
            observation = result['observations'][method]
            assert observation['before_counts'] == {g: len(s) for g, s in a.items()}
            assert observation['after_counts'] == {g: len(s) for g, s in b.items()}
            assert observation['added'] == {g: [list(s) for s in sorted(b[g]-a[g])] for g in GROUPS}
            assert all(a[g] <= b[g] for g in GROUPS)
            assert before['completeness'] == after['completeness'] == 'partial'
            assert before['coverageNote'] == after['coverageNote']
            for arm in ['before', 'after']:
                response = read(base / arm / (method + '.response.json'))
                assert not response.get('isError')
                text = '\n'.join(c['text'] for c in response['content'] if c['type'] == 'text')
                assert after['coverageNote'] in text
                assert len(text.encode()) == observation[arm + '_response_bytes']
            if method == 'CloseNotify':
                assert ('context.go', 'Context.Stream') not in a['callers']
                assert ('context.go', 'Context.Stream') in b['callers']
        print(name + ': raw results verified')
    print(f'PASS: {checked} artifact hashes; no model/token-saving claim')


if __name__ == '__main__':
    main()
