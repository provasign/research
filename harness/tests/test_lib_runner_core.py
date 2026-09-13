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

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import runner_core as rc  # noqa: E402


class ActiveToolTests(unittest.TestCase):
    def test_prism_arm(self):
        self.assertEqual(rc.active_tool("sonnet_prism"), "prism")
        self.assertEqual(rc.active_tool("gpt55_prism"), "prism")

    def test_codegraph_arm(self):
        self.assertEqual(rc.active_tool("sonnet_codegraph"), "codegraph")
        self.assertEqual(rc.active_tool("gpt55_codegraph"), "codegraph")

    def test_native_arm(self):
        self.assertEqual(rc.active_tool("sonnet_native"), "native")
        self.assertEqual(rc.active_tool("gpt55_native"), "native")


class ToolRegistryTests(unittest.TestCase):
    def test_prism_mcp_stdio(self):
        spec = rc.TOOLS["prism"]
        entry = spec.mcp_stdio(Path("/bin/prism"), Path("/work"))
        self.assertEqual(entry, {"type": "stdio", "command": "/bin/prism",
                                 "args": ["mcp", "/work"]})

    def test_codegraph_mcp_stdio(self):
        spec = rc.TOOLS["codegraph"]
        entry = spec.mcp_stdio(Path("/bin/codegraph"), Path("/work"))
        self.assertEqual(entry, {"type": "stdio", "command": "/bin/codegraph",
                                 "args": ["serve", "-p", "/work", "--mcp"]})

    def test_codegraph_init_args_is_non_interactive_with_no_extra_flags(self):
        spec = rc.TOOLS["codegraph"]
        args = spec.init_args(Path("/bin/codegraph"), Path("/work"))
        self.assertEqual(args, ["/bin/codegraph", "init", "/work"])

    def test_prism_codex_mcp_config_approves_compact_tool(self):
        spec = rc.TOOLS["prism"]
        cfg = rc.AgentConfig(prism_tools=["prism_search"])
        lines = spec.codex_mcp_config(Path("/bin/prism"), Path("/work")) + spec.codex_extra_config(cfg)
        self.assertIn("mcp_servers.prism.required=true", lines)
        self.assertIn('mcp_servers.prism.tools.prism.approval_mode="approve"', lines)
        self.assertIn('mcp_servers.prism.tools.prism_search.approval_mode="approve"', lines)

    def test_codegraph_codex_mcp_config_has_no_per_tool_approval_loop(self):
        spec = rc.TOOLS["codegraph"]
        self.assertIsNone(spec.codex_extra_config)
        lines = spec.codex_mcp_config(Path("/bin/codegraph"), Path("/work"))
        self.assertIn("mcp_servers.codegraph.required=true", lines)
        self.assertTrue(any("serve" in line for line in lines))

    def test_invokes_cli_matches_own_binary_only(self):
        self.assertTrue(rc.TOOLS["prism"].invokes_cli("prism query x"))
        self.assertFalse(rc.TOOLS["prism"].invokes_cli("codegraph explore x"))
        self.assertTrue(rc.TOOLS["codegraph"].invokes_cli("codegraph explore x"))
        self.assertFalse(rc.TOOLS["codegraph"].invokes_cli("prism query x"))

    def test_sonnet_call_prefixes_are_distinct(self):
        self.assertEqual(rc.TOOLS["prism"].sonnet_call_prefix, "mcp__prism__")
        self.assertEqual(rc.TOOLS["codegraph"].sonnet_call_prefix, "mcp__codegraph__")


class SuccessfulToolActionsTests(unittest.TestCase):
    def test_denied_compact_mcp_call_is_not_adoption(self):
        calls = [{"type": "mcp_tool_call", "server": "prism", "tool": "prism",
                  "status": "failed", "error": {"message": "requires approval"}}]
        self.assertEqual(rc.successful_own_tool_actions([], calls, "gpt55_prism"), 0)

    def test_completed_mcp_or_cli_call_is_adoption(self):
        calls = [{"type": "mcp_tool_call", "server": "prism", "tool": "prism",
                  "status": "completed", "error": None},
                 {"type": "command_execution", "command": "prism query target",
                  "status": "completed", "exit_code": 0}]
        self.assertEqual(rc.successful_own_tool_actions([], calls, "gpt55_prism"), 2)

    def test_sonnet_requires_successful_result_for_its_call(self):
        calls = [{"type": "tool_use", "id": "ok", "name": "mcp__prism__prism"},
                 {"type": "tool_use", "id": "bad", "name": "mcp__prism__prism"}]
        events = [{"message": {"content": [
            {"type": "tool_result", "tool_use_id": "ok", "is_error": False},
            {"type": "tool_result", "tool_use_id": "bad", "is_error": True},
        ]}}]
        self.assertEqual(rc.successful_own_tool_actions(events, calls, "sonnet_prism"), 1)

