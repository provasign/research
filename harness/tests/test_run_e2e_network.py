"""A session that died on an unreachable API is retried, never scored."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))
sys.argv = sys.argv[:1]
import run_e2e  # noqa: E402

# Final stdout of the pr6012 prism cell that clamshell sleep killed (2026-09-26).
DEAD = ('{"type":"result","subtype":"success","is_error":true,"num_turns":1,'
        '"result":"API Error: Can\'t reach the API server — check your internet or DNS (ENOTFOUND)"}').lower()


class NetworkDownTests(unittest.TestCase):
    def test_unreachable_api_is_network_down(self):
        self.assertTrue(run_e2e._network_down(0, DEAD))
        self.assertTrue(run_e2e._network_down(1, "error: getaddrinfo enotfound api.anthropic.com"))

    def test_finished_session_mentioning_network_words_is_not(self):
        ok = '{"type":"result","is_error":false,"result":"fixed the econnreset retry in client.py"}'.lower()
        self.assertFalse(run_e2e._network_down(0, ok))

    def test_network_down_is_retried_like_a_rate_limit(self):
        self.assertTrue(issubclass(run_e2e.NetworkDown, run_e2e.RateLimited))


if __name__ == "__main__":
    unittest.main()
