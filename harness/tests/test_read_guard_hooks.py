"""hooks/prism_read_tracker.py + prism_read_guard.py, run as the hooks run:
JSON on stdin, cwd/CLAUDE_PROJECT_DIR = the worktree."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
HOOKS = HARNESS / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(HARNESS / "runners"))
import prism_read_tracker as tracker  # noqa: E402

REL = "src/main/java/tools/jackson/databind/deser/bean/BeanDeserializer.java"
SID = "sess-1"


class ReadGuardHookTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.abs = str(self.dir / REL)

    def hook(self, script, payload):
        payload.setdefault("session_id", SID)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.dir))
        r = subprocess.run([sys.executable, str(HOOKS / script)], input=json.dumps(payload),
                           capture_output=True, text=True, cwd=self.dir, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def deliver(self, frm=1406, to=1480, f=REL):
        self.hook("prism_read_tracker.py", {"tool_name": "mcp__prism__prism",
                                            "tool_input": {"op": "read", "args": {"file": f, "from": frm, "to": to}}})

    def read_denied(self, offset=1406, limit=75, **kw):
        out = self.hook("prism_read_guard.py", {"tool_name": "Read", "tool_input": {
            "file_path": self.abs, "offset": offset, "limit": limit}, **kw})
        return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_delivered_range_is_denied(self):
        self.deliver()
        self.assertTrue(self.read_denied())
        self.assertFalse(self.read_denied(offset=1481, limit=100))

    def test_edit_of_that_file_forgets_its_ranges(self):
        # jackson pr5959: edit, then Read of the delivered range was denied
        self.deliver()
        self.deliver(1, 50, "src/main/java/Other.java")
        self.hook("prism_read_tracker.py", {"tool_name": "Edit", "tool_input": {
            "file_path": self.abs, "old_string": "a", "new_string": "b"}})
        self.assertFalse(self.read_denied())
        kept = json.loads((self.dir / ".prism-read-tracker.json").read_text())
        self.assertEqual([t["file"] for t in kept], ["src/main/java/Other.java"])

    def test_write_multiedit_notebookedit_forget_their_file(self):
        for tool, key in (("Write", "file_path"), ("MultiEdit", "file_path"),
                          ("NotebookEdit", "notebook_path")):
            with self.subTest(tool=tool):
                self.deliver()
                self.hook("prism_read_tracker.py", {"tool_name": tool, "tool_input": {key: self.abs}})
                self.assertFalse(self.read_denied())

    def test_edit_of_another_file_keeps_ranges(self):
        self.deliver()
        self.hook("prism_read_tracker.py", {"tool_name": "Edit", "tool_input": {
            "file_path": str(self.dir / "src/main/java/Other.java")}})
        self.assertTrue(self.read_denied())

    def test_file_rewriting_bash_clears_all(self):
        for cmd in ("git stash && git stash pop", "git checkout -- .", "git -C . reset --hard",
                    "git apply /tmp/x.patch", "patch -p1 < /tmp/fix.diff", "sed -i '' 's/a/b/' x.java",
                    "mv /tmp/Bean.java " + REL, "cp /tmp/Bean.java " + REL,
                    "python3 - <<'EOF'\nopen('x.java','w').write(s)\nEOF",
                    "cat /tmp/new > " + REL, "gofmt -w ."):
            with self.subTest(cmd=cmd):
                self.deliver()
                self.hook("prism_read_tracker.py", {"tool_name": "Bash", "tool_input": {"command": cmd}})
                self.assertFalse(self.read_denied())

    def test_read_only_bash_keeps_ranges(self):
        self.deliver()
        for cmd in ("mvn -q -o test -Dtest=X 2>&1 | tail -50", "git diff", "git status",
                    "grep -n foo " + REL, "mvn test > /tmp/log.txt", "ls >/dev/null",
                    "pnpm install --offline"):
            self.hook("prism_read_tracker.py", {"tool_name": "Bash", "tool_input": {"command": cmd}})
        self.assertTrue(self.read_denied())

    def test_ranges_only_read_is_tracked(self):
        self.hook("prism_read_tracker.py", {"tool_name": "mcp__prism__prism", "tool_input": {
            "op": "read", "args": {"ranges": [{"file": REL, "from": 1406, "to": 1480}]}}})
        self.assertTrue(self.read_denied())

    def test_other_sessions_ranges_are_ignored(self):
        self.deliver()
        self.assertFalse(self.read_denied(session_id="sess-2"))

    def test_same_file_matching(self):
        self.assertTrue(tracker._same_file("/w/" + REL, REL))
        self.assertTrue(tracker._same_file("/w/" + REL, "./" + REL))
        self.assertFalse(tracker._same_file("/w/src/Other.java", REL))
        self.assertFalse(tracker._same_file("/w/xBeanDeserializer.java", "BeanDeserializer.java"))


class InstallTests(unittest.TestCase):
    def test_installed_hooks_cover_edits_and_bash(self):
        sys.argv = sys.argv[:1]
        import run_e2e
        wt = Path(tempfile.mkdtemp())
        run_e2e._install_read_guard_hook(wt)
        s = json.loads((wt / ".claude/settings.json").read_text())
        post = {e["matcher"] for e in s["hooks"]["PostToolUse"]}
        self.assertIn("mcp__prism__prism", post)
        self.assertIn("Edit|Write|MultiEdit|NotebookEdit|Bash", post)
        self.assertEqual([e["matcher"] for e in s["hooks"]["PreToolUse"]], ["Read"])


if __name__ == "__main__":
    unittest.main()
