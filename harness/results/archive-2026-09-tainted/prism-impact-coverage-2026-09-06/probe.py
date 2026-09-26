"""Free before/after coverage replay. No models, billing or saved-corpus mutation."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
PRODUCT = Path('/private/tmp/prism-product-clean')
EVIDENCE = HERE.parent / 'prism-accuracy-efficiency-2026-09-06/artifacts'
PANEL = EVIDENCE / 'panel-2026-09-06'
TRANSPORT = EVIDENCE / 'evidence-delivery-2026-09-06/probe_delivery.py'
BINARIES = {'before': Path('/private/tmp/prism-scoped-lookup-candidate'),
            'after': Path('/private/tmp/prism-impact-coverage-candidate')}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          check=True, timeout=240).stdout


def impact_inventory(value):
    return {key: value.get(key, []) for key in
            ['declarations', 'supers', 'family', 'callers', 'declaringTypes']}


def main():
    assert not (HERE / 'results').exists(), 'Never overwrite a retained replay'
    assert sha(BINARIES['before']) == 'ac41360cd212fce40bd627884d3a606720d59e235806cd97978abb5cd2d0867d'
    assert sha(TRANSPORT) == '830b8277b03abeb1f02d408b6a07a17a3fd3382ff43cb92318bf7250a6e89ad1'
    spec = importlib.util.spec_from_file_location('frozen_transport', TRANSPORT)
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    root = Path(tempfile.mkdtemp(prefix='prism-impact-coverage-', dir='/private/tmp'))
    out = root / 'evidence'
    out.mkdir()
    print('RUN_DIR=' + str(root), flush=True)
    previous = json.loads((PANEL / 'manifest.json').read_text())
    request_source = HERE.parent / 'prism-scoped-lookup-ab-2026-09-06/results/b/evidence/django-connparams.r1.codex_prism/audit.json'
    scoped = next(c['arguments'] for c in json.loads(request_source.read_text())['calls'] if c.get('tool') == 'prism_lookup')
    sources = command(['git', 'diff', 'HEAD', '--name-only', '--', 'internal'], PRODUCT).decode().splitlines()
    manifest = dict(product_head=command(['git', 'rev-parse', 'HEAD'], PRODUCT).decode().strip(),
        source_sha256={p: sha(PRODUCT / p) for p in sources},
        binaries={v: sha(p) for v, p in BINARIES.items()},
        probe_sha256=sha(Path(__file__)), protocol_sha256=sha(HERE / 'PROTOCOL.md'),
        transport_sha256=sha(TRANSPORT), request_source_sha256=sha(request_source), tasks=[])
    dump(out / 'manifest.json', manifest)
    (out / 'product.patch').write_bytes(command(['git', 'diff', 'HEAD', '--', 'internal'], PRODUCT))
    result = dict(model_runs=0, estimated_model_cost_usd=0, session_token_saving=None,
                  autonomous_accuracy=None, tasks={}, status='running')
    try:
        for task_id in ['gin-4645', 'django-connparams']:
            task_path = PANEL / (task_id + '.task.json')
            task = json.loads(task_path.read_text())
            entry = next(t for t in previous['tasks'] if t['task'] == task_id)
            archive = command(['git', '-C', task['workdir'], 'archive', task['pin']])
            assert hashlib.sha256(archive).hexdigest() == entry['archive_sha256']
            manifest['tasks'].append(dict(entry, archived_task_sha256=sha(task_path)))
            shutil.copy2(task_path, out / task_path.name)
            requests = ([('impact-close', 'prism_change_impact', {'query': 'responseWriter.CloseNotify', 'file': 'response_writer.go'}),
                         ('impact-hijack', 'prism_change_impact', {'query': 'responseWriter.Hijack', 'file': 'response_writer.go'}),
                         ('bodies', 'prism_lookup', {'name': ['responseWriter.CloseNotify', 'responseWriter.Hijack'], 'file': 'response_writer.go', 'fields': ['signature', 'body']})]
                        if task_id == 'gin-4645' else
                        [('impact', 'prism_change_impact', {'query': 'BaseDatabaseWrapper.get_connection_params', 'file': 'django/db/backends/base/base.py'}),
                         ('bodies', 'prism_lookup', scoped)])
            observed = {}
            for variant, binary in BINARIES.items():
                base = out / (task_id + '.' + variant)
                base.mkdir()
                work = root / (task_id + '.' + variant)
                work.mkdir()
                with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
                    tf.extractall(work, filter='data')
                pristine = {str(p.relative_to(work)): sha(p) for p in work.rglob('*') if p.is_file()}
                command(['git', 'init', '-q'], work)
                assert subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=work, capture_output=True).returncode != 0
                (base / 'index.txt').write_bytes(command([binary, 'index', work], work))
                observed[variant] = {}
                client = transport.MCP(binary, work, base / 'mcp.stderr.txt')
                try:
                    dump(base / 'schema.json', client.request('tools/list', {}))
                    for identity, tool, args in requests:
                        dump(base / (identity + '.request.json'), dict(tool=tool, arguments=args))
                        response = client.call(tool, args)
                        dump(base / (identity + '.response.json'), response)
                        observed[variant][identity] = transport.text(response)
                finally:
                    client.close()
                for identity, tool, args in requests:
                    if tool != 'prism_change_impact':
                        continue
                    payload = json.loads(command([binary, 'change-impact', args['query'], '--file', args['file'], '--format', 'json'], work))
                    dump(base / (identity + '.payload.json'), payload)
                    observed[variant][identity + '-payload'] = payload
                assert all(sha(work / p) == digest for p, digest in pristine.items())
                print('REPLAYED ' + task_id + '.' + variant, flush=True)
            before, after = observed['before'], observed['after']
            assert before['bodies'] == after['bodies'], 'Body delivery changed'
            checks = dict(bodies_identical=True, inventories_identical=True, sources_unchanged=True, history_absent=True)
            for identity, tool, args in requests:
                if tool != 'prism_change_impact':
                    continue
                a, b = before[identity + '-payload'], after[identity + '-payload']
                assert impact_inventory(a) == impact_inventory(b), 'Required sites changed'
                if task_id == 'gin-4645':
                    assert a['completeness'] == 'closed' and b['completeness'] == 'partial'
                    assert b['coverageNote'] in after[identity]
                    assert a == {**{k: v for k, v in b.items() if k != 'coverageNote'}, 'completeness': 'closed'}
                    checks[identity] = dict(before_tier='closed', after_tier='partial',
                        before_response_bytes=len(before[identity].encode()), after_response_bytes=len(after[identity].encode()))
                else:
                    assert a == b and before[identity] == after[identity]
                    expected = set(task['ground_truth'])
                    supplied = {s['filePath'] + ':' + s['name'] for group in impact_inventory(b).values() for s in group}
                    assert expected <= supplied
                    checks['impact_identical'] = True
                    checks['gold_sites_in_impact'] = len(expected)
            if task_id == 'gin-4645':
                text = (root / 'gin-4645.after/context.go').read_text()
                assert 'func (c *Context) Stream(' in text and 'clientGone := w.CloseNotify()' in text
                checks['interface_call_still_in_source'] = True
                checks['engine_recall_repaired'] = False
            result['tasks'][task_id] = checks
        assert all(sha(BINARIES[v]) == digest for v, digest in manifest['binaries'].items())
        assert all(sha(PRODUCT / p) == digest for p, digest in manifest['source_sha256'].items())
        result['status'] = 'pass'
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
