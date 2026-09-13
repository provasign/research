"""Frozen three-task, two-repeat four-way panel; no outcome-based retries."""
import concurrent.futures
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent / 'four-way-2026-09-06/prism-four-way.py'
spec = importlib.util.spec_from_file_location('first_pilot', HELPER)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
TASK_IDS = ['gin-4645', 'django-connparams', 'typeorm-driver-escape']
TOOLS = ['prism_search', 'prism_query', 'prism_read', 'prism_lookup',
         'prism_change_impact', 'prism_verify']
EXPECTED_BINARY = '63f5166f6adf40f768a9cf32701a13344abcf29c51064cc9fe372dbb210a7e7d'
SOURCE_BINARY = Path('/private/tmp/prism-four-way-3k0qvcsa/prism-candidate')
LIMIT_S = 600
LAUNCH_BUDGET = 15.0
WAVE_RESERVE = 4.0


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def stop(proc):
    if proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def preflight(binary, root):
    work = root / 'preflight'
    work.mkdir()
    (work / 'README.md').write_text('PrismPanelPreflightSentinel\n')
    (work / 'main.go').write_text('package main\nfunc main() {}\n')
    bench.command(['git', 'init', '-q'], work)
    bench.command([str(binary), 'index', str(work)], work)
    records = []
    with (root / 'preflight.stderr.txt').open('w') as stderr:
        proc = subprocess.Popen([str(binary), 'mcp', str(work)], cwd=work,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=stderr, text=True, bufsize=1, start_new_session=True)
        def send(obj):
            proc.stdin.write(json.dumps(obj) + '\n')
            proc.stdin.flush()
        def receive(identity):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready, _, _ = select.select([proc.stdout], [], [], max(0, deadline-time.monotonic()))
                if not ready:
                    break
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError('MCP preflight server exited')
                record = json.loads(line)
                records.append(record)
                if record.get('id') == identity:
                    if 'error' in record:
                        raise RuntimeError(str(record['error']))
                    return record['result']
            raise TimeoutError('MCP preflight timed out')
        try:
            send(dict(jsonrpc='2.0', id=1, method='initialize', params=dict(
                protocolVersion='2024-11-05', capabilities={},
                clientInfo=dict(name='four-way-panel-preflight', version='1'))))
            receive(1)
            send(dict(jsonrpc='2.0', method='notifications/initialized'))
            send(dict(jsonrpc='2.0', id=2, method='tools/list', params={}))
            names = {t['name'] for t in receive(2)['tools']}
            assert set(TOOLS) <= names, names
            send(dict(jsonrpc='2.0', id=3, method='tools/call', params=dict(
                name='prism_search', arguments=dict(query='PrismPanelPreflightSentinel', scope='text'))))
            result = receive(3)
            assert not result.get('isError') and 'PrismPanelPreflightSentinel' in json.dumps(result)
        finally:
            stop(proc)
            dump(root / 'preflight.json', records)


def invokes_prism(command):
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    for token in tokens:
        if Path(token).name in ['prism', 'prism-candidate']:
            return True
        if ' ' in token and invokes_prism(token):
            return True
    return False


