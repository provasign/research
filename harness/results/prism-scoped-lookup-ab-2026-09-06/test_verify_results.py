import json
from pathlib import Path
import tempfile
import unittest

import verify_results as verify


class ReplayTests(unittest.TestCase):
    def test_scoped_response_is_not_a_body_success_claim(self):
        call = dict(id='one', type='mcp_tool_call', tool='prism_lookup', status='completed',
                    arguments={'name': [{'name': 'Wrong.receiver', 'file': 'a.py'}]},
                    result={'content': [{'text': 'matched=false'}]})
        result = verify.inspect_calls([call])
        self.assertTrue(result['scoped_calls'][0]['successful_response'])
        self.assertEqual(result['scoped_calls'][0]['items'], call['arguments']['name'])

    def test_rpc_and_result_errors_both_count(self):
        calls = [dict(type='mcp_tool_call', tool='prism_lookup', status='failed', error={'message': 'RPC'}),
                 dict(type='mcp_tool_call', tool='prism_search', status='completed', result={'isError': True})]
        self.assertEqual(len(verify.inspect_calls(calls)['mcp_errors']), 2)

    def test_string_batch_not_scoped_and_json_args_work(self):
        call = dict(type='mcp_tool_call', tool='prism_lookup', status='completed',
                    arguments=json.dumps({'name': ['A', {'name': 'B', 'file': 'b.py'}]}))
        result = verify.inspect_calls([call])
        self.assertEqual(result['scoped_calls'][0]['items'], [{'name': 'B', 'file': 'b.py'}])

    def test_bad_archive_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'raw.txt').write_text('changed')
            (root / 'SHA256SUMS.json').write_text(json.dumps({'raw.txt': 'bad'}))
            with self.assertRaisesRegex(AssertionError, 'Archive changed'):
                verify.verify(root)


if __name__ == '__main__':
    unittest.main()
