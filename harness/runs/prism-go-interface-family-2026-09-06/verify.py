"""Read-only verification of the retained family replay."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = ['declarations', 'supers', 'family', 'callers', 'declaringTypes']


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory(value):
    return {g: {(s['filePath'], s.get('qualifiedName') or s['name'])
                for s in value.get(g, [])} for g in GROUPS}


def main():
    base = HERE / 'results'
    sums = read(base / 'SHA256SUMS.json')
    for path, digest in sums.items(): assert sha(base / path) == digest, path
    manifest = read(base / 'manifest.json')
    assert manifest['probe_sha256'] == sha(HERE / 'probe.py')
    assert manifest['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
    for path, digest in manifest['grove_source_sha256'].items():
        assert sha(base / 'grove-source' / path) == digest
    result = read(base / 'results.json')
    assert result['status'] == 'pass' and result['model_runs'] == result['estimated_model_cost_usd'] == 0
    assert result['session_token_saving'] is result['autonomous_accuracy'] is None
    for name in ['concrete', 'interface']:
        before = inventory(read(base / 'before' / (name + '.payload.json')))
        after = inventory(read(base / 'after' / (name + '.payload.json')))
        assert all(before[g] <= after[g] for g in GROUPS)
        observed = result['observations'][name]
        assert observed['before_counts'] == {g: len(before[g]) for g in GROUPS}
        assert observed['after_counts'] == {g: len(after[g]) for g in GROUPS}
        assert observed['added'] == {g: [list(s) for s in sorted(after[g]-before[g])] for g in GROUPS}
    print(f'PASS: {len(sums)} hashes; raw inventories reproduced; no model/token-saving claim')


if __name__ == '__main__': main()
