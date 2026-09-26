import copy
import unittest

from analyze import analyze, diagnostics


def rows():
    return [dict(task=task, trial=trial, variant=variant, comparison_id=f'{task}.{trial}.{variant}',
                 audited_valid=True, audited_total_tokens=100 if variant=='before' else 50,
                 cost_usd=1 if variant=='before' else .5,
                 score=dict(recall=1, precision=1, overconfident=False))
            for task in ['gin-4645','django-connparams'] for trial in [1,2] for variant in ['before','after']]


class ComparisonTests(unittest.TestCase):
    def test_complete_pass_and_current_spend(self):
        result = analyze(rows())
        self.assertEqual(result['decision'], 'pass')
        self.assertEqual(result['estimated_spend_usd'], 6)
        self.assertEqual(result['median_paired_token_saving'], .5)

    def test_missing_invalid_and_unknown_are_inconclusive(self):
        self.assertEqual(analyze(rows()[:-1])['decision'], 'inconclusive')
        for field, value in [('audited_valid',False), ('cost_usd',None), ('audited_total_tokens',None)]:
            data = rows()
            data[1][field] = value
            self.assertEqual(analyze(data)['decision'], 'inconclusive')

    def test_duplicate_rejected(self):
        data = rows()
        with self.assertRaises(ValueError):
            analyze(data+[copy.deepcopy(data[0])])

    def test_token_loss_not_hidden_by_cost_saving(self):
        data = rows()
        for row in data:
            if row['variant']=='after':
                row['audited_total_tokens'] = 200
        result = analyze(data)
        self.assertEqual(result['decision'], 'fail')
        self.assertTrue(result['checks']['aggregate_cost_30_percent'])

    def test_quality_regression_and_tied_bad_quality_fail(self):
        data = rows()
        data[1]['score']['recall'] = .9
        data[1]['score']['overconfident'] = True
        self.assertEqual(analyze(data)['decision'], 'fail')
        for row in data:
            row['score']['recall'] = .5
        self.assertFalse(analyze(data)['checks']['absolute_recall'])

    def test_diagnostics_require_success_and_keep_attempted_followups(self):
        call = lambda tool, **kw: dict(type='mcp_tool_call',tool=tool,status='completed',arguments={},**kw)
        calls = [call('prism_change_impact',error='failed'), call('prism_search'),
                 call('prism_change_impact'), call('prism_search'), call('prism_lookup'),
                 dict(type='command_execution',status='completed'),
                 dict(type='mcp_tool_call',tool='prism_lookup',status='completed',arguments={'name':['A','B']})]
        self.assertEqual(diagnostics(calls), dict(successful_impact_calls=1,searches_after_impact=1,
             lookups_after_impact=2,native_commands_after_impact=1,successful_batch_calls=1,batch_names_requested=2))


if __name__=='__main__':
    unittest.main()
