
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import unittest
from pathlib import Path
from unittest.mock import patch

import run_e2e


TASK = {"instance_id": "org__repo__pr1", "lang": "go", "repo": "org/repo", "problem_statement": "x"}


class RunCellPersistenceTests(unittest.TestCase):
    def test_scorer_failure_keeps_agent_spend_and_leaves_result_unknown(self):
        meta = {"turns": 9, "cost_usd": 1.25, "session_id": "sid", "api_calls": 5,
                "usage": {"tokens": {"output": 10}, "cache_ttl": {"cache_5m": 0, "cache_1h": 100}}}
        with patch.object(run_e2e, "_worktree", return_value=("repo", Path("/nonexistent/wt"))), \
             patch.object(run_e2e, "_prepare_build_env", return_value={}), \
             patch.object(run_e2e, "_index_graph"), \
             patch.object(run_e2e, "_is_python", return_value=False), \
             patch.object(run_e2e, "_run_cloud", return_value=dict(meta)), \
             patch.object(run_e2e, "_agent_diff", return_value="diff\n"), \
             patch.object(run_e2e, "_save_diff"), \
             patch.object(run_e2e, "_remove_worktree"), \
             patch.object(run_e2e, "_score", side_effect=run_e2e.ScorerRanNoTests("no tests ran")):
            rec = run_e2e.run_cell(TASK, "native", "claude-sonnet-5-5")
        self.assertIsNone(rec["resolved"])
        self.assertEqual(rec["cost_usd"], 1.25)
        self.assertEqual(rec["usage"]["cache_ttl"]["cache_1h"], 100)
        self.assertEqual(rec["api_calls"], 5)
        self.assertIn("ScorerRanNoTests", rec["error"])
        self.assertIn("ScorerRanNoTests", rec["score"]["scorer_error"])

    def test_arm_order_is_seeded_and_not_always_the_same(self):
        arms = ["native", "prism_init"]
        ids = [f"org__repo__pr{i}" for i in range(40)]
        orders = [run_e2e.arm_order("s", i, arms) for i in ids]
        self.assertEqual(orders, [run_e2e.arm_order("s", i, arms) for i in ids])
        self.assertTrue(all(sorted(o) == sorted(arms) for o in orders))
        firsts = {o[0] for o in orders}
        self.assertEqual(firsts, set(arms))
        self.assertNotEqual(orders, [run_e2e.arm_order("t", i, arms) for i in ids])


if __name__ == "__main__":
    unittest.main()
