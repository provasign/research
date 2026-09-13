"""Unit tests for harness/lib/suites.py: suite/task discovery from
harness/tasks/<suite>/ and SUITE.json metadata."""
import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import suites  # noqa: E402


class RealSuiteTests(unittest.TestCase):
    """Exercises the real harness/tasks/e2e and harness/tasks/manual
    SUITE.json files this change adds, so a future edit to either can't
    silently break discovery."""

    def test_e2e_suite_is_discovered_with_kind_and_pilot(self):
        self.assertIn("e2e", suites.list_suites())
        self.assertEqual(suites.suite_kind("e2e"), "coding")
        ids = {t.id for t in suites.list_tasks("e2e")}
        self.assertEqual(len(ids), 8)
        self.assertEqual(set(suites.pilot_task_ids("e2e")),
                         {"pallets__click__pr3244", "urllib3__urllib3__pr3786"})

    def test_manual_suite_is_discovered_with_kind(self):
        self.assertEqual(suites.suite_kind("manual"), "impact")
        ids = {t.id for t in suites.list_tasks("manual")}
        self.assertIn("jackson-jsonnode-get", ids)

    def test_phases_partition_e2e_tasks(self):
        pilot = set(suites.task_ids_for_phase("e2e", "pilot"))
        remaining = set(suites.task_ids_for_phase("e2e", "remaining"))
        full = set(suites.task_ids_for_phase("e2e", "full"))
        self.assertEqual(pilot | remaining, full)
        self.assertEqual(pilot & remaining, set())


class SyntheticSuiteTests(unittest.TestCase):
    def test_suite_without_suite_json_scans_directory(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "demo").mkdir()
            (root / "demo/task-a.json").write_text("{}")
            (root / "demo/task-b.json").write_text("{}")
            (root / "demo/manifest.smoke.json").write_text("{}")

            ids = {t.id for t in suites.list_tasks("demo", tasks_root=root)}

        self.assertEqual(ids, {"task-a", "task-b"})

    def test_suite_json_pilot_and_category_metadata(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "demo").mkdir()
            (root / "demo/SUITE.json").write_text(json.dumps({
                "kind": "coding",
                "tasks": {
                    "a": {"category": "bugfix", "pilot": True},
                    "b": {"category": "feature", "pilot": False},
                },
            }))

            refs = {t.id: t for t in suites.list_tasks("demo", tasks_root=root)}
            kind = suites.suite_kind("demo", tasks_root=root)

        self.assertEqual(refs["a"].category, "bugfix")
        self.assertTrue(refs["a"].pilot)
        self.assertFalse(refs["b"].pilot)
        self.assertEqual(kind, "coding")

    def test_missing_suite_returns_empty(self):
        with tempfile.TemporaryDirectory() as value:
            self.assertEqual(suites.list_tasks("nope", tasks_root=Path(value)), [])


if __name__ == "__main__":
    unittest.main()
