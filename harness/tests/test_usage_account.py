
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

    def test_cache_write_ttl_split_is_kept_per_request_and_in_total(self):
        with patch.object(usage, "claude_version", return_value="test"):
            record = usage.cli_usage({"usage": {
                "input_tokens": 1, "cache_creation_input_tokens": 30, "cache_read_input_tokens": 0,
                "output_tokens": 2, "cache_creation": {"ephemeral_5m_input_tokens": 10,
                                                        "ephemeral_1h_input_tokens": 20},
            }, "total_cost_usd": .01})
            self.assertEqual(record["cache_ttl"], {"cache_5m": 10, "cache_1h": 20})
            self.assertEqual(usage.cli_usage({"usage": {}})["cache_ttl"], {"cache_5m": None, "cache_1h": None})

        def message(mid, rid, write_1h):
            return {"type": "assistant", "requestId": rid, "message": {"id": mid, "usage": {
                "input_tokens": 1, "cache_creation_input_tokens": write_1h,
                "cache_read_input_tokens": 5, "output_tokens": 3,
                "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": write_1h},
            }}}
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"session.jsonl"
            events = [message("m1", "r1", 100), message("m1", "r1", 100), message("m2", "r2", 7)]
            p.write_text("\n".join(json.dumps(e) for e in events))
            got = usage.analyze_transcript(p)
        self.assertEqual(got["cache_ttl"], {"cache_5m": 0, "cache_1h": 107})
        self.assertEqual([r["message_id"] for r in got["per_request"]], ["m1", "m2"])
        self.assertEqual(got["per_request"][1], {
            "message_id": "m2", "request_id": "r2", "input_uncached": 1, "cache_creation": 7,
            "cache_read": 5, "output": 3, "cache_5m": 0, "cache_1h": 7})
        # A transcript without the TTL detail stays unknown, never zero.
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"session.jsonl"
            e = message("m1", "r1", 4); del e["message"]["usage"]["cache_creation"]
            p.write_text(json.dumps(e))
            got = usage.analyze_transcript(p)
        self.assertEqual(got["cache_ttl"], {"cache_5m": None, "cache_1h": None})


if __name__ == "__main__":
    unittest.main()
