"""Fresh, free Gin replay for native Go interface family materialization."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
GROVE = Path('/private/tmp/grove-go-interface-impact')
BINARIES = {'before': Path('/private/tmp/prism-go-interface-candidate'),
            'after': Path('/private/tmp/prism-go-interface-family-candidate')}
SOURCES = ['internal/native/go.go', 'internal/native/go_interfaces.go',
           'internal/native/go_interfaces_test.go', 'internal/graph/changeimpact.go',
           'internal/graph/missingimpl.go', 'pkg/grove/go_interface_impact_test.go']
PIN = '8d0468f72897652485933b845253386f9147a8bf'
ARCHIVE_SHA = '31b5fd56fd04361b9b377da98d2d81f535f758201ad7d1323a1ecafe4bd4981c'
QUERIES = {'concrete': 'responseWriter.CloseNotify',
           'interface': 'ResponseWriter.CloseNotify'}
GROUPS = ['declarations', 'supers', 'family', 'callers', 'declaringTypes']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def command(args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          check=True, timeout=300).stdout


def inventory(value):
    return {g: {(s['filePath'], s.get('qualifiedName') or s['name'])
                for s in value.get(g, [])} for g in GROUPS}


def main():
    assert not (HERE / 'results').exists(), 'Never overwrite retained evidence'
    root = Path(tempfile.mkdtemp(prefix='prism-go-family-', dir='/private/tmp'))
    out = root / 'evidence'
    out.mkdir()
    print('RUN_DIR=' + str(root), flush=True)
    manifest = dict(grove_base=command(['git', 'rev-parse', 'HEAD'], GROVE).decode().strip(),
                    grove_source_sha256={p: sha(GROVE / p) for p in SOURCES},
                    binaries={v: sha(p) for v, p in BINARIES.items()}, pin=PIN,
                    archive_sha256=ARCHIVE_SHA, probe_sha256=sha(Path(__file__)),
                    protocol_sha256=sha(HERE / 'PROTOCOL.md'))
    result = dict(status='running', model_runs=0, estimated_model_cost_usd=0,
                  session_token_saving=None, autonomous_accuracy=None, observations={})
    observed = {}
    try:
        for path in SOURCES:
            dest = out / 'grove-source' / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GROVE / path, dest)
        archive = command(['git', '-C', '/Users/tapabratapal/gvg-corpus/gin', 'archive', PIN])
        assert hashlib.sha256(archive).hexdigest() == ARCHIVE_SHA
        for arm, binary in BINARIES.items():
            base, work = out / arm, root / arm
            base.mkdir(); work.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
                tf.extractall(work, filter='data')
            pristine = {str(p.relative_to(work)): sha(p) for p in work.rglob('*') if p.is_file()}
            command(['git', 'init', '-q'], work)
            assert subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=work, capture_output=True).returncode != 0
            (base / 'binary-build.txt').write_bytes(command(['go', 'version', '-m', binary]))
            start = time.monotonic()
            indexed = subprocess.run([str(binary), 'index', str(work)], cwd=work,
                                     capture_output=True, timeout=300)
            (base / 'index.stdout.txt').write_bytes(indexed.stdout)
            (base / 'index.stderr.txt').write_bytes(indexed.stderr)
            dump(base / 'index.json', dict(returncode=indexed.returncode, seconds=time.monotonic()-start))
            indexed.check_returncode()
            observed[arm] = {}
            for name, query in QUERIES.items():
                completed = subprocess.run([str(binary), 'change-impact', query,
                                            '--file', 'response_writer.go', '--format', 'json'],
                                           cwd=work, capture_output=True, timeout=300)
                (base / (name + '.payload.json')).write_bytes(completed.stdout)
                (base / (name + '.stderr.txt')).write_bytes(completed.stderr)
                completed.check_returncode()
                observed[arm][name] = json.loads(completed.stdout)
            assert all(sha(work / p) == digest for p, digest in pristine.items())
            print('REPLAYED ' + arm, flush=True)
        for name in QUERIES:
            a, b = inventory(observed['before'][name]), inventory(observed['after'][name])
            assert all(a[g] <= b[g] for g in GROUPS)
            assert observed['before'][name]['completeness'] == observed['after'][name]['completeness'] == 'partial'
            result['observations'][name] = dict(
                before_counts={g: len(a[g]) for g in GROUPS},
                after_counts={g: len(b[g]) for g in GROUPS},
                added={g: sorted(b[g]-a[g]) for g in GROUPS})
        added_supers = inventory(observed['after']['concrete'])['supers'] - inventory(observed['before']['concrete'])['supers']
        assert ('response_writer.go', 'ResponseWriter.CloseNotify') in added_supers
        assert ('response_writer.go', 'responseWriter.CloseNotify') in inventory(observed['after']['interface'])['family']
        assert all(sha(BINARIES[v]) == digest for v, digest in manifest['binaries'].items())
        assert all(sha(GROVE / p) == digest for p, digest in manifest['grove_source_sha256'].items())
        result.update(status='pass', inherited_contract_recovered=True,
                      coverage_remains_partial=True, sources_unchanged=True, history_absent=True)
    except BaseException as exc:
        result.update(status='failed', error=repr(exc))
        raise
    finally:
        dump(out / 'manifest.json', manifest)
        dump(out / 'results.json', result)
        shutil.copy2(HERE / 'PROTOCOL.md', out / 'PROTOCOL.md')
        shutil.copytree(out, HERE / 'results')
        dump(HERE / 'results/SHA256SUMS.json', {str(p.relative_to(out)): sha(p)
                                                for p in sorted(out.rglob('*')) if p.is_file()})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
