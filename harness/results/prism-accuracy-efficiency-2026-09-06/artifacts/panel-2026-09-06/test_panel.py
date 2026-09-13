import copy
import json
from pathlib import Path
import unittest

import run_panel as panel


class PanelAuditTests(unittest.TestCase):
    def load(self, arm):
        root = Path(__file__).resolve().parent.parent / 'four-way-2026-09-06/evidence' / arm
        return json.loads((root/'measurement.json').read_text()), panel.bench.events(root/'stdout.jsonl')

    def test_mcp_denial_is_not_valid_prism_delivery(self):
        rec, events = self.load('codex_prism')
        panel.audit_usage(rec, events, 'codex_prism')
        self.assertIn('no successful Prism delivery', rec['violations'])
        self.assertEqual(rec['cost_usd'], .721578)

    def test_corrected_cell_keeps_ordinary_argument_error_cost(self):
        rec, events = self.load('codex_prism_retry')
        panel.audit_usage(rec, events, 'codex_prism')
        self.assertEqual(rec['violations'], [])
        self.assertEqual(len(rec['prism_successful_calls']), 9)
        self.assertEqual(len(rec['tool_errors']), 1)
        self.assertEqual(rec['cost_usd'], .338071)

    def test_claude_auxiliary_usage_included(self):
        for arm, expected in [('sonnet_baseline', 695012), ('sonnet_prism', 145893)]:
            rec, events = self.load(arm)
            panel.audit_usage(rec, events, arm)
            self.assertEqual(rec['audited_total_tokens'], expected)
            self.assertEqual(rec['violations'], [])

    def test_unknown_model_usage_is_not_zero(self):
        rec, events = self.load('sonnet_baseline')
        rec['usage']['model_usage']['claude-sonnet-5'].pop('outputTokens')
        panel.audit_usage(rec, events, 'sonnet_baseline')
        self.assertFalse(rec['measurement_complete'])
        self.assertIsNone(rec['audited_total_tokens'])

    def test_native_paths_do_not_count_as_prism_execution(self):
        for cmd in ['cd /private/tmp/prism-panel-123/work/gin.r1.sonnet_baseline',
                    'rg Foo /private/tmp/prism-panel-123/work/gin.r1.codex_baseline/a.go',
                    '/bin/zsh -lc "rg Foo ."']:
            self.assertFalse(panel.invokes_prism(cmd), cmd)
        for cmd in ['prism search Foo', '/tmp/run/prism-candidate query Foo',
                    '/bin/zsh -lc "prism search Foo"']:
            self.assertTrue(panel.invokes_prism(cmd), cmd)

    def test_native_cannot_silently_use_prism(self):
        rec, events = self.load('codex_baseline')
        rec['calls'].append(dict(type='command_execution', command='prism search Foo'))
        panel.audit_usage(rec, events, 'codex_baseline')
        self.assertIn('native baseline used Prism', rec['violations'])


if __name__=='__main__':
    unittest.main()
