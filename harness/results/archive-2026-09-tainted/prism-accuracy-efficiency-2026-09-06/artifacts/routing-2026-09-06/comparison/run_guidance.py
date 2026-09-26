"""Prepare without models, then execute one immutable eight-cell guidance study."""
import argparse
import concurrent.futures
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
EVIDENCE = HERE.parents[1]
REPO = EVIDENCE.parents[1]
PANEL = EVIDENCE / 'panel-2026-09-06'
PRIOR = EVIDENCE / 'evidence-delivery-2026-09-06/comparison'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


panel = module('guidance_frozen_panel', PANEL / 'run_panel.py')
analysis = module('guidance_frozen_analysis', PRIOR / 'analyze.py')
bench = panel.bench
BINARY = Path('/private/tmp/prism-routing-candidate')
BINARY_HASH = '969239d7bb991c3feb64e48d952cc1ff17d1a449a5d58df588e0a005b28440a2'
DIRECTORIES = {'before': 'a', 'after': 'b'}
WAVES = [('gin-4645', 1, ['before', 'after']), ('django-connparams', 1, ['before', 'after']),
         ('django-connparams', 2, ['after', 'before']), ('gin-4645', 2, ['after', 'before'])]
BUDGET, RESERVE = 3.0, .75
OLD_GUIDANCE = '''\nTOOLS: Native file reads and text searches remain available. Prism MCP is also available.
Start discovery with prism_search or prism_query. For signature-change impact, use
prism_change_impact; retain all affected sites it reports. Use prism_lookup for a whole
named method, prism_read for files, and batch prism_search terms with context when useful.
Treat warnings and unresolved edges as coverage gaps, not proof of completeness.
'''
NEW_GUIDANCE = '''\nTOOLS: Native file reads and text searches remain available. Prism MCP is also available.
Choose the first discovery tool by the evidence needed: for a known affected-site or
signature-change target, call prism_change_impact directly; for known method bodies,
call prism_lookup with name=[...] to read related methods together. Use prism_search
or prism_query when the location is unknown, not just to locate a target already named.
Retain all affected sites reported by impact. Reuse delivered signatures and call
expressions; follow up only for needed bodies, omitted evidence, ambiguous receivers,
stale/incomplete scope, or non-code references required by the task. Do not rescan merely
to reproduce the site list. Use prism_read for files and batch search terms with context.
Treat warnings and unresolved edges as coverage gaps, not proof of completeness.
Report remaining evidence gaps instead of claiming completeness.
'''


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_for(original, variant):
    assert variant in DIRECTORIES
    assert original.endswith(OLD_GUIDANCE), 'Frozen helper guidance changed'
    prefix = original[:-len(OLD_GUIDANCE)]
    assert '\nTOOLS:' not in prefix, 'Duplicate routing instructions'
    return prefix + (OLD_GUIDANCE if variant == 'before' else NEW_GUIDANCE)


def assert_pair(before, after, roots):
    prompts = [cell['cmd'][-1] for cell in [before, after]]
    assert prompt_for(prompts[0], 'after') == prompts[1], 'Difference outside guidance'
    normalized = [[s.replace(str(roots[v]), '<ARM>') for s in cell['cmd'][:-1]]
                  for v, cell in [('before', before), ('after', after)]]
    assert normalized[0] == normalized[1], 'CLI configuration differs between arms'
    for cell in [before, after]:
        assert json.loads((cell['out'] / 'command.json').read_text()) == cell['cmd']
        assert (cell['out'] / 'prompt.txt').read_text() == cell['cmd'][-1]


def stop_reason(rows):
    if any(row.get('setup_abort') for row in rows):
        return 'setup_failure'
    spend = analysis.analyze(rows)['estimated_spend_usd']
    if spend is None:
        return 'measurement_incomplete'
    if spend + RESERVE > BUDGET:
        return 'budget_incomplete'
    return None


def readout(rows, unmeasured):
    result = analysis.analyze(rows)
    if unmeasured:
        result.update(complete=False, decision='inconclusive', estimated_spend_usd=None,
                      unmeasured_attempts=unmeasured)
    return result


