"""Read-only verification of retained imported-interface evidence."""
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
GROUPS = ['declarations', 'supers', 'family', 'callers', 'declaringTypes']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(value):
    return {group: {(site['filePath'], site.get('qualifiedName') or site['name'])
                    for site in value.get(group, [])} for group in GROUPS}


def main():
    base = HERE / 'results'
    sums = read(base / 'SHA256SUMS.json')
    for path, digest in sums.items():
        assert sha(base / path) == digest, path
    manifest = read(base / 'manifest.json')
    assert manifest['probe_sha256'] == sha(HERE / 'probe.py')
    assert manifest['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
    assert manifest['grove_before'].startswith('184f8a9e')
    assert manifest['grove_after'].startswith('8dad4547')
    for path, digest in manifest['grove_source_sha256'].items():
        assert sha(base / 'grove-source' / path) == digest

    result = read(base / 'results.json')
    assert result['status'] == 'pass'
    assert result['model_runs'] == result['estimated_model_cost_usd'] == 0
    assert result['session_token_saving'] is result['autonomous_accuracy'] is None
    assert result['before_query_hard_failed'] and result['before_query_returncode'] != 0
    before_error = (base / 'before' / 'impact.stderr.txt').read_text()
    assert 'declares no method "CloseNotify"' in before_error

    after = inventory(read(base / 'after' / 'impact.payload.json'))
    assert after['family'] == {('impl/impl.go', 'Writer.CloseNotify')}
    assert ('api/api.go', 'Writer.CloseNotify') in after['declarations']
    assert ('api/api.go', 'Stream') in after['callers']
    assert all(name != 'Wrong.CloseNotify' for _, name in after['family'])
    assert result['after_counts'] == {group: len(after[group]) for group in GROUPS}

    timings = read(base / 'timings.json')
    for arm in ('before', 'after'):
        samples = timings[arm]['seconds']
        assert len(samples) == manifest['timing_trials_per_arm'] == 6
        assert timings[arm]['median_seconds'] == statistics.median(samples)
        assert timings[arm]['last_index']['symbolCount'] == 1454
        assert timings[arm]['last_index']['edgeCount'] == 4911
    assert timings['before']['last_index']['symbolCount'] == timings['after']['last_index']['symbolCount']
    assert timings['before']['last_index']['edgeCount'] == timings['after']['last_index']['edgeCount']
    print(f'PASS: {len(sums)} hashes; hard fail recovered; six timing trials per arm; no model claim')


if __name__ == '__main__':
    main()