def audit_usage(rec, ev, arm):
    errors, successful, native_commands, violations = [], [], [], []
    total = rec.get('total_tokens')
    if arm.startswith('sonnet'):
        by_id = {c['id']: c['name'] for c in rec['calls']}
        for e in ev:
            for c in (e.get('message') or {}).get('content', []):
                if c.get('type') == 'tool_result':
                    name = by_id.get(c.get('tool_use_id'), '')
                    if c.get('is_error'):
                        errors.append(dict(tool=name, error=c.get('content')))
                    elif name.startswith('mcp__prism__'):
                        successful.append(name)
        model_usage = rec.get('usage', {}).get('model_usage') or {}
        fields = ['inputTokens', 'cacheCreationInputTokens', 'cacheReadInputTokens', 'outputTokens']
        if not model_usage or not all(type(m.get(k)) is int and m[k]>=0 for m in model_usage.values() for k in fields):
            rec['measurement_complete'] = False
            total = None
        else:
            counts = {k: sum(m[k] for m in model_usage.values()) for k in fields}
            rec['all_model_tokens'] = counts
            total = sum(counts.values())
        native_commands = [c['input'].get('command', '') for c in rec['calls'] if c['name']=='Bash']
        init = rec.get('init') or {}
        if not init or init.get('skills') or init.get('plugins'):
            violations.append('CLI initialization or customization isolation invalid')
        mcp_names = {m['name'] for m in init.get('mcp_servers', [])}
        if mcp_names != ({'prism'} if arm.endswith('_prism') else set()):
            violations.append('unexpected MCP server set')
        if any(c['name'] in ['Agent', 'Task', 'WebFetch', 'WebSearch'] for c in rec['calls']):
            violations.append('delegation or network tool used')
    else:
        for c in rec['calls']:
            if c['type']=='mcp_tool_call':
                if c.get('error') or c.get('status')!='completed':
                    errors.append(dict(tool=c.get('tool'), error=c.get('error')))
                elif c.get('server')=='prism':
                    successful.append(c['tool'])
                else:
                    violations.append('unexpected MCP server used')
        native_commands = [c['command'] for c in rec['calls'] if c['type']=='command_execution']
        if any(c['type'] in ['collab_tool_call', 'web_search', 'file_change'] for c in rec['calls']):
            violations.append('delegation, network tool, or edit used')
    if arm.endswith('_baseline'):
        if successful or any(invokes_prism(c) for c in native_commands):
            violations.append('native baseline used Prism')
    elif not successful:
        violations.append('no successful Prism delivery')
    rec.update(audited_total_tokens=total, prism_successful_calls=successful,
               tool_errors=errors, native_commands=native_commands, violations=violations)
    return rec


def prepare_cell(root, binary, task, archive, trial, arm, pristine):
    key = f'{task.id}.r{trial}.{arm}'
    out = root / 'evidence' / key
    out.mkdir(parents=True)
    work = root / 'work' / key
    work.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        tf.extractall(work, filter='data')
    bench.command(['git', 'init', '-q'], work)
    has_prism = arm.endswith('_prism')
    mcp = {'mcpServers': {}}
    if has_prism:
        start = time.monotonic()
        result = subprocess.run([str(binary), 'index', str(work)], cwd=work,
                                capture_output=True, text=True, timeout=240)
        (out / 'index.stdout.txt').write_text(result.stdout)
        (out / 'index.stderr.txt').write_text(result.stderr)
        dump(out / 'index.json', dict(wall_s=time.monotonic()-start, exit_code=result.returncode))
        if result.returncode:
            raise RuntimeError('Indexing failed for ' + key)
        mcp['mcpServers']['prism'] = dict(type='stdio', command=str(binary), args=['mcp', str(work)])
    dump(out / 'mcp.json', mcp)
    task_wording = ('Enumerate the containing method of every call, declaration, and override.'
                    if task.task_type=='impact' else 'Identify only the functions that must change to fix the issue.')
    prompt = '''Analyze only the repository in your current working directory. Do not edit source files.
Do not use the network, other repository copies, benchmark files, git history, saved answers,
memory, skills, or delegated agents. Use local repository evidence to solve this task.
Return ONLY one JSON object with keys sites (array of strings), complete (boolean),
and unresolved (array of strings). Each site must be <repo-relative-path>:<FunctionOrMethodName>.
''' + task_wording + ''' Deduplicate the same path and method. Do not include types or fields
instead of methods. Claim complete only if justified.

ISSUE:
''' + task.prompt
    if has_prism:
        prompt += '''\nTOOLS: Native file reads and text searches remain available. Prism MCP is also available.
Start discovery with prism_search or prism_query. For signature-change impact, use
prism_change_impact; retain all affected sites it reports. Use prism_lookup for a whole
named method, prism_read for files, and batch prism_search terms with context when useful.
Treat warnings and unresolved edges as coverage gaps, not proof of completeness.
'''
    else:
        prompt += '\nTOOLS: Use native file reads and text searches (rg/grep/find and shell) to investigate.\n'
    if arm.startswith('sonnet'):
        settings = dict(claudeMdExcludes=['/**'], autoMemoryEnabled=False,
                        disableAllHooks=True, enabledPlugins={})
        cmd = [shutil.which('claude'), '-p', prompt, '--model', 'claude-sonnet-5',
               '--effort', 'medium', '--output-format', 'stream-json', '--verbose',
               '--max-budget-usd', '1', '--restricted', '--permission-mode', 'dontAsk',
               '--permission-prompts', 'none', '--strict-mcp-config', '--mcp-config', str(out/'mcp.json'),
               '--settings', json.dumps(settings), '--setting-sources', '',
               '--disable-slash-commands', '--no-chrome', '--no-session-persistence',
               '--tools', 'Read,Grep,Glob,Bash', '--allowedTools', 'Read,Grep,Glob,Bash,mcp__prism']
    else:
        cmd = [shutil.which('codex'), 'exec', '--ignore-user-config', '--ephemeral',
               '-s', 'workspace-write', '-C', str(work), '--json', '--skip-git-repo-check',
               '-m', 'gpt-5.5', '--output-schema', str(root/'answer-schema.json'), '-o', str(out/'final.txt')]
        cfg = ['approval_policy="never"', 'model_reasoning_effort="medium"',
               'project_doc_max_bytes=0', 'web_search="disabled"', 'features.multi_agent=false',
               'features.memories=false', 'features.hooks=false', 'features.apps=false',
               'skills.max_context_tokens=1']
        if has_prism:
            cfg += ['mcp_servers.prism.command='+json.dumps(str(binary)),
                    'mcp_servers.prism.args='+json.dumps(['mcp', str(work)]),
                    'mcp_servers.prism.required=true']
            cfg += [f'mcp_servers.prism.tools.{name}.approval_mode="approve"' for name in TOOLS]
        for setting in cfg:
            cmd += ['-c', setting]
        cmd += [prompt]
    dump(out / 'command.json', cmd)
    (out / 'prompt.txt').write_text(prompt)
    return dict(key=key, out=out, work=work, cmd=cmd, pristine=pristine, trial=trial, arm=arm, task=task.id)