class MakePrismTemplateOrderTests(unittest.TestCase):
    def test_index_runs_before_init(self):
        """Regression test: `prism init` alone leaves the graph empty
        (filesIndexed/symbolCount/edgeCount == 0) -- `prism index` must run
        first, matching product_impact_suite.py's order."""
        calls = []
        binary = Path("/bin/prism")
        original_run = subprocess.run

        def fake_run(args, **kwargs):
            if args and args[0] == str(binary):
                calls.append(list(args))
                if args[1] == "status":
                    stdout = json.dumps({"filesIndexed": 1, "symbolCount": 1, "edgeCount": 1})
                else:
                    stdout = ""
                return mock.Mock(returncode=0, stdout=stdout, stderr="")
            return original_run(args, **kwargs)

        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            base = root / "templates" / "task1" / "base"
            base.mkdir(parents=True)
            (base / "a.py").write_text("x = 1\n")
            subprocess.run(["git", "init", "-q"], cwd=base, check=True)

            with mock.patch.object(rc.subprocess, "run", side_effect=fake_run):
                rc.make_prism_template(root, binary, "task1", base)

        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(calls[0][:2], [str(binary), "index"])
        self.assertEqual(calls[1][:2], [str(binary), "init"])
        self.assertEqual(calls[2][:2], [str(binary), "status"])

    def test_empty_graph_after_index_and_init_raises(self):
        binary = Path("/bin/prism")
        original_run = subprocess.run

        def fake_run(args, **kwargs):
            if args and args[0] == str(binary):
                if args[1] == "status":
                    stdout = json.dumps({"filesIndexed": 0, "symbolCount": 0, "edgeCount": 0})
                else:
                    stdout = ""
                return mock.Mock(returncode=0, stdout=stdout, stderr="")
            return original_run(args, **kwargs)

        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            base = root / "templates" / "task1" / "base"
            base.mkdir(parents=True)
            (base / "a.py").write_text("x = 1\n")
            subprocess.run(["git", "init", "-q"], cwd=base, check=True)

            with mock.patch.object(rc.subprocess, "run", side_effect=fake_run):
                with self.assertRaises(RuntimeError):
                    rc.make_prism_template(root, binary, "task1", base)


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

    def test_coding_file_change_is_not_a_protocol_violation(self):
        rec = {"allow_source_edits": True}
        rc.audit_calls(rec, [{"type": "file_change"}], "gpt55_prism")
        self.assertEqual(rec["violations"], [])

    def test_read_only_file_change_remains_a_protocol_violation(self):
        rec = {}
        rc.audit_calls(rec, [{"type": "file_change"}], "gpt55_prism")
        self.assertEqual(rec["violations"], ["edit used in read-only cell"])

    def test_duplicate_prism_calls_are_counted(self):
        rec = {}
        calls = [
            {"name": "mcp__prism__lookup", "input": {"name": "Foo"}},
            {"name": "mcp__prism__lookup", "input": {"name": "Foo"}},
        ]
        rc.audit_calls(rec, calls, "sonnet_prism")
        self.assertEqual(rec["duplicate_prism_calls"], 1)


