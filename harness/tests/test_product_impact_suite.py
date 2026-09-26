"""Offline checks for impact runner arm selection."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.product_impact_suite import parse_arms  # noqa: E402


class ImpactArmSelectionTests(unittest.TestCase):
    def test_prism_only_pair_keeps_both_agents(self):
        self.assertEqual(parse_arms("sonnet_prism,gpt55_prism"),
                         ["sonnet_prism", "gpt55_prism"])

    def test_rejects_unknown_or_duplicate_arm_before_a_run(self):
        for value in ("sonnet_prism,sonnet_prism", "sonnet_prism,gpt-5_native", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_arms(value)


if __name__ == "__main__":
    unittest.main()
