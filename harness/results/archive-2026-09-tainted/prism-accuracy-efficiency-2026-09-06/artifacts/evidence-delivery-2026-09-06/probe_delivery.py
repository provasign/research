"""Free pinned-corpus checks. Never invokes a model or estimates session savings."""
import hashlib
import io
import json
from pathlib import Path
import select
import shutil
import subprocess
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / 'panel-2026-09-06'
OLD = Path('/private/tmp/prism-panel-b4i4a554/prism-candidate')
NEW = Path('/private/tmp/prism-evidence-delivery-candidate')


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def command(args, cwd=None):
    return subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                          text=True, check=True, timeout=240).stdout


class MCP:
    def __init__(self, binary, work, stderr):
        self.err = stderr.open('w')
        self.proc = subprocess.Popen([str(binary), 'mcp', str(work)], cwd=work,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.err, bufsize=0)
        self.identity = 0
        self.request('initialize', dict(protocolVersion='2024-11-05', capabilities={},
                                       clientInfo=dict(name='free-delivery-probe', version='1')))
        self.proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')

    def request(self, method, params):
        self.identity += 1
        self.proc.stdin.write((json.dumps(dict(jsonrpc='2.0', id=self.identity,
                                              method=method, params=params))+'\n').encode())
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.proc.stdout], [], [], max(0, deadline-time.monotonic()))
            if not ready:
                break
            raw = self.proc.stdout.readline()
            if not raw:
                raise RuntimeError('MCP exited')
            result = json.loads(raw)
            if result.get('id') == self.identity:
                assert 'error' not in result, result
                return result['result']
        raise TimeoutError(method)

    def call(self, name, args):
        result = self.request('tools/call', dict(name=name, arguments=args))
        assert not result.get('isError'), result
        return result

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.err.close()


def text(result):
    return '\n'.join(c['text'] for c in result['content'] if c['type']=='text')


def main():
    root = Path(tempfile.mkdtemp(prefix='prism-delivery-probe-', dir='/private/tmp'))
    print('PROBE_ROOT='+str(root), flush=True)
    report = dict(root=str(root), paid_model_runs=0, binaries={
        label: hashlib.sha256(path.read_bytes()).hexdigest() for label, path in [('before', OLD), ('after', NEW)]}, tasks={})
    assert report['binaries']['before'] == json.loads((PANEL/'manifest.json').read_text())['binary_sha256']
    for task_id, query in [('gin-4645', 'responseWriter.Hijack'),
                           ('django-connparams', 'BaseDatabaseWrapper.get_connection_params'),
                           ('typeorm-driver-escape', 'Driver.escape')]:
        task = json.loads((PANEL/(task_id+'.task.json')).read_text())
        work = root / task_id
        work.mkdir()
        archive = subprocess.check_output(['git', '-C', task.get('workdir') or task['repo'], 'archive', task['pin']])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            tf.extractall(work, filter='data')
        command(['git', 'init', '-q'], work)
        command([NEW, 'index', work], work)
        outputs, displays = {}, {}
        for label, binary in [('before', OLD), ('after', NEW)]:
            out = json.loads(command([binary, 'change-impact', query, work, '--format', 'json'], work))
            assert not out.get('cached'), out
            outputs[label] = out
            dump(HERE/(task_id+'.'+label+'.json'), out)
            client = MCP(binary, work, HERE/(task_id+'.'+label+'.stderr.txt'))
            try:
                response = client.call('prism_change_impact', dict(query=query))
                displays[label] = text(response)
                dump(HERE/(task_id+'.'+label+'.mcp.json'), response)
                (HERE/(task_id+'.'+label+'.txt')).write_text(displays[label])
                if task_id=='gin-4645':
                    names = ['responseWriter.Hijack', 'responseWriter.CloseNotify', 'responseWriter.Flush']
                    if label=='before':
                        singles = [client.call('prism_lookup', dict(name=name, file='response_writer.go')) for name in names]
                        dump(HERE/'gin-single-lookups.json', singles)
                    else:
                        schemas = client.request('tools/list', {})
                        dump(HERE/'tools-list.json', schemas)
                        batch = client.call('prism_lookup', dict(name=names, file='response_writer.go'))
                        dump(HERE/'gin-batch-lookup.json', batch)
                        expected = [text(single) for single in singles]
                        batch_text = text(batch)
                        assert all(single in batch_text for single in expected), 'Batch lost single-lookup evidence'
                        report['gin_lookup'] = dict(single_calls=3, batch_calls=1, same_bodies=True,
                                                   before_bytes=sum(len(s.encode()) for s in expected),
                                                   after_bytes=len(batch_text.encode()))
            finally:
                client.close()
        keys = ['declarations','supers','family','callers','declaringTypes']
        identities = lambda out: {key:[(s['qualifiedName'],s['filePath'],s['line']) for s in out.get(key,[])] for key in keys}
        assert identities(outputs['before']) == identities(outputs['after']), task_id
        after = outputs['after']
        callers = after.get('callers', [])
        report['tasks'][task_id] = dict(pin=task['pin'], same_ordered_site_inventory=True,
            site_count=sum(len(after.get(k,[])) for k in keys),
            callers=len(callers), callers_with_evidence=sum(bool(s.get('evidence')) for s in callers),
            call_evidence_lines=sum(len(s.get('evidence',[])) for s in callers),
            before_text_bytes=len(displays['before'].encode()), after_text_bytes=len(displays['after'].encode()))
        print(task_id, json.dumps(report['tasks'][task_id]), flush=True)
    dump(HERE/'probe-results.json', report)
    print(json.dumps(report['gin_lookup']), flush=True)


if __name__ == '__main__':
    main()
