from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import coding_suite


class GptCostTests(unittest.TestCase):
    def test_standard_cost_separates_cached_input(self) -> None:
        rec = {
            "measurement_complete": True,
            "input_tokens": 1_000_000,
            "cache_read_tokens": 200_000,
            "output_tokens": 100_000,
            "usage_raw": [{"input_tokens": 100_000}],
        }

        coding_suite.add_gpt55_cost(rec)

        self.assertEqual(rec["cost_usd"], 7.1)
        self.assertFalse(rec["long_context_pricing"])

    def test_long_context_multiplier_applies_to_full_run(self) -> None:
        rec = {
            "measurement_complete": True,
            "input_tokens": 300_000,
            "cache_read_tokens": 0,
            "output_tokens": 100_000,
            "usage_raw": [{"input_tokens": 300_000}],
        }

        coding_suite.add_gpt55_cost(rec)

        self.assertEqual(rec["cost_usd"], 7.5)
        self.assertTrue(rec["long_context_pricing"])

    def test_incomplete_measurement_has_no_estimated_cost(self) -> None:
        rec = {"measurement_complete": False, "cost_usd": None}

        coding_suite.add_gpt55_cost(rec)

        self.assertIsNone(rec["cost_usd"])


if __name__ == "__main__":
    unittest.main()
