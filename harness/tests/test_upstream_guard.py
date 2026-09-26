"""hooks/upstream_guard.py: deny fetching the upstream repo, allow code text."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
import upstream_guard as ug  # noqa: E402

BLOCKED = [
    # the two real leaks (sweep50, 2026-09-26)
    "gh pr diff 3466 --repo pallets/click",
    "curl -s https://github.com/psf/requests/pull/7315.diff",
    "curl -sL https://patch-diff.githubusercontent.com/raw/psf/requests/pull/7315.diff | head -100",
    "cd /tmp && wget -q https://codeload.github.com/pallets/click/zip/refs/heads/main",
    "curl -s 'https://api.github.com/repos/FasterXML/jackson-databind/commits?sha=3.x'",
    "gh api repos/honojs/hono/pulls/5164/files",
    "gh issue view 5958 -R FasterXML/jackson-databind",
    "gh -R pallets/click pr view 3466",
    "git clone --depth 1 https://github.com/colinhacks/zod /tmp/zod",
    "git -C /tmp/x fetch https://github.com/gin-gonic/gin.git master",
    "go get github.com/urfave/cli/v3@main",
    "pip install git+https://github.com/pallets/click.git",
    "python3 -c \"import urllib.request as u; print(u.urlopen('https://github.com/a/b/pull/1.diff').read())\"",
    "node -e \"fetch('https://raw.githubusercontent.com/h3js/h3/main/src/index.ts').then(r=>r.text())\"",
    "curl https://gitlab.com/x/y/-/merge_requests/3.diff",
]

ALLOWED = [
    # Go source written through a heredoc must stay allowed
    "cat > /tmp/repro/main.go <<'EOF'\npackage main\n\nimport (\n\t\"net/http\"\n\t"
    "\"github.com/gin-gonic/gin\"\n)\n\nfunc main() { http.Get(\"https://github.com/x\") }\nEOF\n"
    "cd /tmp/repro && go run .",
    "cat <<-EOF > go.mod\n\tmodule x\n\trequire github.com/urfave/cli/v3 v3.0.0\n\tEOF",
    "echo 'import \"github.com/labstack/echo/v4\"' > x.go",
    "grep -rn 'github.com/go-chi/chi' --include=*.go .",
    "go build ./... && go test ./... -run TestRouter",
    "mvn -q -o -DskipTests compile",
    "curl -s http://localhost:8080/hello",
    "git log --oneline -5 && git diff",
    "gh --version",
    "pnpm install --offline && pnpm vitest run src/x.test.ts",
    "sed -n '1,20p' go.mod  # github.com/foo/bar",
]


class UpstreamGuardTests(unittest.TestCase):
    def test_blocks_real_and_variant_fetches(self):
        for cmd in BLOCKED:
            with self.subTest(cmd=cmd):
                self.assertTrue(ug.bash_blocked(cmd))

    def test_allows_code_text_and_local_commands(self):
        for cmd in ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertFalse(ug.bash_blocked(cmd))

    def test_webfetch(self):
        self.assertTrue(ug.url_blocked("https://github.com/pallets/click/pull/3466"))
        self.assertTrue(ug.url_blocked("https://raw.githubusercontent.com/a/b/main/x"))
        self.assertFalse(ug.url_blocked("https://go.dev/play/p/abc123"))
        self.assertFalse(ug.url_blocked("https://notgithub.com.example.org/x"))

    def test_hook_protocol(self):
        def run(payload):
            r = subprocess.run([sys.executable, str(HOOKS / "upstream_guard.py")],
                               input=json.dumps(payload), capture_output=True, text=True)
            return r.stdout.strip()
        out = json.loads(run({"tool_name": "Bash", "tool_input": {"command": BLOCKED[0]}}))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("off-limits", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(run({"tool_name": "Bash", "tool_input": {"command": "ls"}}), "")
        self.assertEqual(run({"tool_name": "WebFetch", "tool_input": {"url": "https://go.dev/x"}}), "")


if __name__ == "__main__":
    unittest.main()
