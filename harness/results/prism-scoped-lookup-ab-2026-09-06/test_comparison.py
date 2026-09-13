import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_comparison as run


class ComparisonTests(unittest.TestCase):
    def test_prompt_is_identical_new_guidance(self):
        self.assertEqual(run.prompt_for('TASK' + run.guidance.OLD_GUIDANCE),
                         'TASK' + run.guidance.NEW_GUIDANCE)

    def test_unknown_prompt_rejected(self):
        with self.assertRaises(AssertionError):
            run.prompt_for('other steering')

    def test_pair_only_paths_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = {v: Path(tmp) / d for v, d in run.guidance.DIRECTORIES.items()}
            cells = {}
            for variant, root in roots.items():
                root.mkdir()
                cmd = ['codex', str(root / 'prism-candidate'), 'same prompt']
                run.dump(root / 'command.json', cmd)
                (root / 'prompt.txt').write_text(cmd[-1])
                cells[variant] = dict(cmd=cmd, out=root)
            run.assert_pair(cells['before'], cells['after'], roots)
            cells['after']['cmd'][0] = 'other-model'
            with self.assertRaises(AssertionError):
                run.assert_pair(cells['before'], cells['after'], roots)

    def test_unknown_attempt_cannot_pass_or_cost_zero(self):
        result = run.guidance.readout([], [dict(cost_usd=None)])
        self.assertIsNone(result['estimated_spend_usd'])
        self.assertEqual(result['decision'], 'inconclusive')

    def test_budget_and_setup_stop(self):
        with patch.object(run.analysis, 'analyze', return_value={'estimated_spend_usd': 2.26}):
            self.assertEqual(run.guidance.stop_reason([]), 'budget_incomplete')
        self.assertEqual(run.guidance.stop_reason([{'setup_abort': True}]), 'setup_failure')

    def test_no_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run.dump(root / 'manifest.json', {})
            run.dump(root / 'summary.json', {'status': 'complete'})
            with self.assertRaisesRegex(AssertionError, 'resumed or reused'):
                run.guidance.run(root)

    def test_identities_detect_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for variant in ['before', 'after']:
                (root / variant).mkdir()
                (root / variant / 'prism-candidate').write_bytes(variant.encode())
            manifest = dict(codex_version='test', variant_directories={v: v for v in ['before', 'after']},
                binary_sha256={v: run.sha(root / v / 'prism-candidate') for v in ['before', 'after']},
                source_sha256={}, local_sha256={}, frozen_sha256={}, harness_sha256={}, prepared_sha256={})
            with patch.object(run.bench, 'command', return_value=b'test\n'):
                run.verify_identities(root, manifest)
                (root / 'after/prism-candidate').write_bytes(b'changed')
                with self.assertRaises(AssertionError):
                    run.verify_identities(root, manifest)

    def test_scorer_imports_are_pinned(self):
        import schema
        self.assertEqual(Path(schema.__file__).parent, run.SNAPSHOT)
        self.assertIs(run.bench.Task, schema.Task)


if __name__ == '__main__':
    unittest.main()
