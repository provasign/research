"""Replay recorded Django lookups over MCP without launching a model."""
import argparse
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          check=True, timeout=240).stdout


def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.relative_to(root).parts[0] not in ['.git', '.grove']}


def tool_reply(client, name, request, expected_rejection=False):
    try:
        return client.request('tools/call', dict(name=name, arguments=request))
    except AssertionError as error:
        packet = error.args[0] if error.args else None
        if not expected_rejection or not isinstance(packet, dict) or not isinstance(packet.get('error'), dict):
            raise
        require(packet['error'].get('code') == -32000 and
                'name batch must contain only nonempty strings' in packet['error'].get('message', ''),
                'Unexpected control rejection')
        return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prism-repo', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='prism-scoped-replay-', dir='/private/tmp'))
    print('RESULTS=' + str(root), flush=True)
    report = dict(status='running', paid_model_runs=0, model_spend_usd=0)
    try:
        archive = args.evidence_root / 'artifacts'
        previous = archive / 'routing-2026-09-06/comparison/results'
        manifest = json.loads((previous / 'manifest.json').read_text())
        audit_path = previous / 'b/evidence/django-connparams.r1.codex_prism/audit.json'
        audit = json.loads(audit_path.read_text())
        original = [call['arguments'] for call in audit['calls'] if call.get('tool') == 'prism_lookup']
        require(len(original) == 5, 'Unexpected observed sequence')
        fields = original[0]['fields']
        items = []
        for request in original:
            require(request['fields'] == fields, 'Projection differs across requests')
            names = request['name'] if isinstance(request['name'], list) else [request['name']]
            file = request['file']
            if file == 'django/db/backends/base':
                file += '/base.py'
            items.extend(dict(name=name, file=file) for name in names)
        require(len(items) == 10, 'Unexpected flattened sequence')
        batch = dict(name=items, fields=fields)
        dump(root / 'requests.json', dict(original=original, scoped=batch))
        task_path = previous / 'django-connparams.task.json'
        task = json.loads(task_path.read_text())
        pin = next(t for t in manifest['tasks'] if t['task'] == 'django-connparams')
        source_task = archive / 'panel-2026-09-06/harness-snapshot/tasks/django-connparams.json'
        archived_sums = json.loads((previous / 'SHA256SUMS.json').read_text())
        require(sha(task_path) == archived_sums[task_path.name], 'Archived task bytes differ')
        require(sha(source_task) == pin['task_sha256'], 'Frozen source task differs')
        require(task == json.loads(source_task.read_text()), 'Archived task semantics differ')
        corpus = command(['git', '-C', task.get('workdir') or task['repo'], 'archive', pin['pin']])
        require(hashlib.sha256(corpus).hexdigest() == pin['archive_sha256'], 'Corpus archive differs')
        require(sha(args.before) == manifest['binary_sha256'], 'Wrong control binary')
        for name, digest in manifest['source_sha256'].items():
            data = command(['git', 'show', 'db23621:' + name], args.prism_repo)
            require(hashlib.sha256(data).hexdigest() == digest, 'Control source differs: ' + name)
        source_names = command(['git', 'diff', '--name-only', 'HEAD', '--', 'internal'], args.prism_repo).decode().splitlines()
        require(source_names, 'Expected candidate source changes')
        helper_path = archive / 'evidence-delivery-2026-09-06/probe_delivery.py'
        spec = importlib.util.spec_from_file_location('frozen_mcp_transport', helper_path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        frozen = dict(prism_head=command(['git', 'rev-parse', 'HEAD'], args.prism_repo).decode().strip(),
                      corpus_pin=pin['pin'], corpus_sha256=pin['archive_sha256'],
                      source_sha256={n: sha(args.prism_repo / n) for n in source_names},
                      before_binary_sha256=sha(args.before), after_binary_sha256=sha(args.after),
                      observed_audit_sha256=sha(audit_path), transport_sha256=sha(helper_path),
                      probe_sha256=sha(HERE / 'probe.py'), protocol_sha256=sha(HERE / 'PROTOCOL.md'))
        dump(root / 'manifest.json', frozen)
        shutil.copy2(HERE / 'PROTOCOL.md', root / 'PROTOCOL.md')
        (root / 'candidate.patch').write_bytes(command(['git', 'diff', '--binary', 'HEAD', '--', 'internal'], args.prism_repo))
        observations = {}
        for label, binary in [('before', args.before), ('after', args.after)]:
            work = root / (label + '-work')
            work.mkdir()
            with tarfile.open(fileobj=io.BytesIO(corpus)) as tf:
                tf.extractall(work, filter='data')
            command(['git', 'init', '-q'], work)
            originals = inventory(work)
            out = root / label
            out.mkdir()
            (out / 'index.txt').write_bytes(command([binary, 'index', work], work))
            client = helper.MCP(binary, work, out / 'mcp.stderr.txt')
            try:
                def call(name, request, filename):
                    result = tool_reply(client, name, request,
                                        expected_rejection=label == 'before' and filename == 'scoped-batch.json')
                    dump(out / filename, result)
                    return result
                schemas = client.request('tools/list', {})
                dump(out / 'tools-list.json', schemas)
                lookups = [t for t in schemas['tools'] if t['name'] == 'prism_lookup']
                require(len(lookups) == 1, 'Missing lookup schema')
                schema_text = json.dumps(lookups[0], separators=(',', ':'))
                require(('exact per-item file scope' in schema_text) == (label == 'after'), 'Wrong schema contract')
                impact = call('prism_change_impact', dict(query='BaseDatabaseWrapper.get_connection_params'), 'impact.json')
                legacy = [call('prism_lookup', request, f'legacy-{i}.json') for i, request in enumerate(original)]
                scalar = [call('prism_lookup', dict(name=item['name'], file=item['file'], fields=fields), f'scalar-{i}.json')
                          for i, item in enumerate(items)]
                combined = call('prism_lookup', batch, 'scoped-batch.json')
                require(all(not r.get('isError') for r in [impact, *legacy, *scalar]), 'Legacy MCP error')
                require(bool(combined.get('isError') or combined.get('error')) == (label == 'before'), 'Unexpected scoped batch status')
                singles = []
                if label == 'after':
                    singles = [call('prism_lookup', dict(name=[item], fields=fields), f'scoped-single-{i}.json')
                               for i, item in enumerate(items)]
                    require(all(not r.get('isError') for r in singles), 'Scoped single MCP error')
                observations[label] = dict(impact=impact, legacy=legacy, scalar=scalar,
                                           combined=combined, singles=singles, schema_bytes=len(schema_text.encode()))
            finally:
                client.close()
            require(inventory(work) == originals, 'Corpus was modified')
            head = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=work, capture_output=True)
            require(head.returncode != 0, 'Corpus has git history')
        before, after = observations['before'], observations['after']
        require(before['impact'] == after['impact'], 'Impact response changed')
        require(before['legacy'] == after['legacy'], 'Legacy request behavior changed')
        text = helper.text(after['combined'])
        require(text == ''.join(helper.text(r) for r in after['singles']), 'Batch differs from scoped singles')
        misses = [i for i, result in enumerate(after['singles']) if '// NO EXACT MATCH' in helper.text(result)]
        require(misses == [2, 3], 'Wrong explicit misses: ' + str(misses))
        for i in [0, 1, 4, 5, 6, 7, 8, 9]:
            expected = helper.text(before['scalar'][i])
            require(text.count(expected) == 1, 'Valid scalar evidence missing/duplicated: ' + str(items[i]))
        require('NOT DELIVERED' not in text and '// ERROR:' not in text, 'Scoped batch incomplete')
        require(frozen['source_sha256'] == {n: sha(args.prism_repo / n) for n in source_names}, 'Source changed during replay')
        before_bytes = sum(len(helper.text(r).encode()) for r in before['legacy'])
        report.update(status='pass', corpus_unchanged=True, full_impact_response_identical=True,
                      legacy_requests_identical=True, observed_lookup_calls=5, candidate_batch_calls=1,
                      scoped_items=10, preserved_valid_bodies=8, explicit_wrong_scope_or_receiver_misses=misses,
                      batch_equals_scoped_singles=True, old_response_bytes=before_bytes,
                      candidate_response_bytes=len(text.encode()),
                      lookup_schema_bytes={label: row['schema_bytes'] for label, row in observations.items()},
                      session_token_savings=None, autonomous_accuracy=None)
    except Exception as error:
        report.update(status='fail', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        dump(root / 'report.json', report)
        checks = {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
                  if p.is_file() and p.relative_to(root).parts[0] not in ['before-work', 'after-work']
                  and p.name != 'SHA256SUMS.json'}
        dump(root / 'SHA256SUMS.json', checks)
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