def verify_identities(root, manifest):
    assert sha(root / 'prism-candidate') == BINARY_HASH
    assert bench.command(['codex', '--version']).decode().strip() == manifest['codex_version']
    for name, digest in manifest['source_sha256'].items():
        assert sha(REPO / name) == digest, 'Source changed: ' + name
    for name, digest in manifest['local_sha256'].items():
        assert sha(HERE / name) == digest, 'Experiment changed: ' + name
    for name, digest in manifest['frozen_sha256'].items():
        assert sha(EVIDENCE / name) == digest, 'Frozen helper changed: ' + name
    for name, digest in manifest['harness_sha256'].items():
        assert sha(bench.HARNESS / name) == digest, 'Harness changed: ' + name
    for name, digest in manifest['prepared_sha256'].items():
        assert sha(root / name) == digest, 'Prepared input changed: ' + name


def prepare():
    previous = json.loads((PANEL / 'manifest.json').read_text())
    source = json.loads((HERE.parent / 'free-replay/results.json').read_text())
    assert sha(BINARY) == BINARY_HASH == source['binary_sha256']
    assert sha(PANEL / 'run_panel.py') == previous['runner_sha256']
    assert sha(panel.HELPER) == previous['helper_sha256']
    root = Path(tempfile.mkdtemp(prefix='prism-routing-ab-', dir='/private/tmp'))
    print('RUN_DIR=' + str(root), flush=True)
    binary = root / 'prism-candidate'
    shutil.copy2(BINARY, binary)
    roots = {v: root / d for v, d in DIRECTORIES.items()}
    for base in roots.values():
        base.mkdir()
        shutil.copy2(PANEL / 'answer-schema.json', base / 'answer-schema.json')
        panel.preflight(binary, base)
    tasks, prepared = [], {}
    for task_id in analysis.TASKS:
        path = PANEL / (task_id + '.task.json')
        task = bench.Task.load(path)
        entry = next(t for t in previous['tasks'] if t['task'] == task_id)
        assert json.loads(path.read_text()) == json.loads((PANEL / 'harness-snapshot/tasks' / (task_id + '.json')).read_text())
        assert sha(PANEL / 'harness-snapshot/tasks' / (task_id + '.json')) == entry['task_sha256']
        archive = bench.command(['git', '-C', task.workdir or task.repo, 'archive', task.pin])
        assert hashlib.sha256(archive).hexdigest() == entry['archive_sha256']
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            pristine = {}
            for member in tf:
                p = Path(member.name)
                assert p.name not in ['AGENTS.md', 'CLAUDE.md', '.mcp.json']
                assert not any(part in p.parts for part in ['.codex', '.claude', '.git'])
                if member.isfile():
                    pristine[member.name] = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
        prepared[task_id] = (task, archive, pristine)
        tasks.append(entry)
        shutil.copy2(path, root / path.name)
    cells = {}
    for task_id, trial, variants in WAVES:
        task, archive, pristine = prepared[task_id]
        pair = {}
        for variant in variants:
            cell = panel.prepare_cell(roots[variant], binary, task, archive, trial, 'codex_prism', pristine)
            cell['cmd'][-1] = prompt_for(cell['cmd'][-1], variant)
            dump(cell['out'] / 'command.json', cell['cmd'])
            (cell['out'] / 'prompt.txt').write_text(cell['cmd'][-1])
            # Archive snapshots have no history, not merely an unadvertised checkout.
            history = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=cell['work'], capture_output=True)
            assert history.returncode != 0
            assert all(sha(cell['work'] / p) == digest for p, digest in pristine.items())
            pair[variant] = cell
            identity = f'{task_id}.r{trial}.{variant}'
            cells[identity] = dict(cell, out=str(cell['out']), work=str(cell['work']))
        assert_pair(pair['before'], pair['after'], roots)
    dump(root / 'cells.json', cells)
    shutil.copy2(HERE / 'PROTOCOL.md', root / 'PROTOCOL.md')
    frozen = [PANEL / 'run_panel.py', panel.HELPER, PRIOR / 'analyze.py',
              PANEL / 'answer-schema.json', HERE.parent / 'NEXT_TEST.md']
    manifest = dict(run_id=root.name, created_at=time.time(), binary_sha256=BINARY_HASH,
        treatment='routing paragraph only; both arms use the same candidate binary',
        model='gpt-5.5', effort='medium', codex_version=previous['codex_version'],
        variant_directories=DIRECTORIES, tasks=tasks, planned_cells=8, waves=WAVES, retries=0,
        launch_budget_usd=BUDGET, pair_reserve_usd=RESERVE, hard_billing_cap=None,
        concurrency=2, timeout_s=panel.LIMIT_S, source_sha256=source['source_sha256'],
        harness_sha256=previous['harness_sha256'],
        frozen_sha256={str(p.relative_to(EVIDENCE)): sha(p) for p in frozen},
        local_sha256={name: sha(HERE / name) for name in ['run_guidance.py', 'test_guidance.py', 'PROTOCOL.md', 'archive.py']},
        prepared_sha256={str(p.relative_to(root)): sha(p) for p in root.rglob('*')
                         if p.is_file() and 'work' not in p.relative_to(root).parts})
    dump(root / 'manifest.json', manifest)
    verify_identities(root, manifest)
    dump(root / 'summary.json', dict(status='prepared', rows=[], planned_cells=8, estimated_spend_usd=0))
    dump(root / 'dry-run.json', dict(pass_all=True, prepared_cells=8, model_runs=0,
         same_binary=True, only_guidance_differs=True, history_absent=True, pristine_sources=True,
         mcp_preflight_arms=2, fresh_usage_ledger=True))
    dump(HERE / 'active-run.json', dict(root=str(root), status='prepared'))
    print('DRY RUN PASS: 8 cells prepared; 0 model runs', flush=True)


