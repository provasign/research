"""Infrastructure-only replacement for the denied MCP attempt; retains its spend."""
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time

spec = importlib.util.spec_from_file_location('fourway', '/private/tmp/prism-four-way.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
root = Path('/private/tmp/prism-four-way-3k0qvcsa')
old = root / 'evidence/codex_prism'
out = root / 'evidence/codex_prism_retry'
out.mkdir()
work = root / 'work/codex_prism_retry'
work.mkdir()
archive = bench.command(['git','-C',bench.TASK.repo,'archive',bench.TASK.pin])
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
    tf.extractall(work, filter='data')
bench.command(['git','init','-q'], work)
binary = root / 'prism-candidate'
start = time.monotonic()
indexed = subprocess.run([str(binary),'index',str(work)],cwd=work,capture_output=True,text=True,timeout=180,check=True)
(out/'index.stdout.txt').write_text(indexed.stdout)
(out/'index.stderr.txt').write_text(indexed.stderr)
bench.dump(out/'index.json',dict(wall_s=time.monotonic()-start))
cmd = json.loads((old/'command.json').read_text())
cmd[cmd.index('-C')+1] = str(work)
cmd[cmd.index('-o')+1] = str(out/'final.txt')
for i, value in enumerate(cmd):
    if value.startswith('mcp_servers.prism.args='):
        cmd[i] = 'mcp_servers.prism.args=' + json.dumps(['mcp',str(work)])
prompt = cmd.pop()
for name in ['prism_search','prism_query','prism_read','prism_lookup','prism_change_impact','prism_verify']:
    cmd += ['-c',f'mcp_servers.prism.tools.{name}.approval_mode="approve"']
cmd += [prompt]
bench.dump(out/'command.json',cmd)
(out/'prompt.txt').write_text(prompt)
bench.dump(out/'attempt.json',dict(reason='MCP approval denied in initial Codex Prism attempt; no successful Prism response',
            replaces='codex_prism',keep_initial_spend=True,quality_retry=False,
            binary_sha256=bench.sha(binary),runner_sha256=bench.sha(Path(__file__))))
files = {str(p.relative_to(work)):bench.sha(p) for p in work.rglob('*') if p.is_file() and '.git' not in p.parts}
env = os.environ.copy()
env.pop('CLAUDECODE',None)
env['PATH'] = ':'.join([str(Path(bench.shutil.which('rg')).parent),'/opt/homebrew/bin','/usr/bin','/bin','/usr/sbin','/sbin'])
start = time.monotonic()
timed_out = False
print('START codex_prism_retry',flush=True)
with (out/'stdout.jsonl').open('w') as stdout, (out/'stderr.txt').open('w') as stderr:
    p = subprocess.Popen(cmd,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
    try:
        p.wait(timeout=bench.LIMIT_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(p.pid,signal.SIGTERM)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL)
            p.wait()
rec = bench.summarize(out,'codex_prism_retry',time.monotonic()-start,p.returncode,timed_out)
rec['source_changed'] = [f for f,h in files.items() if not (work/f).exists() or bench.sha(work/f)!=h]
rec['prism_successful_calls'] = sum(c.get('type')=='mcp_tool_call' and c.get('server')=='prism'
                                   and c.get('status')=='completed' and not c.get('error') for c in rec['calls'])
rec['valid'] = rec['valid'] and not rec['source_changed'] and rec['prism_successful_calls']>0
bench.dump(out/'measurement.json',rec)
print(json.dumps({k:rec.get(k) for k in ['arm','valid','wall_s','total_tokens','cost_usd','tool_calls','prism_successful_calls','score']}),flush=True)
