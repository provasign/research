"""Free replay for imported Go interface contract recovery."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
GROVE = Path('/private/tmp/grove-go-interface-impact')
PRISM = Path('/private/tmp/prism-product-clean')
BINARIES = {
    'before': Path('/private/tmp/prism-go-cross-before'),
    'after': Path('/private/tmp/prism-go-cross-after'),
}
GROVE_BEFORE = '184f8a9ee57170d41e96029e70d578655f901a34'
GROVE_AFTER = '8dad45479ff72b78c7c8e930c6d49cbed18b39a8'
SOURCES = [
    'internal/graph/changeimpact.go',
    'internal/index/indexer.go',
    'internal/index/nativecarry_test.go',
    'internal/native/go.go',
    'internal/native/go_importer.go',
    'internal/native/go_interfaces.go',
    'internal/native/go_interfaces_test.go',
    'pkg/grove/go_interface_impact_test.go',
]
GROUPS = ['declarations', 'supers', 'family', 'callers', 'declaringTypes']
TRIALS = 6
FIXTURE = {
    'go.mod': 'module example.com/cross\n\ngo 1.22\n',
    'api/api.go': '''package api
import "net/http"
type Writer interface { http.CloseNotifier }
func Stream(w Writer) { <-w.CloseNotify() }
''',
    'impl/impl.go': '''package impl
import (
    "example.com/cross/api"
    "example.com/cross/util"
)
type Writer struct{}
func (*Writer) CloseNotify() <-chan bool { return nil }
var _ api.Writer = (*Writer)(nil)
var _ = util.Marker
type Wrong struct{}
func (*Wrong) CloseNotify() chan bool { return nil }
''',
    'util/util.go': 'package util\nconst Marker = true\n',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def command(args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          check=True, timeout=300).stdout


def inventory(value):
    return {group: {(site['filePath'], site.get('qualifiedName') or site['name'])
                    for site in value.get(group, [])} for group in GROUPS}


def write_fixture(root):
    for relative, body in FIXTURE.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def main():
    assert not (HERE / 'results').exists(), 'Never overwrite retained evidence'
    assert command(['git', 'rev-parse', 'HEAD'], GROVE).decode().strip() == GROVE_AFTER
    run = Path(tempfile.mkdtemp(prefix='prism-go-cross-', dir='/private/tmp'))
    out = run / 'evidence'
    out.mkdir()
    cache = run / 'cache'
    cache.mkdir()
    home = run / 'home'
    home.mkdir()
    os.environ['HOME'] = str(home)
    os.environ['XDG_CACHE_HOME'] = str(cache)
    print('RUN_DIR=' + str(run), flush=True)
    archive = command(['git', 'archive', 'HEAD'], PRISM)
    manifest = {
        'grove_before': GROVE_BEFORE,
        'grove_after': GROVE_AFTER,
        'prism_commit': command(['git', 'rev-parse', 'HEAD'], PRISM).decode().strip(),
        'prism_archive_sha256': hashlib.sha256(archive).hexdigest(),
        'binaries': {arm: sha(path) for arm, path in BINARIES.items()},
        'grove_source_sha256': {path: sha(GROVE / path) for path in SOURCES},
        'probe_sha256': sha(Path(__file__)),
        'protocol_sha256': sha(HERE / 'PROTOCOL.md'),
        'timing_trials_per_arm': TRIALS,
    }
    result = {
        'status': 'running',
        'model_runs': 0,
        'estimated_model_cost_usd': 0,
        'session_token_saving': None,
        'autonomous_accuracy': None,
    }
    try:
        for path in SOURCES:
            destination = out / 'grove-source' / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GROVE / path, destination)
        fixture_out = out / 'fixture'
        write_fixture(fixture_out)
        observed = {}
        impact_returncodes = {}
        for arm, binary in BINARIES.items():
            arm_out = out / arm
            arm_out.mkdir()
            work = run / ('fixture-' + arm)
            write_fixture(work)
            pristine = {path: sha(work / path) for path in FIXTURE}
            (arm_out / 'binary-build.txt').write_bytes(command(['go', 'version', '-m', binary]))
            started = time.monotonic()
            indexed = subprocess.run([str(binary), 'index', str(work)], cwd=work,
                                     capture_output=True, timeout=300)
            dump(arm_out / 'fixture-index.json', {
                'returncode': indexed.returncode,
                'seconds': time.monotonic() - started,
            })
            (arm_out / 'fixture-index.stdout.txt').write_bytes(indexed.stdout)
            (arm_out / 'fixture-index.stderr.txt').write_bytes(indexed.stderr)
            indexed.check_returncode()
            impact = subprocess.run([
                str(binary), 'change-impact', 'Writer.CloseNotify',
                '--file', 'api/api.go', '--format', 'json',
            ], cwd=work, capture_output=True, timeout=300)
            (arm_out / 'impact.payload.json').write_bytes(impact.stdout)
            (arm_out / 'impact.stderr.txt').write_bytes(impact.stderr)
            impact_returncodes[arm] = impact.returncode
            if arm == 'before':
                assert impact.returncode != 0
                observed[arm] = None
            else:
                impact.check_returncode()
                observed[arm] = json.loads(impact.stdout)
            assert all(sha(work / path) == digest for path, digest in pristine.items())

        after = inventory(observed['after'])
        assert after['family'] == {('impl/impl.go', 'Writer.CloseNotify')}
        assert ('api/api.go', 'Writer.CloseNotify') in after['declarations']
        assert ('api/api.go', 'Stream') in after['callers']
        assert all(name != 'Wrong.CloseNotify' for _, name in after['family'])
        assert observed['after']['completeness'] == 'partial'

        timings = {arm: [] for arm in BINARIES}
        last_indexes = {}
        for trial in range(TRIALS):
            order = ('before', 'after') if trial % 2 == 0 else ('after', 'before')
            for arm in order:
                with tempfile.TemporaryDirectory(prefix='prism-cross-perf-', dir='/private/tmp') as temp:
                    work = Path(temp)
                    with tarfile.open(fileobj=io.BytesIO(archive)) as archive_file:
                        archive_file.extractall(work, filter='data')
                    started = time.monotonic()
                    indexed = subprocess.run([str(BINARIES[arm]), 'index', str(work)], cwd=work,
                                             capture_output=True, timeout=300)
                    timings[arm].append(time.monotonic() - started)
                    indexed.check_returncode()
                    last_indexes[arm] = json.loads(indexed.stdout)
        timing_summary = {
            arm: {
                'seconds': timings[arm],
                'median_seconds': statistics.median(timings[arm]),
                'mean_seconds': statistics.mean(timings[arm]),
                'last_index': last_indexes[arm],
            }
            for arm in BINARIES
        }
        before_median = timing_summary['before']['median_seconds']
        after_median = timing_summary['after']['median_seconds']
        timing_summary['median_delta_seconds'] = after_median - before_median
        timing_summary['median_delta_percent'] = ((after_median / before_median) - 1) * 100
        dump(out / 'timings.json', timing_summary)
        assert last_indexes['before']['symbolCount'] == last_indexes['after']['symbolCount']
        assert last_indexes['before']['edgeCount'] == last_indexes['after']['edgeCount']
        assert all(sha(BINARIES[arm]) == digest for arm, digest in manifest['binaries'].items())
        assert all(sha(GROVE / path) == digest for path, digest in manifest['grove_source_sha256'].items())
        result.update({
            'status': 'pass',
            'before_query_returncode': impact_returncodes['before'],
            'before_query_hard_failed': True,
            'after_counts': {group: len(after[group]) for group in GROUPS},
            'wrong_signature_excluded': True,
            'coverage_remains_partial': True,
            'sources_unchanged': True,
            'timing': {
                'trials_per_arm': TRIALS,
                'before_median_seconds': before_median,
                'after_median_seconds': after_median,
                'median_delta_seconds': after_median - before_median,
                'median_delta_percent': ((after_median / before_median) - 1) * 100,
            },
        })
    except BaseException as exc:
        result.update(status='failed', error=repr(exc))
        raise
    finally:
        dump(out / 'manifest.json', manifest)
        dump(out / 'results.json', result)
        shutil.copy2(HERE / 'PROTOCOL.md', out / 'PROTOCOL.md')
        shutil.copytree(out, HERE / 'results')
        dump(HERE / 'results/SHA256SUMS.json', {
            str(path.relative_to(out)): sha(path)
            for path in sorted(out.rglob('*')) if path.is_file()
        })
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