def run(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    assert json.loads((root / 'summary.json').read_text())['status'] == 'prepared', 'Run cannot be resumed or reused'
    assert json.loads((root / 'dry-run.json').read_text())['pass_all']
    verify_identities(root, manifest)
    cells = json.loads((root / 'cells.json').read_text())
    rows, unmeasured, status = [], [], 'running'

    def save():
        result = readout(rows, unmeasured)
        dump(root / 'summary.json', dict(status=status, rows=rows, planned_cells=8,
             unmeasured_attempts=unmeasured, estimated_spend_usd=result['estimated_spend_usd']))
        dump(root / 'analysis.json', result)
        dump(HERE / 'active-run.json', dict(root=str(root), status=status, observed_cells=len(rows),
             estimated_spend_usd=result['estimated_spend_usd']))
        return result

    save()
    try:
        for task_id, trial, variants in WAVES:
            reason = stop_reason(rows)
            if reason:
                status = reason
                break
            verify_identities(root, manifest)
            bench.TASK = bench.Task.load(root / (task_id + '.task.json'))

            def execute(variant):
                identity = f'{task_id}.r{trial}.{variant}'
                cell = dict(cells[identity])
                cell['out'], cell['work'] = Path(cell['out']), Path(cell['work'])
                assert all(sha(cell['work'] / p) == digest for p, digest in cell['pristine'].items())
                print('START VARIANT ' + identity, flush=True)
                rec = panel.run_cell(cell)
                row = dict(rec, variant=variant, comparison_id=identity,
                           evidence_path=str(cell['out'].relative_to(root)),
                           diagnostics=analysis.diagnostics(rec['calls']))
                dump(cell['out'] / 'comparison.json', row)
                return row

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = {pool.submit(execute, variant): variant for variant in variants}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        row = future.result()
                    except Exception as exc:
                        unmeasured.append(dict(comparison_id=f'{task_id}.r{trial}.{futures[future]}',
                                               error=repr(exc), cost_usd=None))
                        save()
                        continue
                    rows.append(row)
                    save()
                    print('MEASURED ' + json.dumps({k: row[k] for k in ['comparison_id', 'audited_valid', 'audited_total_tokens', 'cost_usd', 'score', 'diagnostics']}), flush=True)
            if unmeasured:
                status = 'harness_error'
                break
        if status == 'running':
            status = 'complete' if len(rows) == 8 and all(r['audited_valid'] for r in rows) else 'audit_incomplete'
    except BaseException:
        status = 'harness_error'
        save()
        raise
    result = save()
    print('FINISHED ' + json.dumps({k: v for k, v in result.items() if k != 'pairs'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--run', type=Path)
    args = parser.parse_args()
    prepare() if args.prepare else run(args.run.resolve())