def run_cell(cell):
    out, work = cell['out'], cell['work']
    env = os.environ.copy()
    env.pop('CLAUDECODE', None)
    env['PATH'] = ':'.join([str(Path(shutil.which('rg')).parent), '/opt/homebrew/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'])
    started = time.time()
    start = time.monotonic()
    print('START ' + cell['key'], flush=True)
    timed_out, setup_abort = False, False
    with (out/'stdout.jsonl').open('w') as stdout, (out/'stderr.txt').open('w') as stderr:
        proc = subprocess.Popen(cell['cmd'], cwd=work, env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while proc.poll() is None:
                if time.monotonic()-start > LIMIT_S:
                    timed_out = True
                    stop(proc)
                    break
                text = (out/'stdout.jsonl').read_text(errors='replace')
                # Transport/approval failures are setup failures; argument errors are not.
                if cell['arm'].endswith('_prism') and any(s in text for s in [
                        'MCP tool call requires approval', 'MCP startup failed',
                        'failed to initialize MCP server']):
                    setup_abort = True
                    stop(proc)
                    break
                time.sleep(1)
        finally:
            stop(proc)
    rec = bench.summarize(out, cell['arm'], time.monotonic()-start, proc.returncode, timed_out)
    audit_usage(rec, bench.events(out/'stdout.jsonl'), cell['arm'])
    changed = [p for p,h in cell['pristine'].items() if not (work/p).exists() or bench.sha(work/p)!=h]
    rec.update(cell_id=cell['key'], trial=cell['trial'], task=cell['task'], started_at=started,
               source_changed=changed, setup_abort=setup_abort)
    rec['score']['trial'] = cell['trial']
    rec['audited_valid'] = bool(proc.returncode==0 and not timed_out and not setup_abort
                               and rec.get('measurement_complete') and not rec.get('agent_error')
                               and not rec['violations'] and not changed)
    dump(out/'audit.json', rec)
    print('DONE ' + json.dumps({k:rec.get(k) for k in ['cell_id','wall_s','audited_valid','audited_total_tokens','cost_usd','tool_calls']})
          + f" recall={rec['score']['recall']} precision={rec['score']['precision']}", flush=True)
    return rec


def main():
    root = Path(tempfile.mkdtemp(prefix='prism-panel-', dir='/private/tmp'))
    print('RUN_DIR=' + str(root), flush=True)
    dump(HERE/'active-run.json', dict(root=str(root), status='preflight'))
    binary = root/'prism-candidate'
    shutil.copy2(SOURCE_BINARY, binary)
    assert bench.sha(binary)==EXPECTED_BINARY
    assert bench.command(['git','diff','HEAD','--','internal'], bench.PRISM_REPO)==(HERE.parent/'four-way-2026-09-06/prism-working-tree.patch').read_bytes()
    shutil.copy2(HERE.parent/'four-way-2026-09-06/answer-schema.json', root/'answer-schema.json')
    prepared = {}
    task_manifests = []
    for name in TASK_IDS:
        path = bench.HARNESS/'tasks'/f'{name}.json'
        task = bench.Task.load(path)
        corpus = task.workdir or task.repo
        pin = bench.command(['git','-C',corpus,'rev-parse',f'{task.pin}^{{commit}}']).decode().strip()
        archive = bench.command(['git','-C',corpus,'archive',pin])
        pristine = {}
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            for m in tf:
                p = Path(m.name)
                if p.name in ['AGENTS.md','CLAUDE.md','.mcp.json'] or any(x in p.parts for x in ['.codex','.claude']):
                    raise RuntimeError('Unexpected archived agent customization: '+m.name)
                if m.isfile():
                    pristine[m.name] = hashlib.sha256(tf.extractfile(m).read()).hexdigest()
        dump(root/f'{name}.task.json',json.loads(path.read_text()))
        task_manifests.append(dict(task=name,pin=pin,task_sha256=bench.sha(path),
                                   archive_sha256=hashlib.sha256(archive).hexdigest(),files=len(pristine)))
        prepared[name] = (task,archive,pristine)
    waves = [(name,1,list(bench.ARMS)) for name in TASK_IDS]
    waves += [(name,2,list(reversed(bench.ARMS))) for name in reversed(TASK_IDS)]
    manifest = dict(run_id=root.name,tasks=task_manifests,waves=waves,planned_cells=24,
                    binary_sha256=EXPECTED_BINARY,runner_sha256=bench.sha(Path(__file__)),
                    helper_sha256=bench.sha(HELPER),
                    harness_sha256={n:bench.sha(bench.HARNESS/n) for n in ['schema.py','score.py','usage_account.py']},
                    timeout_s=LIMIT_S,claude_cell_cap_usd=1,launch_budget_usd=LAUNCH_BUDGET,
                    wave_reserve_usd=WAVE_RESERVE,codex_hard_dollar_cap=None,
                    budget_policy='Stop before a wave if known spend + $4 reserve exceeds $15; in-flight Codex costs not hard capped. Stop on unknown usage.',
                    effort='medium',concurrency=4,retries=0,started_at=time.time(),
                    claude_version=bench.command(['claude','--version']).decode().strip(),
                    codex_version=bench.command(['codex','--version']).decode().strip())
    dump(root/'manifest.json', manifest)
    preflight(binary, root)
    print('PREFLIGHT PASS; all corpora and candidate hashes frozen', flush=True)
    if '--preflight-only' in sys.argv:
        dump(HERE/'active-run.json',dict(root=str(root),status='preflight_only'))
        return
    rows, spent, status = [], 0.0, 'running'
    for name,trial,arms in waves:
        if spent+WAVE_RESERVE > LAUNCH_BUDGET:
            status='budget_incomplete'
            break
        task, archive, pristine = prepared[name]
        bench.TASK = task
        cells = [prepare_cell(root,binary,task,archive,trial,arm,pristine) for arm in arms]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for rec in pool.map(run_cell, cells):
                rows.append(rec)
                dump(root/'summary.json',dict(status='running',rows=rows,planned_cells=24))
        costs = [r.get('cost_usd') for r in rows]
        if any(type(c) not in (int,float) or not math.isfinite(c) or c<0 for c in costs):
            status='measurement_incomplete'
            spent=None
            break
        spent=sum(costs)
        dump(root/'summary.json',dict(status='running',estimated_spend_usd=spent,rows=rows,planned_cells=24))
        print(f'WAVE DONE: {len(rows)}/24; estimated spend ${spent:.4f}',flush=True)
        if any(r['setup_abort'] for r in rows):
            status='setup_failure'
            break
    if status=='running':
        status='complete' if len(rows)==24 and all(r['audited_valid'] for r in rows) else 'audit_incomplete'
    dump(root/'summary.json',dict(status=status,estimated_spend_usd=spent,rows=rows,planned_cells=24))
    dump(HERE/'active-run.json',dict(root=str(root),status=status,estimated_spend_usd=spent))
    print(f'FINISHED {status}: {root}',flush=True)


if __name__=='__main__':
    main()
