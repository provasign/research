"""One fixed task, four independent cells, no selective retries."""
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

HARNESS = Path('/Users/tapabratapal/Projects/provasign/research/harness')
PRISM_REPO = Path('/Users/tapabratapal/Projects/provasign/prism')
sys.path.insert(0, str(HARNESS))
from schema import Task, Answer
from score import score, SCORER_VERSION
from usage_account import cli_usage

TASK_PATH = HARNESS / 'tasks/jackson-settable-set.json'
TASK = Task.load(TASK_PATH)
LIMIT_S = 600
ARMS = ['sonnet_baseline', 'codex_baseline', 'sonnet_prism', 'codex_prism']


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, check=True).stdout


def events(path):
    result = []
    for line in path.read_text(errors='replace').splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return result


def summarize(out, name, wall, code, timed_out):
    ev = events(out / 'stdout.jsonl')
    rec = dict(arm=name, wall_s=round(wall, 3), exit_code=code,
               timed_out=timed_out, task=TASK.id, scorer_version=SCORER_VERSION)
    calls = []
    final = ''
    if name.startswith('sonnet'):
        finals = [e for e in ev if e.get('type') == 'result']
        init = [e for e in ev if e.get('type') == 'system' and e.get('subtype') == 'init']
        rec['init'] = init[-1] if init else None
        if finals:
            j = finals[-1]
            dump(out / 'result.raw.json', j)
            usage = cli_usage(j)
            rec['usage'] = usage
            rec['model'] = list((j.get('modelUsage') or {}).keys())
            rec['input_tokens'] = usage['input_total']
            rec['output_tokens'] = usage['tokens']['output']
            rec['cost_usd'] = usage['cost_usd_cli']
            rec['cost_basis'] = 'Claude CLI estimate (not invoice)'
            rec['measurement_complete'] = usage['usage_complete']
            rec['agent_error'] = j.get('is_error', False)
            final = j.get('result', '')
        else:
            rec['measurement_complete'] = False
        seen = set()
        for e in ev:
            if e.get('type') != 'assistant':
                continue
            for c in (e.get('message') or {}).get('content', []):
                if c.get('type') == 'tool_use' and c.get('id') not in seen:
                    seen.add(c.get('id'))
                    calls.append(c)
    else:
        rec['model'] = 'gpt-5.5'
        turns = [e for e in ev if e.get('type') == 'turn.completed']
        valid = bool(turns) and all(all(type(e.get('usage', {}).get(k)) is int
                    and e['usage'][k] >= 0 for k in
                    ['input_tokens', 'cached_input_tokens', 'output_tokens']) for e in turns)
        rec['usage_raw'] = [e.get('usage') for e in turns]
        rec['measurement_complete'] = valid
        if valid:
            u = {k: sum(e['usage'][k] for e in turns) for k in
                 ['input_tokens', 'cached_input_tokens', 'output_tokens']}
            rec['input_tokens'] = u['input_tokens']
            rec['output_tokens'] = u['output_tokens']
            rec['cache_read_tokens'] = u['cached_input_tokens']
            if u['cached_input_tokens'] > u['input_tokens']:
                rec['measurement_complete'] = False
            else:
                rec['cost_usd'] = ((u['input_tokens'] - u['cached_input_tokens']) * 5
                                   + u['cached_input_tokens'] * 0.5
                                   + u['output_tokens'] * 30) / 1_000_000
            rec['cost_basis'] = 'API-equivalent estimate: GPT-5.5 $5/$0.50/$30 per M input/cached/output; not subscription billing'
        for e in ev:
            item = e.get('item') or {}
            if e.get('type') == 'item.completed':
                if item.get('type') in ['command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call', 'file_change']:
                    calls.append(item)
                elif item.get('type') == 'agent_message':
                    final = item.get('text', final)
        if (out / 'final.txt').exists():
            final = (out / 'final.txt').read_text()
        rec['agent_error'] = any(e.get('type') in ['turn.failed', 'error'] for e in ev)
    (out / 'final.txt').write_text(final)
    rec['tool_calls'] = len(calls)
    rec['prism_calls'] = sum(1 for c in calls if 'prism' in str(c.get('name', '')).lower()
                              or c.get('server') == 'prism')
    rec['calls'] = calls
    if rec.get('input_tokens') is not None and rec.get('output_tokens') is not None:
        rec['total_tokens'] = rec['input_tokens'] + rec['output_tokens']
    answer = Answer.parse(final)
    rec['answer'] = dict(sites=[str(s) for s in answer.sites], complete=answer.complete,
                         unresolved=answer.unresolved)
    rec['score'] = score(TASK, answer, name, 1).to_dict()
    rec['valid'] = (code == 0 and not timed_out and rec.get('measurement_complete')
                    and not rec.get('agent_error') and bool(answer.sites))
    dump(out / 'measurement.json', rec)
    return rec


