"""Binary-only experiment; reuse the frozen execution loop and exact-site scorer."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent / 'prism-accuracy-efficiency-2026-09-06/artifacts'
PANEL = EVIDENCE / 'panel-2026-09-06'
SNAPSHOT = PANEL / 'harness-snapshot'
PRODUCT = Path('/private/tmp/prism-product-clean')
FREE = HERE.parent / 'prism-scoped-lookup-2026-09-06/results/manifest.json'
BINARIES = {'before': Path('/private/tmp/prism-routing-candidate'),
            'after': Path('/private/tmp/prism-scoped-lookup-candidate')}
ORIGINAL_HARNESS = Path('/Users/tapabratapal/Projects/provasign/research/harness')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


# The frozen helper has absolute imports. Verify them before importing, then pin
# subsequent task and scorer access to the archived snapshot without editing it.
PREVIOUS = json.loads((PANEL / 'manifest.json').read_text())
for name, digest in PREVIOUS['harness_sha256'].items():
    assert sha(SNAPSHOT / name) == sha(ORIGINAL_HARNESS / name) == digest
    module(name[:-3], SNAPSHOT / name)
guidance = module('scoped_frozen_guidance', EVIDENCE / 'routing-2026-09-06/comparison/run_guidance.py')
panel, analysis, bench = guidance.panel, guidance.analysis, guidance.bench
bench.HARNESS = SNAPSHOT
guidance.HERE = HERE
guidance.REPO = PRODUCT
dump = guidance.dump
SOURCE = json.loads(FREE.read_text())


def prompt_for(original):
    return guidance.prompt_for(original, 'after')


def assert_pair(before, after, roots):
    assert before['cmd'][-1] == after['cmd'][-1], 'Prompts differ'
    normalized = [[arg.replace(str(roots[variant]), '<ARM>') for arg in cell['cmd']]
                  for variant, cell in [('before', before), ('after', after)]]
    assert normalized[0] == normalized[1], 'Configuration differs beyond arm paths'
    for cell in [before, after]:
        assert json.loads((cell['out'] / 'command.json').read_text()) == cell['cmd']
        assert (cell['out'] / 'prompt.txt').read_text() == cell['cmd'][-1]


def verify_identities(root, manifest):
    assert bench.command(['codex', '--version']).decode().strip() == manifest['codex_version']
    for variant, directory in manifest['variant_directories'].items():
        assert sha(root / directory / 'prism-candidate') == manifest['binary_sha256'][variant]
    for base, key in [(PRODUCT, 'source_sha256'), (HERE, 'local_sha256'),
                      (EVIDENCE, 'frozen_sha256'), (SNAPSHOT, 'harness_sha256'),
                      (root, 'prepared_sha256')]:
        for name, digest in manifest[key].items():
            assert sha(base / name) == digest, 'Changed identity: ' + str(base / name)


guidance.verify_identities = verify_identities


def prepare():
    assert sha(PANEL / 'run_panel.py') == PREVIOUS['runner_sha256']
    assert sha(panel.HELPER) == PREVIOUS['helper_sha256']
    for variant, binary in BINARIES.items():
        assert sha(binary) == SOURCE[variant + '_binary_sha256']
    root = Path(tempfile.mkdtemp(prefix='prism-scoped-ab-', dir='/private/tmp'))
    print('RUN_DIR=' + str(root), flush=True)
    dump(HERE / 'active-run.json', dict(root=str(root), status='preparing', model_runs=0))
    roots = {v: root / d for v, d in guidance.DIRECTORIES.items()}
    for variant, base in roots.items():
        base.mkdir()
        shutil.copy2(BINARIES[variant], base / 'prism-candidate')
        shutil.copy2(PANEL / 'answer-schema.json', base / 'answer-schema.json')
        panel.preflight(base / 'prism-candidate', base)
    tasks, prepared = [], {}
    for task_id in analysis.TASKS:
        path = PANEL / (task_id + '.task.json')
        task = bench.Task.load(path)
        entry = next(t for t in PREVIOUS['tasks'] if t['task'] == task_id)
        assert json.loads(path.read_text()) == json.loads((SNAPSHOT / 'tasks' / (task_id + '.json')).read_text())
        assert sha(SNAPSHOT / 'tasks' / (task_id + '.json')) == entry['task_sha256']
        archive = bench.command(['git', '-C', task.workdir or task.repo, 'archive', task.pin])
        assert hashlib.sha256(archive).hexdigest() == entry['archive_sha256']
        pristine = {}
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            for member in tf:
                path_parts = Path(member.name)
                assert path_parts.name not in ['AGENTS.md', 'CLAUDE.md', '.mcp.json']
                assert not any(p in path_parts.parts for p in ['.codex', '.claude', '.git'])
                if member.isfile():
                    pristine[member.name] = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
        prepared[task_id] = task, archive, pristine
        tasks.append(entry)
        shutil.copy2(path, root / path.name)
    cells = {}
    for task_id, trial, variants in guidance.WAVES:
        task, archive, pristine = prepared[task_id]
        pair = {}
        for variant in variants:
            base = roots[variant]
            cell = panel.prepare_cell(base, base / 'prism-candidate', task, archive,
                                      trial, 'codex_prism', pristine)
            cell['cmd'][-1] = prompt_for(cell['cmd'][-1])
            dump(cell['out'] / 'command.json', cell['cmd'])
            (cell['out'] / 'prompt.txt').write_text(cell['cmd'][-1])
            history = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'],
                                     cwd=cell['work'], capture_output=True)
            assert history.returncode != 0
            assert all(sha(cell['work'] / p) == digest for p, digest in pristine.items())
            pair[variant] = cell
            cells[f'{task_id}.r{trial}.{variant}'] = dict(cell, out=str(cell['out']), work=str(cell['work']))
        assert_pair(pair['before'], pair['after'], roots)
        print(f'PREPARED {task_id}.r{trial}', flush=True)
    dump(root / 'cells.json', cells)
    shutil.copy2(HERE / 'PROTOCOL.md', root / 'PROTOCOL.md')
    frozen = [PANEL / 'run_panel.py', panel.HELPER, PANEL / 'manifest.json',
              PANEL / 'answer-schema.json',
              EVIDENCE / 'routing-2026-09-06/comparison/run_guidance.py',
              EVIDENCE / 'routing-2026-09-06/comparison/archive.py',
              EVIDENCE / 'evidence-delivery-2026-09-06/comparison/analyze.py']
    manifest = dict(run_id=root.name, created_at=time.time(),
        treatment='Prism binary only; identical direct-routing guidance in both arms',
        model='gpt-5.5', effort='medium', codex_version='codex-cli 0.153.4',
        product_head=bench.command(['git', 'rev-parse', 'HEAD'], PRODUCT).decode().strip(),
        binary_sha256={v: SOURCE[v + '_binary_sha256'] for v in BINARIES},
        variant_directories=guidance.DIRECTORIES, tasks=tasks, planned_cells=8,
        waves=guidance.WAVES, retries=0, launch_budget_usd=guidance.BUDGET,
        pair_reserve_usd=guidance.RESERVE, hard_billing_cap=None, concurrency=2,
        timeout_s=panel.LIMIT_S, source_sha256=SOURCE['source_sha256'],
        harness_sha256=PREVIOUS['harness_sha256'],
        price_basis='fixed-rate API equivalent, not invoice/subscription cost; excludes long-context premium',
        prices_per_million=dict(input=5, cached_input=.5, output=30),
        frozen_sha256={str(p.relative_to(EVIDENCE)): sha(p) for p in frozen},
        local_sha256={name: sha(HERE / name) for name in
                      ['run_comparison.py', 'test_comparison.py', 'archive.py', 'PROTOCOL.md']},
        prepared_sha256={str(p.relative_to(root)): sha(p) for p in root.rglob('*')
                         if p.is_file() and not {'work', 'preflight'} & set(p.relative_to(root).parts)})
    dump(root / 'manifest.json', manifest)
    verify_identities(root, manifest)
    dump(root / 'summary.json', dict(status='prepared', rows=[], planned_cells=8, estimated_spend_usd=0))
    dump(root / 'dry-run.json', dict(pass_all=True, prepared_cells=8, model_runs=0,
         same_prompt=True, only_binary_differs=True, history_absent=True,
         pristine_sources=True, mcp_preflight_arms=2, fresh_usage_ledger=True))
    dump(HERE / 'active-run.json', dict(root=str(root), status='prepared'))
    print('DRY RUN PASS: 8 cells prepared; 0 model runs', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
    else:
        assert args.root is not None
        guidance.run(args.root.resolve())


if __name__ == '__main__':
    main()