class CrossToolMutualExclusionTests(unittest.TestCase):
    """Generalized audit_calls: a violation is any call to a tool other than
    active_tool(arm)."""

    def test_codegraph_arm_calling_prism_is_a_violation(self):
        rec = {}
        calls = [{"name": "mcp__prism__search", "input": {}}]
        rc.audit_calls(rec, calls, "sonnet_codegraph")
        self.assertTrue(any("Prism" in v for v in rec["violations"]))
        self.assertEqual(rec["own_tool_calls"], [])

    def test_prism_arm_calling_codegraph_is_a_violation(self):
        rec = {}
        calls = [{"name": "mcp__codegraph__explore", "input": {}}]
        rc.audit_calls(rec, calls, "sonnet_prism")
        self.assertTrue(any("CodeGraph" in v for v in rec["violations"]))

    def test_native_arm_calling_codegraph_is_a_violation(self):
        rec = {}
        calls = [{"name": "mcp__codegraph__explore", "input": {}}]
        rc.audit_calls(rec, calls, "sonnet_native")
        self.assertIn("native arm used CodeGraph", rec["violations"])

    def test_codegraph_arm_calling_codegraph_is_not_a_violation(self):
        rec = {}
        calls = [{"name": "mcp__codegraph__explore", "input": {"q": "x"}}]
        rc.audit_calls(rec, calls, "sonnet_codegraph")
        self.assertEqual(rec["violations"], [])
        self.assertEqual(rec["own_tool_calls"], ["mcp__codegraph__explore"])
        self.assertEqual(rec["own_tool"], "codegraph")
        # Legacy field name carries the arm's own-tool call count under the
        # historical "prism_calls" key even though this arm uses codegraph.
        self.assertEqual(rec["prism_calls"], ["mcp__codegraph__explore"])

    def test_codegraph_arm_shelling_out_to_prism_cli_is_a_violation(self):
        rec = {}
        calls = [{"name": "Bash", "input": {"command": "prism search x"}}]
        rc.audit_calls(rec, calls, "sonnet_codegraph")
        self.assertTrue(any("Prism" in v for v in rec["violations"]))

    def test_codex_codegraph_arm_calling_prism_server_is_a_violation(self):
        rec = {}
        calls = [{"type": "mcp_tool_call", "server": "prism", "tool": "prism_search"}]
        rc.audit_calls(rec, calls, "gpt55_codegraph")
        self.assertTrue(any("Prism" in v for v in rec["violations"]))

    def test_codex_codegraph_arm_calling_own_server_is_not_a_violation(self):
        rec = {}
        calls = [{"type": "mcp_tool_call", "server": "codegraph", "tool": "codegraph_explore"}]
        rc.audit_calls(rec, calls, "gpt55_codegraph")
        self.assertEqual(rec["violations"], [])
        self.assertEqual(rec["own_tool_calls"], ["codegraph_explore"])


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


class BuildCommandThinkingDisplayTests(unittest.TestCase):
    """`--thinking-display` is what makes the model's reasoning land in
    stdout.jsonl; without it `claude -p --output-format stream-json`
    returns signature-only thinking blocks."""

    def _sonnet_cmd(self, cfg):
        return rc.build_command(cfg, Path("/run"), Path("/run/evidence/c"),
                                Path("/run/work/c"), "sonnet_native", "fix it",
                                Path("/run/prism-bin"))

    def test_default_requests_summarized_thinking(self):
        cmd = self._sonnet_cmd(rc.AgentConfig())
        self.assertIn("--thinking-display", cmd)
        self.assertEqual(cmd[cmd.index("--thinking-display") + 1], "summarized")

    def test_none_omits_the_flag(self):
        cmd = self._sonnet_cmd(rc.AgentConfig(thinking_display=None))
        self.assertNotIn("--thinking-display", cmd)

    def test_does_not_change_effort_or_thinking_mode(self):
        # Display-only: the flag must not add --thinking/--effort changes, so
        # agent behavior stays comparable with runs that lacked it.
        cmd = self._sonnet_cmd(rc.AgentConfig())
        self.assertNotIn("--thinking", cmd)
        self.assertEqual(cmd[cmd.index("--effort") + 1], "medium")


