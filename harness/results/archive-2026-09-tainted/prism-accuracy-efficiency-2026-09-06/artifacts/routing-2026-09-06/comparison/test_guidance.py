import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_guidance as run


def rows():
    return [dict(task=task, trial=trial, variant=variant, comparison_id=f'{task}.{trial}.{variant}',
                 audited_valid=True, audited_total_tokens=100 if variant == 'before' else 50,
                 cost_usd=.2 if variant == 'before' else .1, setup_abort=False,
                 score=dict(recall=1, precision=1, overconfident=False))
            for task in run.analysis.TASKS for trial in [1, 2] for variant in run.DIRECTORIES]


class GuidanceTests(unittest.TestCase):
    def test_guidance_only_replacement(self):
        prefix = 'Do not edit.\nISSUE:\nA task with its own unchanged instructions.'
        old = prefix + run.OLD_GUIDANCE
        self.assertEqual(run.prompt_for(old, 'before'), old)
        new = run.prompt_for(old, 'after')
        self.assertEqual(new, prefix + run.NEW_GUIDANCE)
        self.assertNotIn('Start discovery with prism_search or prism_query.', new)
        self.assertEqual(new.count('\nTOOLS:'), 1)
        for requirement in ['call prism_change_impact directly', 'name=[...]', 'Retain all affected sites',
                            'omitted evidence', 'ambiguous receivers', 'Report remaining evidence gaps']:
            self.assertIn(requirement, new)

    def test_reject_changed_or_duplicate_steering(self):
        for original in ['Task\nChanged guidance', '\nTOOLS: earlier guidance' + run.OLD_GUIDANCE]:
            with self.assertRaises(AssertionError):
                run.prompt_for(original, 'after')

    def test_pair_rejects_settings_and_task_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = {v: Path(directory) / d for v, d in run.DIRECTORIES.items()}
            cells = {}
            for variant, root in roots.items():
                root.mkdir()
                cmd = ['codex', '-C', str(root), '-m', 'gpt-5.5', run.prompt_for('Task' + run.OLD_GUIDANCE, variant)]
                run.dump(root / 'command.json', cmd)
                (root / 'prompt.txt').write_text(cmd[-1])
                cells[variant] = dict(out=root, cmd=cmd)
            run.assert_pair(cells['before'], cells['after'], roots)
            for index, value in [(4, 'other-model'), (-1, 'Changed task' + run.NEW_GUIDANCE)]:
                altered = copy.deepcopy(cells['after'])
                altered['cmd'][index] = value
                with self.assertRaises(AssertionError):
                    run.assert_pair(cells['before'], altered, roots)

    def test_fresh_cost_and_all_failures_count(self):
        self.assertEqual(run.analysis.analyze([])['estimated_spend_usd'], 0)
        data = rows()
        self.assertAlmostEqual(run.analysis.analyze(data)['estimated_spend_usd'], 1.2)
        data[0]['audited_valid'] = False
        self.assertAlmostEqual(run.analysis.analyze(data)['estimated_spend_usd'], 1.2)
        self.assertEqual(run.analysis.analyze(data)['decision'], 'inconclusive')
        data[0]['setup_abort'] = True
        self.assertEqual(run.stop_reason(data), 'setup_failure')

    def test_unknown_usage_budget_and_incomplete_bed(self):
        data = rows()
        data[0]['cost_usd'] = None
        self.assertEqual(run.stop_reason(data), 'measurement_incomplete')
        self.assertIsNone(run.analysis.analyze(data)['estimated_spend_usd'])
        self.assertEqual(run.analysis.analyze(rows()[:-1])['decision'], 'inconclusive')
        self.assertEqual(run.analysis.analyze(rows())['decision'], 'pass')
        data = rows()
        data[0]['cost_usd'] = 2
        self.assertEqual(run.stop_reason(data), 'budget_incomplete')

    def test_quality_regression_and_tokens_are_not_offset_by_cost(self):
        for change in ['recall', 'tokens', 'false_complete']:
            data = rows()
            if change == 'recall':
                data[1]['score']['recall'] = .5
            elif change == 'tokens':
                for row in data:
                    if row['variant'] == 'after':
                        row['audited_total_tokens'] = 200
            else:
                data[1]['score']['overconfident'] = True
            self.assertEqual(run.analysis.analyze(data)['decision'], 'fail')

    def test_no_completed_run_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run.dump(root / 'manifest.json', {})
            for status in ['running', 'complete', 'harness_error', 'budget_incomplete']:
                run.dump(root / 'summary.json', dict(status=status))
                with patch.object(run.panel, 'run_cell') as paid:
                    with self.assertRaises(AssertionError):
                        run.run(root)
                    paid.assert_not_called()

    def test_frozen_analyzer_is_unmodified(self):
        previous = json.loads((run.PRIOR / 'manifest.json').read_text())
        self.assertEqual(run.sha(run.PRIOR / 'analyze.py'), previous['local_sha256']['analyze.py'])

    def test_exception_keeps_spend_unknown_not_partial_sum(self):
        errors = [dict(comparison_id='failed-cell', cost_usd=None, error='measurement failure')]
        result = run.readout(rows(), errors)
        self.assertIsNone(result['estimated_spend_usd'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['decision'], 'inconclusive')
        self.assertEqual(result['unmeasured_attempts'], errors)


if __name__ == '__main__':
    unittest.main()
