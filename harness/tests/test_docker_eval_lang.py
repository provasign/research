"""Unit tests for scoring/docker_eval_lang.py's pure parsing functions --
the Go/Rust/JS runners this session added alongside the pytest path.
No Docker required: these test the text/JSON -> outcomes mapping only.
See scoring/docker_eval_lang.py's module docstring for what these back.
"""
from __future__ import annotations

import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
for _d in (HARNESS, HARNESS / "scoring"):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

import docker_eval_lang as del_  # noqa: E402


def test_parse_go_json_tracks_last_action_per_test():
    out = (
        '{"Action":"run","Test":"TestFoo"}\n'
        '{"Action":"pass","Test":"TestFoo"}\n'
        '{"Action":"run","Test":"TestBar"}\n'
        '{"Action":"fail","Test":"TestBar"}\n'
        '{"Action":"output","Test":"TestBar","Output":"    --- FAIL\\n"}\n'
    )
    run = del_._parse_go_json(out)
    assert run.outcomes == {"TestFoo": "PASSED", "TestBar": "FAILED"}
    assert not run.collection_failed


def test_parse_go_json_no_events_is_collection_failed():
    run = del_._parse_go_json("go: cannot find main module\n")
    assert run.outcomes == {}
    assert run.collection_failed


def test_parse_cargo_output_maps_ok_failed_ignored():
    out = (
        "running 3 tests\n"
        "test tests::a ... ok\n"
        "test tests::b ... FAILED\n"
        "test tests::c ... ignored\n"
        "test result: FAILED. 1 passed; 1 failed; 1 ignored\n"
    )
    run = del_._parse_cargo_output(out)
    assert run.outcomes == {"tests::a": "PASSED", "tests::b": "FAILED", "tests::c": "SKIPPED"}
    assert not run.collection_failed


def test_parse_cargo_output_build_failure_is_collection_failed():
    out = "error[E0433]: failed to resolve: use of undeclared crate\n"
    run = del_._parse_cargo_output(out)
    assert run.outcomes == {}
    assert run.collection_failed


def test_parse_cargo_output_no_tests_no_error_is_not_collection_failed():
    # An empty but successful run (no matching tests) is not a build
    # failure; only cargo's own error lines mean that.
    run = del_._parse_cargo_output("running 0 tests\ntest result: ok. 0 passed\n")
    assert run.outcomes == {}
    assert not run.collection_failed


def test_parse_jest_report_strips_container_prefix_and_keeps_file_level_id():
    report = {
        "testResults": [
            {
                "name": "/w/tests/generators/utils/parse.tests.ts",
                "assertionResults": [
                    {"title": "Base64 in CSS", "status": "passed"},
                    {"title": "Empty config", "status": "failed"},
                ],
            }
        ]
    }
    outcomes = del_._parse_jest_report(report)
    assert outcomes["tests/generators/utils/parse.tests.ts:Base64 in CSS"] == "PASSED"
    assert outcomes["tests/generators/utils/parse.tests.ts:Empty config"] == "FAILED"
    # File-level id keeps the FIRST assertion's status (Multi-SWE-bench's
    # own p2p_tests carries these bare-path ids for some instances).
    assert outcomes["tests/generators/utils/parse.tests.ts"] == "PASSED"


def test_parse_jest_report_maps_pending_and_unknown_status():
    report = {"testResults": [{"name": "/w/x.ts",
              "assertionResults": [{"title": "a", "status": "pending"},
                                   {"title": "b", "status": "todo"}]}]}
    outcomes = del_._parse_jest_report(report)
    assert outcomes["x.ts:a"] == "SKIPPED"
    assert outcomes["x.ts:b"] == "ERROR"


def test_nearest_jest_config_walks_up_to_per_directory_config(tmp_path):
    # Reproduces darkreader#7241: base commit predates the later
    # tests/unit/jest.config.mjs layout and still uses a config next to
    # each test directory.
    (tmp_path / "tests" / "generators" / "utils").mkdir(parents=True)
    (tmp_path / "tests" / "generators" / "utils" / "jest.config.js").write_text("module.exports = {}")
    found = del_._nearest_jest_config(tmp_path, "tests/generators/utils/parse.tests.ts")
    assert found == "tests/generators/utils/jest.config.js"


def test_nearest_jest_config_returns_none_when_absent(tmp_path):
    (tmp_path / "tests").mkdir()
    assert del_._nearest_jest_config(tmp_path, "tests/x.ts") is None


def test_changed_test_files_parses_diff_headers():
    patch = (
        "diff --git a/tests/a.ts b/tests/a.ts\n"
        "index 1234567..89abcde 100644\n"
        "--- a/tests/a.ts\n"
        "+++ b/tests/a.ts\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/tests/dir/b.ts b/tests/dir/b.ts\n"
        "--- a/tests/dir/b.ts\n"
        "+++ b/tests/dir/b.ts\n"
    )
    assert del_._changed_test_files(patch) == ["tests/a.ts", "tests/dir/b.ts"]


def test_runners_registry_covers_go_rust_ts_js():
    assert set(del_.RUNNERS) == {"go", "rust", "ts", "js"}
    assert del_.NEEDS_TEST_PATCH == {"ts", "js"}
