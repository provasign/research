"""Audit saved cells and package evidence without changing raw measurements."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

source = Path('/private/tmp/prism-four-way-3k0qvcsa')
target = Path('/Users/tapabratapal/Projects/provasign/prism/docs/accuracy-efficiency-candidate/four-way-2026-09-06')
target.mkdir(exist_ok=True)
sys.path.insert(0, '/Users/tapabratapal/Projects/provasign/research/harness')
from schema import Answer, Task
from score import score


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


task = Task.load(source / 'task.json')
rows = []
for directory in sorted((source / 'evidence').iterdir()):
    rec = json.loads((directory / 'measurement.json').read_text())
    ev = [json.loads(line) for line in (directory / 'stdout.jsonl').read_text().splitlines() if line.startswith('{')]
    successful = []
    tool_errors = []
    native_commands = []
    if rec['arm'].startswith('sonnet'):
        names = {c['id']: c['name'] for c in rec['calls']}
        for e in ev:
            for c in (e.get('message') or {}).get('content', []):
                if c.get('type') == 'tool_result':
                    name = names.get(c.get('tool_use_id'), '')
                    if c.get('is_error'):
                        tool_errors.append(dict(name=name, result=c.get('content')))
                    elif name.startswith('mcp__prism__'):
                        successful.append(name)
        native_commands = [c['input'].get('command','') for c in rec['calls'] if c['name']=='Bash']
        model_usage = rec['usage']['model_usage']
        fields = ['inputTokens','cacheCreationInputTokens','cacheReadInputTokens','outputTokens']
        assert all(type(m[k]) is int and m[k]>=0 for m in model_usage.values() for k in fields)
        counts = {k:sum(m[k] for m in model_usage.values()) for k in fields}
        tokens = dict(input_uncached=counts['inputTokens'], cache_creation=counts['cacheCreationInputTokens'],
                      cache_read=counts['cacheReadInputTokens'], output=counts['outputTokens'])
        rec['audited_total_tokens'] = sum(tokens.values())
        rec['audited_tokens'] = tokens
        rec['auxiliary_models'] = [m for m in model_usage if m!='claude-sonnet-5']
        assert not any(c['name'] in ['Agent','Task','WebFetch','WebSearch'] for c in rec['calls'])
        assert not rec['init']['skills'] and not rec['init']['plugins']
        if rec['arm'].endswith('baseline'):
            assert not rec['init']['mcp_servers']
    else:
        for c in rec['calls']:
            if c.get('type')=='mcp_tool_call':
                if c.get('error') or c.get('status')!='completed':
                    tool_errors.append(dict(name=c.get('tool'),error=c.get('error')))
                elif c.get('server')=='prism':
                    successful.append(c['tool'])
        native_commands = [c['command'] for c in rec['calls'] if c['type']=='command_execution']
        rec['audited_total_tokens'] = rec['total_tokens']
        rec['audited_tokens'] = dict(input_uncached=rec['input_tokens']-rec['cache_read_tokens'],
                                     cache_read=rec['cache_read_tokens'],output=rec['output_tokens'],
                                     cache_creation=None)
        assert not any(c['type'] in ['collab_tool_call','web_search','file_change'] for c in rec['calls'])
    if rec['arm'].endswith('baseline'):
        assert not any('prism' in c.lower() for c in native_commands)
    rec['prism_successful_calls'] = successful
    rec['tool_errors'] = tool_errors
    rec['arm_compliance'] = not successful if rec['arm'].endswith('baseline') else bool(successful)
    rec['audited_valid'] = bool(rec['valid'] and rec['arm_compliance'])
    final = (directory / 'final.txt').read_text()
    assert score(task, Answer.parse(final), rec['arm'], 1).to_dict() == rec['score']
    rec['native_commands'] = native_commands
    if rec['arm']=='codex_prism':
        rec['excluded_reason'] = 'No successful Prism response: MCP approval denied; retained as setup-failed attempt with all spend.'
        assert not rec['audited_valid']
    else:
        assert rec['audited_valid']
    rows.append(rec)
    shutil.copytree(directory, target / 'evidence' / directory.name, dirs_exist_ok=True)
    dump(target / 'evidence' / directory.name / 'audit.json', rec)

selected = {r['arm']:r for r in rows if r['audited_valid']}
deltas = {}
for model in ['sonnet','codex']:
    b = selected[model+'_baseline']
    p = selected[model+('_prism' if model=='sonnet' else '_prism_retry')]
    deltas[model] = {k:100*(1-p[k]/b[k]) for k in ['audited_total_tokens','cost_usd','wall_s']}
setup = next(r for r in rows if r['arm']=='codex_prism')
summary = dict(task=task.id, expected_sites=len(task.ground_truth), successful_cells=list(selected),
               deltas_percent_saved=deltas, attempts=len(rows), infrastructure_retries=1,
               setup_attempt_cost_usd=setup['cost_usd'], setup_attempt_tokens=setup['audited_total_tokens'],
               all_attempt_estimated_cost_usd=sum(r['cost_usd'] for r in rows),
               all_attempt_tokens=sum(r['audited_total_tokens'] for r in rows),
               codex_prism_including_setup_cost_usd=setup['cost_usd']+selected['codex_prism_retry']['cost_usd'],
               rows=rows)
dump(target / 'summary.json',summary)
for f in ['manifest.json','task.json','prism-working-tree.patch','answer-schema.json']:
    shutil.copy2(source/f,target/f)
for f in ['prism-four-way.py','prism-four-way-codex-retry.py','prism-four-way-report.py']:
    shutil.copy2(Path('/private/tmp')/f,target/f)
checksums = {str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in target.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
dump(target/'SHA256SUMS.json',checksums)
print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