def main():
    root = Path(tempfile.mkdtemp(prefix='prism-four-way-', dir='/private/tmp'))
    print('RUN_DIR=' + str(root), flush=True)
    binary = root / 'prism-candidate'
    shutil.copy2('/private/tmp/prism-improvement.s40slA/prism-candidate', binary)
    archive = command(['git', '-C', TASK.repo, 'archive', TASK.pin])
    schema = dict(type='object', properties={
        'sites': dict(type='array', items=dict(type='string')),
        'complete': dict(type='boolean'),
        'unresolved': dict(type='array', items=dict(type='string'))},
        required=['sites', 'complete', 'unresolved'], additionalProperties=False)
    dump(root / 'answer-schema.json', schema)
    manifest = dict(task=TASK.id, task_sha256=sha(TASK_PATH), corpus_pin=TASK.pin,
                    archive_sha256=hashlib.sha256(archive).hexdigest(),
                    prism_head=command(['git', 'rev-parse', 'HEAD'], PRISM_REPO).decode().strip(),
                    prism_binary_sha256=sha(binary), runner_sha256=sha(Path(__file__)),
                    harness_hashes={f:sha(HARNESS/f) for f in ['schema.py','score.py','usage_account.py']},
                    timeout_s=LIMIT_S, claude_budget_per_cell_usd=2,
                    codex_cost_limit=None, retries=0, replicates=1,
                    effort='medium', launch_order=ARMS, concurrency=4,
                    claude_version=command(['claude','--version']).decode().strip(),
                    codex_version=command(['codex','--version']).decode().strip(),
                    pricing_source='https://developers.openai.com/api/docs/models/gpt-5.5',
                    started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    (root / 'prism-working-tree.patch').write_bytes(command(['git','diff','HEAD','--','internal'], PRISM_REPO))
    dump(root / 'task.json', json.loads(TASK_PATH.read_text()))
    common = '''Analyze only the repository in your current working directory. Do not edit source files.
Do not use the network, other repository copies, benchmark files, git history, saved answers,
memory, skills, or delegated agents. Use local repository evidence to solve this task.
Return ONLY one JSON object with keys sites (array of strings), complete (boolean),
and unresolved (array of strings). Each site must be <repo-relative-path>:<FunctionOrMethodName>.
Enumerate the containing method of every call, declaration, and override; deduplicate the same
path and method. Do not include types or fields instead of methods. Claim complete only if justified.

ISSUE:
''' + TASK.prompt
    native = '\nTOOLS: Use native file reads and text searches (rg/grep/find and shell) to investigate.\n'
    prism = '''\nTOOLS: Native file reads and text searches remain available. Prism MCP is also available.
Start discovery with prism_search or prism_query. For signature-change impact, use
prism_change_impact; retain all affected sites it reports. Use prism_lookup for a whole
named method, prism_read for files, and batch prism_search terms with context when useful.
Treat warnings and unresolved edges as coverage gaps, not proof of completeness.
'''
    cells = []
    for name in ARMS:
        out = root / 'evidence' / name
        out.mkdir(parents=True)
        work = root / 'work' / name
        work.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            tf.extractall(work, filter='data')
        command(['git','init','-q'], work)
        instruction_paths = [str(p.relative_to(work)) for p in work.rglob('*')
                             if p.name in ['AGENTS.md','CLAUDE.md','.mcp.json'] or '.codex' in p.parts]
        if instruction_paths:
            raise RuntimeError('Unexpected corpus steering files: ' + repr(instruction_paths))
        has_prism = name.endswith('_prism')
        mcp = {'mcpServers': {}}
        if has_prism:
            start = time.monotonic()
            indexed = subprocess.run([str(binary),'index',str(work)], cwd=work, capture_output=True, text=True, timeout=180)
            (out / 'index.stdout.txt').write_text(indexed.stdout)
            (out / 'index.stderr.txt').write_text(indexed.stderr)
            if indexed.returncode:
                raise RuntimeError('Index failed: ' + indexed.stderr[-1000:])
            dump(out / 'index.json', dict(wall_s=time.monotonic()-start))
            mcp['mcpServers']['prism'] = dict(type='stdio', command=str(binary), args=['mcp',str(work)])
        dump(out / 'mcp.json', mcp)
        prompt = common + (prism if has_prism else native)
        (out / 'prompt.txt').write_text(prompt)
        if name.startswith('sonnet'):
            settings = dict(claudeMdExcludes=['/**'], autoMemoryEnabled=False,
                            disableAllHooks=True, enabledPlugins={})
            cmd = [shutil.which('claude'), '-p', prompt, '--model', 'claude-sonnet-5',
                   '--effort', 'medium', '--output-format', 'stream-json', '--verbose',
                   '--max-budget-usd', '2', '--restricted', '--permission-mode', 'dontAsk',
                   '--permission-prompts', 'none', '--strict-mcp-config',
                   '--mcp-config', str(out/'mcp.json'), '--settings', json.dumps(settings),
                   '--setting-sources', '', '--disable-slash-commands', '--no-chrome',
                   '--no-session-persistence', '--tools', 'Read,Grep,Glob,Bash',
                   '--allowedTools', 'Read,Grep,Glob,Bash,mcp__prism']
        else:
            cmd = [shutil.which('codex'), 'exec', '--ignore-user-config', '--ephemeral',
                   '-s', 'workspace-write', '-C', str(work), '--json',
                   '--skip-git-repo-check', '-m', 'gpt-5.5',
                   '--output-schema', str(root/'answer-schema.json'), '-o', str(out/'final.txt')]
            cfg = ['approval_policy="never"', 'model_reasoning_effort="medium"',
                   'project_doc_max_bytes=0', 'web_search="disabled"',
                   'features.multi_agent=false', 'features.memories=false',
                   'features.hooks=false', 'features.apps=false', 'skills.max_context_tokens=1']
            if has_prism:
                cfg += ['mcp_servers.prism.command='+json.dumps(str(binary)),
                        'mcp_servers.prism.args='+json.dumps(['mcp',str(work)]),
                        'mcp_servers.prism.required=true']
            for c in cfg:
                cmd += ['-c', c]
            cmd += [prompt]
        dump(out / 'command.json', cmd)
        files = {str(p.relative_to(work)):sha(p) for p in work.rglob('*')
                 if p.is_file() and '.git' not in p.parts and '.prism' not in p.parts}
        cells.append((name, out, work, cmd, files))
    manifest['corpus_file_count'] = len(cells[0][4])
    dump(root / 'manifest.json', manifest)

    def run(cell):
        name, out, work, cmd, files = cell
        env = os.environ.copy()
        env.pop('CLAUDECODE', None)
        env['PATH'] = ':'.join([str(Path(shutil.which('rg')).parent), '/opt/homebrew/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'])
        start = time.monotonic()
        print('START ' + name, flush=True)
        timed_out = False
        with (out/'stdout.jsonl').open('w') as stdout, (out/'stderr.txt').open('w') as stderr:
            proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                proc.wait(timeout=LIMIT_S)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
        rec = summarize(out, name, time.monotonic()-start, proc.returncode, timed_out)
        rec['source_changed'] = [p for p,h in files.items() if not (work/p).exists() or sha(work/p) != h]
        rec['valid'] = rec['valid'] and not rec['source_changed']
        dump(out / 'measurement.json', rec)
        print('DONE ' + json.dumps({k:rec.get(k) for k in ['arm','wall_s','valid','total_tokens','cost_usd','tool_calls','prism_calls']}) + ' recall=' + str(rec['score']['recall']), flush=True)
        return rec

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(run, cells))
    dump(root / 'summary.json', rows)
    print('FINISHED=' + str(root), flush=True)


if __name__ == '__main__':
    main()
