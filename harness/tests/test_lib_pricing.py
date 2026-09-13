"""Unit tests for harness/lib/pricing.py."""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import pricing  # noqa: E402


class Gpt55CostTests(unittest.TestCase):
    def test_standard_cost_separates_cached_input(self):
        rec = {
            "measurement_complete": True,
            "input_tokens": 1_000_000,
            "cache_read_tokens": 200_000,
            "output_tokens": 100_000,
            "usage_raw": [{"input_tokens": 100_000}],
        }
        pricing.add_gpt55_cost(rec)
        self.assertEqual(rec["cost_usd"], 7.1)
        self.assertFalse(rec["long_context_pricing"])

    def test_long_context_multiplier_applies_to_full_run(self):
        rec = {
            "measurement_complete": True,
            "input_tokens": 300_000,
            "cache_read_tokens": 0,
            "output_tokens": 100_000,
            "usage_raw": [{"input_tokens": 300_000}],
        }
        pricing.add_gpt55_cost(rec)
        self.assertEqual(rec["cost_usd"], 7.5)
        self.assertTrue(rec["long_context_pricing"])

    def test_incomplete_measurement_has_no_estimated_cost(self):
        rec = {"measurement_complete": False, "cost_usd": None}
        pricing.add_gpt55_cost(rec)
        self.assertIsNone(rec["cost_usd"])

    def test_untabulated_model_is_a_no_op(self):
        rec = {"measurement_complete": True, "input_tokens": 100, "cache_read_tokens": 0,
               "output_tokens": 10, "usage_raw": [], "cost_usd": None}
        pricing.add_api_cost(rec, "some-future-model")
        self.assertIsNone(rec["cost_usd"])


class PricingTableTests(unittest.TestCase):
    def test_pricing_for_known_model(self):
        self.assertIsNotNone(pricing.pricing_for("gpt-5.5"))

    def test_pricing_for_unknown_model_is_none(self):
        self.assertIsNone(pricing.pricing_for("nonexistent-model"))


if __name__ == "__main__":
    unittest.main()
