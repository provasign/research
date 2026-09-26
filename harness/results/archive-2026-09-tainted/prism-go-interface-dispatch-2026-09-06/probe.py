"""Free, immutable before/after replay of native Go interface dispatch."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
PRODUCT = Path('/private/tmp/prism-product-clean')
GROVE = Path('/private/tmp/grove-go-interface-impact')
TRANSPORT = HERE.parent / 'prism-accuracy-efficiency-2026-09-06/artifacts/evidence-delivery-2026-09-06/probe_delivery.py'
BINARIES = {'before': Path('/private/tmp/prism-impact-coverage-candidate'),
            'after': Path('/private/tmp/prism-go-interface-candidate')}
SOURCES = ['internal/native/go.go', 'internal/native/go_interfaces.go',
           'internal/native/go_interfaces_test.go', 'pkg/grove/go_interface_impact_test.go']
PIN = '8d0468f72897652485933b845253386f9147a8bf'
ARCHIVE_SHA = '31b5fd56fd04361b9b377da98d2d81f535f758201ad7d1323a1ecafe4bd4981c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def command(args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          timeout=300, check=True).stdout


def inventory(value):
    return {group: {(s['filePath'], s.get('qualifiedName') or s['name'])
                    for s in value.get(group, [])}
            for group in ['declarations', 'supers', 'family', 'callers', 'declaringTypes']}


def main():
    assert not (HERE / 'results').exists(), 'Never overwrite retained evidence'
    assert sha(TRANSPORT) == '830b8277b03abeb1f02d408b6a07a17a3fd3382ff43cb92318bf7250a6e89ad1'
    spec = importlib.util.spec_from_file_location('frozen_transport', TRANSPORT)
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    root = Path(tempfile.mkdtemp(prefix='prism-go-dispatch-', dir='/private/tmp'))
    out = root / 'evidence'
    out.mkdir()
    print('RUN_DIR=' + str(root), flush=True)
    result = dict(status='running', model_runs=0, estimated_model_cost_usd=0,
                  session_token_saving=None, autonomous_accuracy=None, observations={})
    manifest = dict(product_head=command(['git', 'rev-parse', 'HEAD'], PRODUCT).decode().strip(),
                    grove_base=command(['git', 'rev-parse', 'HEAD'], GROVE).decode().strip(),
                    grove_source_sha256={p: sha(GROVE / p) for p in SOURCES},
                    binaries={v: sha(p) for v, p in BINARIES.items()},
                    pin=PIN, archive_sha256=ARCHIVE_SHA, probe_sha256=sha(Path(__file__)),
                    transport_sha256=sha(TRANSPORT), protocol_sha256=sha(HERE / 'PROTOCOL.md'))
    observed = {}
    try:
        for p in SOURCES:
            dest = out / 'grove-source' / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GROVE / p, dest)
        archive = command(['git', '-C', '/Users/tapabratapal/gvg-corpus/gin', 'archive', PIN])
        assert hashlib.sha256(archive).hexdigest() == ARCHIVE_SHA
        for variant, binary in BINARIES.items():
            base = out / variant
            base.mkdir()
            work = root / variant
            work.mkdir()
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
            observed[variant] = {}
            client = transport.MCP(binary, work, base / 'mcp.stderr.txt')
            try:
                for method in ['CloseNotify', 'Hijack']:
                    args = dict(query='responseWriter.' + method, file='response_writer.go')
                    dump(base / (method + '.request.json'), dict(tool='prism_change_impact', arguments=args))
                    response = client.request('tools/call', dict(name='prism_change_impact', arguments=args))
                    dump(base / (method + '.response.json'), response)
                    assert not response.get('isError'), response
                    observed[variant][method + '-text'] = transport.text(response)
            finally:
                client.close()
            for method in ['CloseNotify', 'Hijack']:
                completed = subprocess.run([str(binary), 'change-impact', 'responseWriter.' + method,
                                           '--file', 'response_writer.go', '--format', 'json'],
                                          cwd=work, capture_output=True, timeout=300)
                (base / (method + '.payload.json')).write_bytes(completed.stdout)
                (base / (method + '.stderr.txt')).write_bytes(completed.stderr)
                completed.check_returncode()
                observed[variant][method] = json.loads(completed.stdout)
            assert all(sha(work / p) == digest for p, digest in pristine.items())
            print('REPLAYED ' + variant, flush=True)
        for method in ['CloseNotify', 'Hijack']:
            before, after = observed['before'][method], observed['after'][method]
            a, b = inventory(before), inventory(after)
            assert all(a[group] <= b[group] for group in a), 'Previously returned site disappeared'
            assert before['completeness'] == after['completeness'] == 'partial'
            assert before['coverageNote'] == after['coverageNote']
            assert after['coverageNote'] in observed['after'][method + '-text']
            result['observations'][method] = dict(
                before_counts={g: len(s) for g, s in a.items()},
                after_counts={g: len(s) for g, s in b.items()},
                added={g: sorted(b[g]-a[g]) for g in a},
                before_response_bytes=len(observed['before'][method + '-text'].encode()),
                after_response_bytes=len(observed['after'][method + '-text'].encode()))
        stream = lambda value: any(s['filePath'] == 'context.go' and s['name'] == 'Stream'
                                   for s in value.get('callers', []))
        assert not stream(observed['before']['CloseNotify'])
        assert stream(observed['after']['CloseNotify']), 'Real Gin caller still missing'
        assert all(sha(BINARIES[v]) == digest for v, digest in manifest['binaries'].items())
        assert all(sha(GROVE / p) == digest for p, digest in manifest['grove_source_sha256'].items())
        result.update(status='pass', recovered_stream=True, coverage_remains_partial=True,
                      sources_unchanged=True, history_absent=True)
    except BaseException as exc:
        result.update(status='failed', error=repr(exc))
        raise
    finally:
        dump(out / 'manifest.json', manifest)
        dump(out / 'results.json', result)
        shutil.copy2(HERE / 'PROTOCOL.md', out / 'PROTOCOL.md')
        shutil.copytree(out, HERE / 'results')
        dump(HERE / 'results/SHA256SUMS.json', {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
