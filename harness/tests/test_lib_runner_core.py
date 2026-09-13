"""Unit tests for harness/lib/runner_core.py: the audit logic, PATH
isolation, and the template content-hash mismatch check -- everything
testable without live claude/codex/docker.
"""
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

from lib import runner_core as rc  # noqa: E402


class InvokesPrismTests(unittest.TestCase):
    def test_detects_bare_prism_invocation(self):
        self.assertTrue(rc.invokes_prism("prism query 'find target'"))

    def test_detects_prism_under_a_path(self):
        self.assertTrue(rc.invokes_prism("/Users/me/bin/prism search x"))

    def test_ignores_unrelated_commands(self):
        self.assertFalse(rc.invokes_prism("rg pattern src"))

    def test_tolerates_unterminated_quotes(self):
        self.assertFalse(rc.invokes_prism("rg 'unterminated"))


class AuditCallsTests(unittest.TestCase):
    def test_native_arm_using_mcp_prism_is_a_violation(self):
        rec = {}
        calls = [{"name": "mcp__prism__search", "input": {}}]
        rc.audit_calls(rec, calls, "sonnet_native")
        self.assertIn("native arm used Prism", rec["violations"])

    def test_native_arm_using_prism_cli_is_a_violation(self):
        rec = {}
        calls = [{"type": "command_execution", "command": "prism search target"}]
        rc.audit_calls(rec, calls, "gpt55_native")
        self.assertEqual(rec["violations"], ["native arm used Prism"])

    def test_prism_arm_using_prism_cli_is_adoption_not_a_violation(self):
        rec = {}
        calls = [{"type": "command_execution", "command": "prism query 'find target'"}]
        rc.audit_calls(rec, calls, "gpt55_prism")
        self.assertEqual(rec["violations"], [])
        self.assertEqual(rec["prism_actions"], 1)
        self.assertEqual(rec["prism_cli_commands"], ["prism query 'find target'"])

    def test_delegation_tool_is_a_violation_for_sonnet(self):
        rec = {}
        calls = [{"name": "WebFetch", "input": {"url": "https://example.com"}}]
        rc.audit_calls(rec, calls, "sonnet_prism")
        self.assertIn("delegation or network tool used", rec["violations"])

    def test_duplicate_prism_calls_are_counted(self):
        rec = {}
        calls = [
            {"name": "mcp__prism__lookup", "input": {"name": "Foo"}},
            {"name": "mcp__prism__lookup", "input": {"name": "Foo"}},
        ]
        rc.audit_calls(rec, calls, "sonnet_prism")
        self.assertEqual(rec["duplicate_prism_calls"], 1)


class TemplateContentTests(unittest.TestCase):
    def test_excludes_vcs_and_index_databases(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "src").mkdir()
            (root / "src/generated.py").write_text("VERSION = '1'\n")
            (root / ".grove").mkdir()
            (root / ".grove/index.db").write_text("ignored")
            (root / ".prism").mkdir()
            (root / ".prism/index.db").write_text("ignored")

            content = rc.template_content(root)

        self.assertIn("src/generated.py", content)
        self.assertNotIn(".grove/index.db", content)
        self.assertNotIn(".prism/index.db", content)

    def test_content_hash_changes_when_a_file_changes(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "a.py").write_text("x = 1\n")
            before = rc.template_content(root)
            (root / "a.py").write_text("x = 2\n")
            after = rc.template_content(root)
        self.assertNotEqual(before["a.py"], after["a.py"])


class AgentPathTests(unittest.TestCase):
    def test_prism_arm_exposes_pinned_cli_ahead_of_rg(self):
        path = rc.agent_path(Path("/run/env/task"), Path("/run/bin"), "/tools/rg")
        parts = path.split(":")
        self.assertIn("/run/bin", parts)
        self.assertIn("/tools", parts)
        self.assertLess(parts.index("/run/bin"), parts.index("/tools"))

    def test_native_arm_does_not_expose_prism_cli(self):
        path = rc.agent_path(Path("/run/env/task"), None, "/tools/rg")
        self.assertNotIn("/run/bin", path.split(":"))

    def test_no_env_dir_is_tolerated(self):
        path = rc.agent_path(None, None, None)
        self.assertTrue(path)


class SourcePathTests(unittest.TestCase):
    def test_accepts_python_implementation_files(self):
        self.assertTrue(rc.is_source_path("src/example/core.py"))

    def test_rejects_tests_and_generated_databases(self):
        self.assertFalse(rc.is_source_path("tests/test_core.py"))
        self.assertFalse(rc.is_source_path("test/example_test.py"))
        self.assertFalse(rc.is_source_path(".grove/grove.db"))


if __name__ == "__main__":
    unittest.main()
