"""Unit tests for harness/bench.py: arm construction, model overrides, and
the results index -- everything testable without live claude/codex/docker."""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bench  # noqa: E402


class ArmsForTests(unittest.TestCase):
    def test_native_prism_matches_legacy_four_arm_order(self):
        # Same order the legacy `--prism both` (tools=["native", "prism"])
        # produced -- the manifest-parity contract with coding_suite.py's
        # historical output.
        self.assertEqual(
            bench.arms_for(["claude", "codex"], ["native", "prism"]),
            ["sonnet_native", "gpt55_native", "sonnet_prism", "gpt55_prism"],
        )

    def test_prism_only_tool(self):
        self.assertEqual(bench.arms_for(["claude"], ["prism"]), ["sonnet_prism"])

    def test_native_only_tool(self):
        self.assertEqual(bench.arms_for(["claude", "codex"], ["native"]),
                         ["sonnet_native", "gpt55_native"])

    def test_single_agent_smoke_test(self):
        self.assertEqual(bench.arms_for(["claude"], ["prism"]), ["sonnet_prism"])

    def test_codegraph_only_tool(self):
        self.assertEqual(bench.arms_for(["claude"], ["codegraph"]), ["sonnet_codegraph"])

    def test_three_tools_cross_product(self):
        self.assertEqual(
            bench.arms_for(["claude", "codex"], ["native", "prism", "codegraph"]),
            ["sonnet_native", "gpt55_native", "sonnet_prism", "gpt55_prism",
             "sonnet_codegraph", "gpt55_codegraph"],
        )


class PrismFlagToToolsTests(unittest.TestCase):
    def test_both_maps_to_native_and_prism(self):
        self.assertEqual(bench.prism_flag_to_tools("both"), ["native", "prism"])

    def test_on_maps_to_prism_only(self):
        self.assertEqual(bench.prism_flag_to_tools("on"), ["prism"])

    def test_off_maps_to_native_only(self):
        self.assertEqual(bench.prism_flag_to_tools("off"), ["native"])


class ParseKvTests(unittest.TestCase):
    def test_defaults_when_unset(self):
        self.assertEqual(bench.parse_kv(None, bench.DEFAULT_MODELS), bench.DEFAULT_MODELS)

    def test_overrides_one_model(self):
        result = bench.parse_kv("claude=claude-opus-5", bench.DEFAULT_MODELS)
        self.assertEqual(result["claude"], "claude-opus-5")
        self.assertEqual(result["codex"], bench.DEFAULT_MODELS["codex"])

    def test_overrides_both_models(self):
        result = bench.parse_kv("claude=a,codex=b", bench.DEFAULT_MODELS)
        self.assertEqual(result, {"claude": "a", "codex": "b"})


class RunStatusTests(unittest.TestCase):
    def test_rejected_model_does_not_produce_a_complete_run(self):
        rows = [{"audited_valid": False, "agent_error": True,
                 "score": {"resolved": False}}]
        self.assertEqual(bench.run_status(rows, 1), "audit_incomplete")

    def test_all_valid_scored_cells_complete(self):
        rows = [{"audited_valid": True, "score": {"resolved": False}}]
        self.assertEqual(bench.run_status(rows, 1), "complete")

    def test_missing_cell_or_scoring_error_is_incomplete(self):
        rows = [{"audited_valid": True, "score": {"harness_error": "docker failed"}}]
        self.assertEqual(bench.run_status(rows, 1), "audit_incomplete")
        self.assertEqual(bench.run_status(rows, 2), "audit_incomplete")
        self.assertEqual(bench.run_status([{"audited_valid": True}], 1),
                         "audit_incomplete")


class IndexTests(unittest.TestCase):
    def _write_run(self, root: Path, name: str, cell_id: str, arm: str) -> None:
        run_dir = root / name
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(json.dumps({
            "study": "bench-e2e", "models": {"sonnet": "claude-sonnet-5", "gpt": "gpt-5.5"},
            "started_utc": "2026-09-12T00:00:00Z",
        }))
        (run_dir / "summary.json").write_text(json.dumps({"rows": [{
            "cell_id": cell_id, "task": "demo-task", "arm": arm, "trial": 1,
            "total_tokens": 1000, "turns": 3, "wall_s": 12.5, "cost_usd": 0.05,
            "resolved": True,
        }]}))

    def test_index_is_idempotent(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            self._write_run(root, "run1", "demo-task.sonnet_prism", "sonnet_prism")
            out = root / "index.jsonl"
            args = argparse.Namespace(results_dir=str(root), out=str(out))

            bench.cmd_index(args)
            first = out.read_text()
            bench.cmd_index(args)
            second = out.read_text()

        self.assertEqual(first, second)
        rows = [json.loads(line) for line in first.splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent"], "claude")
        self.assertEqual(rows[0]["prism"], "on")
        self.assertEqual(rows[0]["tool"], "prism")

    def test_index_codegraph_arm_gets_tool_field_and_legacy_prism_off(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            self._write_run(root, "run1", "demo-task.sonnet_codegraph", "sonnet_codegraph")
            out = root / "index.jsonl"
            bench.cmd_index(argparse.Namespace(results_dir=str(root), out=str(out)))
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tool"], "codegraph")
        self.assertEqual(rows[0]["prism"], "off")

    def test_index_dedupes_by_run_dir_and_cell_id(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value).resolve()
            self._write_run(root, "run1", "demo-task.gpt55_native", "gpt55_native")
            self._write_run(root, "run2", "demo-task.gpt55_native", "gpt55_native")
            out = root / "index.jsonl"
            bench.cmd_index(argparse.Namespace(results_dir=str(root), out=str(out)))

            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(len(rows), 2)
        self.assertEqual({r["run_dir"] for r in rows}, {str(root / "run1"), str(root / "run2")})


if __name__ == "__main__":
    unittest.main()
