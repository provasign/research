"""Eight new paid cells using the previous panel's unmodified execution helpers."""
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

from analyze import analyze, diagnostics, known

HERE = Path(__file__).resolve().parent
PANEL = HERE.parents[1]/'panel-2026-09-06'
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location('frozen_panel', PANEL/'run_panel.py')
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
bench = panel.bench
BINARIES = dict(before=Path('/private/tmp/prism-panel-b4i4a554/prism-candidate'),
                after=Path('/private/tmp/prism-evidence-delivery-candidate'))
HASHES = dict(before='63f5166f6adf40f768a9cf32701a13344abcf29c51064cc9fe372dbb210a7e7d',
              after='b8819ec951c78823c0df87b9ac39a9916302322c4799760e772efd125e4c39d0')
WAVES = [('gin-4645',1,['before','after']), ('django-connparams',1,['before','after']),
         ('django-connparams',2,['after','before']), ('gin-4645',2,['after','before'])]
BUDGET, RESERVE = 3.0, .75


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(tempfile.mkdtemp(prefix='prism-delivery-ab-', dir='/private/tmp'))
    print('RUN_DIR='+str(root), flush=True)
    dump(HERE/'active-run.json', dict(root=str(root), status='preflight'))
    previous = json.loads((PANEL/'manifest.json').read_text())
    source = json.loads((HERE.parent/'validation.json').read_text())
    for name, digest in source['source_sha256'].items():
        assert sha(REPO/name) == digest, 'Source drift: '+name
    assert sha(PANEL/'run_panel.py') == previous['runner_sha256']
    assert sha(panel.HELPER) == previous['helper_sha256']
    for name, digest in previous['harness_sha256'].items():
        assert sha(bench.HARNESS/name) == digest, 'Harness drift: '+name
    version = bench.command(['codex','--version']).decode().strip()
    assert version == previous['codex_version'], version
    roots, binaries = {}, {}
    for variant, directory in [('before','a'), ('after','b')]:
        base = root/directory
        base.mkdir()
        roots[variant] = base
        assert sha(BINARIES[variant]) == HASHES[variant], variant
        binary = base/'prism-candidate'
        shutil.copy2(BINARIES[variant], binary)
        binaries[variant] = binary
        shutil.copy2(PANEL/'answer-schema.json', base/'answer-schema.json')
        panel.preflight(binary, base)
    prepared, task_manifest = {}, []
    for task_id in ['gin-4645','django-connparams']:
        path = PANEL/(task_id+'.task.json')
        task = bench.Task.load(path)
        entry = next(e for e in previous['tasks'] if e['task']==task_id)
        assert json.loads(path.read_text()) == json.loads((PANEL/'harness-snapshot/tasks'/(task_id+'.json')).read_text())
        assert sha(PANEL/'harness-snapshot/tasks'/(task_id+'.json')) == entry['task_sha256']
        archive = bench.command(['git','-C',task.workdir or task.repo,'archive',task.pin])
        assert hashlib.sha256(archive).hexdigest() == entry['archive_sha256'], task_id
        pristine = {}
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            for member in tf:
                p = Path(member.name)
                assert p.name not in ['AGENTS.md','CLAUDE.md','.mcp.json'] and not any(x in p.parts for x in ['.codex','.claude']), member.name
                if member.isfile():
                    pristine[member.name] = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
        prepared[task_id] = task, archive, pristine
        task_manifest.append(entry)
        shutil.copy2(path, root/(task_id+'.task.json'))
    shutil.copy2(HERE/'PROTOCOL.md', root/'PROTOCOL.md')
    manifest = dict(run_id=root.name, started_at=time.time(), binaries=HASHES,
        variant_directories={'before':'a','after':'b'}, model='gpt-5.5', effort='medium',
        codex_version=version, waves=WAVES, concurrency=2, planned_cells=8, retries=0,
        launch_budget_usd=BUDGET, pair_reserve_usd=RESERVE, hard_billing_cap=None,
        timeout_s=panel.LIMIT_S, tasks=task_manifest,
        source_sha256=source['source_sha256'], harness_sha256=previous['harness_sha256'],
        helper_sha256=previous['helper_sha256'], panel_runner_sha256=previous['runner_sha256'],
        local_sha256={name:sha(HERE/name) for name in ['run_comparison.py','analyze.py','PROTOCOL.md','test_comparison.py']})
    dump(root/'manifest.json', manifest)
    print('PREFLIGHT PASS; binary, source, task, harness, and CLI identities verified', flush=True)
    rows, status = [], 'running'

    def save():
        result = analyze(rows)
        dump(root/'summary.json', dict(status=status, rows=rows, planned_cells=8,
                                       estimated_spend_usd=result['estimated_spend_usd']))
        dump(root/'analysis.json', result)
        dump(HERE/'active-run.json', dict(root=str(root), status=status,
             observed_cells=len(rows), estimated_spend_usd=result['estimated_spend_usd']))
        return result

    for task_id, trial, variants in WAVES:
        result = save()
        spent = result['estimated_spend_usd']
        if spent is None or spent+RESERVE > BUDGET:
            status = 'measurement_incomplete' if spent is None else 'budget_incomplete'
            break
        task, archive, pristine = prepared[task_id]
        bench.TASK = task
        cells = {}
        for variant in variants:
            print(f'PREPARE {task_id}.r{trial}.{variant}', flush=True)
            cells[variant] = panel.prepare_cell(roots[variant], binaries[variant], task,
                                                archive, trial, 'codex_prism', pristine)
        assert (cells['before']['out']/'prompt.txt').read_bytes() == (cells['after']['out']/'prompt.txt').read_bytes()
        def run(variant):
            print(f'START VARIANT {task_id}.r{trial}.{variant}', flush=True)
            rec = panel.run_cell(cells[variant])
            row = dict(rec, variant=variant, comparison_id=f'{task_id}.r{trial}.{variant}',
                       evidence_path=str(cells[variant]['out'].relative_to(root)),
                       diagnostics=diagnostics(rec['calls']))
            dump(cells[variant]['out']/'comparison.json', row)
            return row
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for row in pool.map(run, variants):
                rows.append(row)
                save()
                print('MEASURED '+json.dumps({k:row[k] for k in ['comparison_id','audited_valid','audited_total_tokens','cost_usd','diagnostics']}), flush=True)
        if any(r['setup_abort'] for r in rows):
            status = 'setup_failure'
            break
        if any(not known(r.get('cost_usd')) for r in rows):
            status = 'measurement_incomplete'
            break
    if status=='running':
        status = 'complete' if len(rows)==8 and all(r['audited_valid'] for r in rows) else 'audit_incomplete'
    result = save()
    print('FINISHED '+json.dumps({k:v for k,v in result.items() if k!='pairs'}), flush=True)


if __name__=='__main__':
    main()
