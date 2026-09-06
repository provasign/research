import copy
import unittest

import analyze_panel as analysis


def rows():
    return [dict(task=task,trial=trial,arm=model+'_'+arm,cell_id=f'{task}-{trial}-{model}-{arm}',
                 audited_valid=True,audited_total_tokens=100 if arm=='baseline' else 50,
                 cost_usd=1 if arm=='baseline' else .5,
                 score=dict(recall=1,precision=1,overconfident=False))
            for task in analysis.TASKS for trial in [1,2]
            for model in ['sonnet','codex'] for arm in ['baseline','prism']]


class AnalysisTests(unittest.TestCase):
    def test_all_pairs_and_clients_must_pass(self):
        data=rows()
        self.assertEqual(analysis.analyze(data)['decision'],'pass')
        data[1]['score']['recall']=.9
        self.assertEqual(analysis.analyze(data)['decision'],'fail')

    def test_incomplete_or_invalid_cannot_pass(self):
        self.assertEqual(analysis.analyze(rows()[:-1])['decision'],'inconclusive')
        data=rows()
        data[0]['audited_valid']=False
        self.assertEqual(analysis.analyze(data)['decision'],'inconclusive')

    def test_duplicate_trials_are_not_extra_evidence(self):
        data=rows()
        with self.assertRaises(ValueError):
            analysis.analyze(data+[data[0]])

    def test_dollar_savings_do_not_override_token_regression(self):
        data=rows()
        for row in data:
            if row['arm']=='codex_prism':
                row['audited_total_tokens']=110
        result=analysis.analyze(data)
        self.assertEqual(result['decision'],'fail')
        self.assertTrue(result['providers']['sonnet']['pass'])
        self.assertFalse(result['providers']['codex']['checks']['median_tokens_25_percent'])

    def test_equal_poor_quality_is_not_success(self):
        data=rows()
        for row in data:
            row['score']['recall']=.9
        self.assertEqual(analysis.analyze(data)['decision'],'fail')


if __name__=='__main__':
    unittest.main()
