"""Every arm's claude -p carries the upstream_guard hook and an unauthenticated gh."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))
sys.argv = sys.argv[:1]
import run_e2e  # noqa: E402

TASK = {"instance_id": "x__y__pr1", "lang": "go", "repo": "none/none", "base_commit": "0" * 40,
        "problem_statement": "bug"}


class UpstreamGuardWiringTests(unittest.TestCase):
    def cmd_and_env(self, arm):
        wt = Path(tempfile.mkdtemp())
        (wt / ".mcp.json").write_text("{}")
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"], seen["env"] = cmd, kw["env"]
            return mock.Mock(returncode=0, stdout="{}", stderr="")
        with mock.patch.object(run_e2e.subprocess, "run", fake_run), \
                mock.patch.object(run_e2e, "_tool_trace_for", lambda wt: {}), \
                mock.patch.dict(os.environ, {"GH_TOKEN": "t", "GITHUB_TOKEN": "t"}):
            run_e2e._run_cloud("sonnet", arm, wt, TASK)
        return seen["cmd"], seen["env"]

    def test_both_arms_get_the_same_hook(self):
        settings = []
        for arm in ("baseline", "prism_init"):
            cmd, env = self.cmd_and_env(arm)
            s = json.loads(cmd[cmd.index("--settings") + 1])
            (entry,) = s["hooks"]["PreToolUse"]
            self.assertEqual(entry["matcher"], "Bash|WebFetch")
            self.assertTrue(entry["hooks"][0]["command"].endswith("hooks/upstream_guard.py"))
            self.assertTrue(Path(entry["hooks"][0]["command"].split(" ", 1)[1]).exists())
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertTrue(Path(env["GH_CONFIG_DIR"]).is_dir())
            self.assertEqual(os.listdir(env["GH_CONFIG_DIR"]), [])
            settings.append(s)
        self.assertEqual(settings[0], settings[1])


if __name__ == "__main__":
    unittest.main()
