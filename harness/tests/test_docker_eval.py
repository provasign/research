from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)


import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import docker_eval


class DockerPreflightTests(unittest.TestCase):
    @mock.patch("docker_eval.subprocess.run")
    def test_require_docker_accepts_running_daemon(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, stdout="29.4.3\n", stderr="")

        docker_eval._require_docker()

    @mock.patch("docker_eval.subprocess.run")
    def test_require_docker_reports_daemon_error(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="Cannot connect to the Docker daemon"
        )

        with self.assertRaisesRegex(RuntimeError, "Docker is unavailable"):
            docker_eval._require_docker()


class CollectionDetectionTests(unittest.TestCase):
    def test_collection_error_is_distinct_from_empty_run(self) -> None:
        self.assertIsNotNone(
            docker_eval.COLLECTION_ERROR_RE.search(
                "collected 25 items / 1 error\nERROR tests/test_example.py"
            )
        )
        self.assertIsNone(docker_eval.COLLECTION_ERROR_RE.search("no tests ran"))

    def test_pytest_run_keeps_collection_status_separate(self) -> None:
        run = docker_eval.PytestRun({"tests/test_ok.py::test_ok": "PASSED"}, True)

        self.assertEqual(run.outcomes["tests/test_ok.py::test_ok"], "PASSED")
        self.assertTrue(run.collection_failed)


if __name__ == "__main__":
    unittest.main()
