import unittest
from unittest.mock import Mock

from probe import tool_reply


class ToolReplyTests(unittest.TestCase):
    def test_success_is_unchanged(self):
        result = {'content': [{'type': 'text', 'text': 'body'}]}
        client = Mock()
        client.request.return_value = result
        self.assertIs(tool_reply(client, 'prism_lookup', {'name': 'Get'}), result)

    def test_expected_rejection_keeps_original_rpc_packet(self):
        packet = {'jsonrpc': '2.0', 'id': 19, 'error': {
            'code': -32000, 'message': 'name batch must contain only nonempty strings; no lookups were run'}}
        client = Mock()
        client.request.side_effect = AssertionError(packet)
        self.assertIs(tool_reply(client, 'prism_lookup', {}, expected_rejection=True), packet)
        with self.assertRaises(AssertionError):
            tool_reply(client, 'prism_lookup', {})

    def test_other_failures_are_not_expected_rejection(self):
        client = Mock()
        for packet in [None, 'error', {'error': 'bad'}, {'error': {'code': -32000, 'message': 'index failed'}}]:
            client.request.side_effect = AssertionError(packet)
            with self.assertRaises((AssertionError, ValueError)):
                tool_reply(client, 'prism_lookup', {}, expected_rejection=True)


if __name__ == '__main__':
    unittest.main()