class SummarizeSonnetThinkingCaptureTests(unittest.TestCase):
    def _summarize(self, events):
        with tempfile.TemporaryDirectory() as tmp:
            rec, _final, _calls = rc.summarize_sonnet(events, Path(tmp))
        return rec

    def test_counts_assistant_thinking_text(self):
        events = [
            {"type": "assistant", "message": {"content": [
                {"type": "thinking", "thinking": "step one", "signature": "s1"}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "thinking", "thinking": "", "signature": "s2"}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "done"}]}},
        ]
        rec = self._summarize(events)
        self.assertEqual(rec["thinking_blocks"], 2)
        self.assertEqual(rec["thinking_chars"], len("step one"))

    def test_signature_only_blocks_report_zero_chars(self):
        # The failure mode the counter exists to expose: thinking happened
        # (blocks present) but the text was stripped.
        events = [{"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "", "signature": "s"}]}}] * 3
        rec = self._summarize(events)
        self.assertEqual(rec["thinking_blocks"], 3)
        self.assertEqual(rec["thinking_chars"], 0)

    def test_ignores_thinking_outside_assistant_events(self):
        events = [{"type": "user", "message": {"content": [
            {"type": "thinking", "thinking": "not the model", "signature": "s"}]}}]
        rec = self._summarize(events)
        self.assertEqual(rec["thinking_blocks"], 0)
        self.assertEqual(rec["thinking_chars"], 0)


class NetworkClassifierTests(unittest.TestCase):
    def test_definite_fetches(self):
        for cmd in (
            "pip download click==8.5.0 --no-deps -d /tmp/x",
            "cd /tmp && pip download click==8.1.4 --no-deps -d /tmp/y",  # compound form
            "pip3 install requests",
            "curl -sI https://example.com | head -1",
            "wget https://example.com/x.tgz",
            "gh pr view 5890 --json files",
            "git clone https://github.com/pallets/click /tmp/c",
            "cd repo && git fetch origin",
            "uv pip install requests",
            "npm install",
        ):
            self.assertEqual(rc.classify_network(cmd), "definite", cmd)

    def test_url_literal_is_only_suspect(self):
        # A URL inside test code proves nothing -- recorded, never a violation.
        cmd = "python - <<'PY'\nProxyManager('https://localhost:1', use_forwarding_for_https=True)\nPY"
        self.assertEqual(rc.classify_network(cmd), "suspect")

    def test_local_commands_are_unflagged(self):
        for cmd in (
            "pip show click", "pip --version", "python -m pytest tests/ -q",
            "python3 -c 'import click; print(click.__file__)'",
            "git diff", "git status", "git log --oneline -3",
            "uv --version", "grep -rn fileno src/",
        ):
            self.assertIsNone(rc.classify_network(cmd), cmd)


class NetworkAuditTests(unittest.TestCase):
    def test_sonnet_shell_fetch_is_a_violation_on_any_arm(self):
        for arm in ("sonnet_native", "sonnet_prism", "sonnet_codegraph"):
            rec = {}
            calls = [{"name": "Bash", "input": {"command": "cd /tmp && pip download click==8.5.0"}}]
            rc.audit_calls(rec, calls, arm)
            self.assertIn("network access via shell", rec["violations"], arm)
            self.assertEqual(len(rec["network_commands"]), 1)

    def test_codex_command_execution_fetch_is_a_violation(self):
        rec = {}
        calls = [{"type": "command_execution", "command": "/bin/zsh -lc 'curl -sI https://example.com'",
                  "status": "completed", "exit_code": 0}]
        rc.audit_calls(rec, calls, "gpt55_native")
        self.assertIn("network access via shell", rec["violations"])

    def test_url_literal_is_recorded_not_violated(self):
        rec = {}
        calls = [{"name": "Bash", "input": {"command":
                  "python - <<'PY'\nProxyManager('https://localhost:1')\nPY"}}]
        rc.audit_calls(rec, calls, "sonnet_native")
        self.assertNotIn("network access via shell", rec["violations"])
        self.assertEqual(rec["network_commands"], [])
        self.assertEqual(len(rec["network_suspects"]), 1)

    def test_clean_cell_has_empty_network_fields(self):
        rec = {}
        calls = [{"name": "Bash", "input": {"command": "python -m pytest tests/test_testing.py -q"}}]
        rc.audit_calls(rec, calls, "sonnet_native")
        self.assertEqual(rec["network_commands"], [])
        self.assertEqual(rec["network_suspects"], [])
        self.assertNotIn("network access via shell", rec["violations"])


class BuildCommandNetworkBlockTests(unittest.TestCase):
    def _sonnet_cmd(self, cfg):
        return rc.build_command(cfg, Path("/run"), Path("/run/evidence/c"),
                                Path("/run/work/c"), "sonnet_native", "fix it",
                                Path("/run/prism-bin"))

    def test_default_denies_shell_fetches_and_web_tools(self):
        cmd = self._sonnet_cmd(rc.AgentConfig())
        self.assertIn("--disallowedTools", cmd)
        deny = cmd[cmd.index("--disallowedTools") + 1]
        for pattern in ("Bash(pip download:*)", "Bash(pip install:*)", "Bash(curl:*)",
                        "Bash(wget:*)", "Bash(git clone:*)", "WebFetch", "WebSearch"):
            self.assertIn(pattern, deny, pattern)

    def test_deny_list_stays_narrow(self):
        # A broad Bash(pip:*) would deny `pip show`/`pip --version`, which
        # legitimate cells use; the probes in swebench_ab.py's history show
        # that breaks runs. Keep the deny list to fetching subcommands.
        deny = rc.AgentConfig().disallowed_tools
        self.assertNotIn("Bash(pip:*)", deny)
        self.assertNotIn("Bash(python", deny)
        self.assertNotIn("Bash(git:*)", deny)

    def test_empty_deny_list_omits_the_flag(self):
        cmd = self._sonnet_cmd(rc.AgentConfig(disallowed_tools=""))
        self.assertNotIn("--disallowedTools", cmd)


class NetworkClassifierEdgeTests(unittest.TestCase):
    def test_heredoc_body_is_not_a_command(self):
        # Text written to a file must not read as a fetch being run.
        cmd = "cat > /tmp/repro.py <<'EOF'\nimport click\n# pip install click\ncurl http://x\nEOF\npython /tmp/repro.py"
        self.assertIsNone(rc.classify_network(cmd))

    def test_command_after_heredoc_still_counts(self):
        cmd = "cat > /tmp/repro.py <<'EOF'\nprint(1)\nEOF\npip download click==8.5.0 -d /tmp/x"
        self.assertEqual(rc.classify_network(cmd), "definite")

    def test_local_editable_install_is_suspect_not_definite(self):
        # The real pr3228 shape: write a repro, then `python -m pip install -e .`
        cmd = "cat > /tmp/clickfoo.py <<'EOF'\nimport click\nEOF\npython -m pip install -e . -q 2>/dev/null\npython /tmp/clickfoo.py"
        self.assertEqual(rc.classify_network(cmd), "suspect")
        for local in ("pip install -e .", "pip install .", "pip install ./vendor/pkg",
                      "pip install --no-deps -e . -q", "uv pip install -e ."):
            self.assertEqual(rc.classify_network(local), "suspect", local)

    def test_index_installs_stay_definite(self):
        for fetch in ("pip install requests", "pip install -q requests",
                      "pip install -r requirements.txt", "python -m pip install click==8.5.0",
                      "uv pip install requests"):
            self.assertEqual(rc.classify_network(fetch), "definite", fetch)

    def test_executed_heredoc_body_is_live_code(self):
        # `python - <<'PY'` runs the body; a fetch inside it is real network
        # use and a URL inside it is a real suspect -- neither may be stripped.
        self.assertEqual(rc.classify_network(
            "python - <<'PY'\nimport subprocess\nsubprocess.run('pip download click', shell=True)\nPY"),
            "definite")
        self.assertEqual(rc.classify_network(
            "python - <<'PY'\nProxyManager('https://localhost:1')\nPY"), "suspect")
        self.assertEqual(rc.classify_network(
            "cat <<'EOF' | python\nprint('https://example.com')\nEOF"), "suspect")
        self.assertEqual(rc.classify_network(
            "bash <<'EOF'\ncurl -sI https://example.com\nEOF"), "definite")

    def test_written_heredoc_body_is_inert_even_via_tee(self):
        self.assertIsNone(rc.classify_network(
            "tee /tmp/notes.md <<'EOF'\nrun: pip install click\nsee https://example.com\nEOF"))


class BuildCommandCodexSandboxTests(unittest.TestCase):
    def test_codex_pins_workspace_write_network_off(self):
        cmd = rc.build_command(rc.AgentConfig(), Path("/run"), Path("/run/evidence/c"),
                               Path("/run/work/c"), "gpt55_native", "fix it",
                               Path("/run/prism-bin"))
        self.assertIn("sandbox_workspace_write.network_access=false", cmd)
        self.assertEqual(cmd[cmd.index("sandbox_workspace_write.network_access=false") - 1], "-c")


if __name__ == "__main__":
    unittest.main()
