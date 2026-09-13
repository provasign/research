
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usage_account as usage


class UsageTests(unittest.TestCase):
    def test_cache_creation_is_included_and_unknown_is_not_zero(self):
        with patch.object(usage, "claude_version", return_value="test"):
            record = usage.cli_usage({"usage": {
                "input_tokens": 10, "cache_creation_input_tokens": 20,
                "cache_read_input_tokens": 30, "output_tokens": 4,
            }, "total_cost_usd": .12})
            self.assertEqual(record["input_total"], 60)
            self.assertTrue(record["usage_complete"])
            self.assertFalse(usage.cli_usage({"usage": [1], "total_cost_usd": 1})["usage_complete"])
            for value in (None, float("nan"), -1, True):
                invalid = usage.cli_usage({"total_cost_usd": value})
                self.assertFalse(invalid["usage_complete"])
                self.assertIsNone(invalid["input_total"])
                self.assertIsNone(invalid["cost_usd_cli"])

    def test_streaming_duplicates_use_latest_usage_and_distinct_tool_ids(self):
        first = {"type": "assistant", "message": {"id": "m1", "usage": {
            "input_tokens": 10, "cache_creation_input_tokens": 20,
            "cache_read_input_tokens": 30, "output_tokens": 1,
        }, "content": [{"type": "tool_use", "id": "t1", "name": "Read"}]}}
        last = json.loads(json.dumps(first))
        last["message"]["usage"]["output_tokens"] = 8
        result = {"type": "user", "message": {"content": [{
            "type": "tool_result", "tool_use_id": "t1", "content": "\u00e9",
        }]}}
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"session.jsonl"
            events = [first, last, result, result,
                      {"type": "result", "usage": {"output_tokens": 12}}]
            p.write_text("\n".join(json.dumps(e) for e in events))
            got = usage.analyze_transcript(p)
        self.assertEqual(got["messages"], 1)
        self.assertEqual(got["duplicate_lines"], 1)
        self.assertEqual(got["tokens"], {"input_uncached": 10, "cache_creation": 20, "cache_read": 30, "output": 12})
        self.assertEqual(got["tool_calls"], {"Read": 1})
        self.assertEqual(got["tool_result_bytes"], {"Read": 2})
        self.assertTrue(got["usage_complete"])
        self.assertTrue(got["diagnostics_complete"])
        self.assertEqual(got["aggregate_status"], "present")

    def test_session_transcript_without_stdout_result_has_valid_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"session.jsonl"
            p.write_text(json.dumps({"type": "assistant", "message": {
                "id": "m1", "usage": {"input_tokens": 2, "cache_creation_input_tokens": 0,
                                       "cache_read_input_tokens": 100, "output_tokens": 1}}}))
            got = usage.analyze_transcript(p)
        self.assertTrue(got["diagnostics_complete"])
        self.assertIsNone(got["usage_complete"])
        self.assertEqual(got["aggregate_status"], "not_present_in_transcript")
        self.assertIsNone(got["tokens"]["output"])
        self.assertEqual(got["step_output_observed"], 1)
        self.assertEqual(got["warnings"], [])
        self.assertIn("no final aggregate in transcript", got["notes"][0])

    def test_explicit_zero_cache_counters_are_valid_but_missing_is_unknown(self):
        raw = {"input_tokens": 10, "output_tokens": 4,
               "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        with patch.object(usage, "claude_version", return_value="test"):
            record = usage.cli_usage({"usage": raw, "total_cost_usd": .01})
            self.assertTrue(record["usage_complete"])
            self.assertEqual(record["input_total"], 10)
            del raw["cache_creation_input_tokens"]
            record = usage.cli_usage({"usage": raw, "total_cost_usd": .01})
            self.assertFalse(record["usage_complete"])
            self.assertIsNone(record["tokens"]["cache_creation"])

    def test_missing_message_ids_cannot_be_treated_as_complete_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"session.jsonl"
            p.write_text(json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 5}}}))
            got = usage.analyze_transcript(p)
        self.assertFalse(got["usage_complete"])
        self.assertFalse(got["diagnostics_complete"])
        self.assertIn("assistant message missing identity", got["warnings"])
        self.assertIsNone(got["tokens"]["output"])


if __name__ == "__main__":
    unittest.main()
