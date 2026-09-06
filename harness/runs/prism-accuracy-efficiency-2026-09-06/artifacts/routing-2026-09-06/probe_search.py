"""Free replay of actual failed requests; never invokes a model."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
DELIVERY = PARENT / 'evidence-delivery-2026-09-06'
PANEL = PARENT / 'panel-2026-09-06'
REPO = PARENT.parents[1]
BINARY = Path('/private/tmp/prism-routing-candidate')
spec = importlib.util.spec_from_file_location('free_delivery', DELIVERY / 'probe_delivery.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / 'free-replay'
    output.mkdir()
    work = Path(tempfile.mkdtemp(prefix='prism-routing-replay-', dir='/private/tmp'))
    task_path = PANEL / 'gin-4645.task.json'
    task = json.loads(task_path.read_text())
    archive = subprocess.check_output(['git', '-C', task.get('workdir') or task['repo'], 'archive', task['pin']])
    old_manifest = json.loads((PANEL / 'manifest.json').read_text())
    expected = next(t for t in old_manifest['tasks'] if t['task'] == task['id'])
    assert hashlib.sha256(archive).hexdigest() == expected['archive_sha256']
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        pristine = {m.name: hashlib.sha256(tf.extractfile(m).read()).hexdigest()
                    for m in tf if m.isfile()}
        tf.extractall(work, filter='data')
    helper.command(['git', 'init', '-q'], work)
    (output / 'index.txt').write_text(helper.command([BINARY, 'index', work], work))
    results = []
    for trial in [1, 2]:
        source = DELIVERY / f'comparison/b/evidence/gin-4645.r{trial}.codex_prism/audit.json'
        calls = json.loads(source.read_text())['calls']
        failed = [c for c in calls if c.get('tool') == 'prism_search'
                  and 'task' in c.get('arguments', {}) and c.get('error')]
        assert len(failed) == 1
        args = failed[0]['arguments']
        responses = {}
        for variant in ['original_request', 'without_label']:
            params = dict(args)
            if variant == 'without_label':
                del params['task']
            # Fresh sessions avoid response-note deduplication affecting parity.
            client = helper.MCP(BINARY, work, output / f'r{trial}.{variant}.stderr.txt')
            try:
                schemas = client.request('tools/list', {})
                search = next(s for s in schemas['tools'] if s['name'] == 'prism_search')
                assert search['inputSchema']['properties']['task']['type'] == 'string'
                result = client.call('prism_search', params)
                assert helper.text(result).strip()
                helper.dump(output / f'r{trial}.{variant}.json', dict(arguments=params, result=result))
                responses[variant] = result
            finally:
                client.close()
        assert responses['original_request'] == responses['without_label'], 'Label changed delivery'
        results.append(dict(trial=trial, original_audit_sha256=sha(source),
                            original_error=failed[0]['error'], arguments=args,
                            new_request_succeeded=True, result_identical_without_label=True))
    assert all((work / p).is_file() and sha(work / p) == digest for p, digest in pristine.items())
    source_paths = ['internal/cli/commands.go', 'internal/mcp/tools.go',
                    'internal/mcp/rollup.go', 'internal/mcp/searchtext.go',
                    'internal/mcp/oncenotes.go', 'internal/textsearch/textsearch.go']
    helper.dump(output / 'results.json', dict(
        work=str(work), task_pin=task['pin'], binary_sha256=sha(BINARY),
        archive_sha256=hashlib.sha256(archive).hexdigest(), paid_model_runs=0,
        session_savings_measured=False, source_sha256={p: sha(REPO / p) for p in source_paths},
        cases=results))
    helper.dump(output / 'SHA256SUMS.json', {str(p.relative_to(output)): sha(p)
                                            for p in sorted(output.iterdir()) if p.is_file()})
    print(json.dumps(dict(cases=len(results), all_succeeded=True,
                          results_unchanged_by_label=True, paid_model_runs=0)))


if __name__ == '__main__':
    main()
