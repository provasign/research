from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)


import sys
import tempfile
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


class SourcePathTests(unittest.TestCase):
    def test_accepts_python_implementation_files(self) -> None:
        self.assertTrue(coding_suite.is_source_path("src/example/core.py"))
        self.assertTrue(coding_suite.is_source_path("rich/segment.py"))

    def test_rejects_tests_docs_and_generated_databases(self) -> None:
        self.assertFalse(coding_suite.is_source_path("tests/test_core.py"))
        self.assertFalse(coding_suite.is_source_path("test/example_test.py"))
        self.assertFalse(coding_suite.is_source_path("docs/design.rst"))
        self.assertFalse(coding_suite.is_source_path(".grove/grove.db"))

    def test_template_content_includes_generated_source_but_not_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "src").mkdir()
            (root / "src/generated.py").write_text("VERSION = '1'\n")
            (root / ".grove").mkdir()
            (root / ".grove/index.db").write_text("ignored")

            content = coding_suite.template_content(root)

        self.assertIn("src/generated.py", content)
        self.assertNotIn(".grove/index.db", content)


class AgentPathTests(unittest.TestCase):
    def test_prism_arm_exposes_pinned_cli(self) -> None:
        cell = {
            "env_dir": Path("/run/environments/task"),
            "prism_cli_dir": Path("/run/bin"),
        }

        parts = coding_suite.agent_path(cell, "/tools/rg").split(":")

        self.assertIn("/run/bin", parts)
        self.assertIn("/tools", parts)

    def test_native_arm_does_not_expose_prism_cli(self) -> None:
        cell = {"env_dir": Path("/run/environments/task"), "prism_cli_dir": None}

        parts = coding_suite.agent_path(cell, "/tools/rg").split(":")

        self.assertNotIn("/run/bin", parts)


class AuditTests(unittest.TestCase):
    def test_codex_cli_fallback_counts_as_prism_adoption(self) -> None:
        rec = {}
        calls = [{"type": "command_execution", "command": "prism query 'find target'"}]

        coding_suite.audit(rec, calls, "gpt55_prism")

        self.assertEqual(rec["prism_actions"], 1)
        self.assertEqual(rec["prism_cli_commands"], ["prism query 'find target'"])
        self.assertEqual(rec["violations"], [])

    def test_native_cli_prism_is_a_protocol_violation(self) -> None:
        rec = {}
        calls = [{"type": "command_execution", "command": "prism search target"}]

        coding_suite.audit(rec, calls, "gpt55_native")

        self.assertEqual(rec["violations"], ["native arm used Prism"])


if __name__ == "__main__":
    unittest.main()
