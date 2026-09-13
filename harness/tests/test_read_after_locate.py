
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from read_after_locate import analyze


def use(mid, tid, name, args):
    return {"type": "assistant", "message": {"id": mid, "content": [
        {"type": "tool_use", "id": tid, "name": name, "input": args}]}}


def result(tid, text):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": text}]}}


class ReadAfterLocateTests(unittest.TestCase):
    def analyze(self, events):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"trace.jsonl"
            p.write_text("\n".join(json.dumps(e) for e in events))
            return analyze(p)

    def test_read_does_not_credit_its_own_result_and_stream_duplicates(self):
        read = use("m1", "t1", "mcp__prism__prism_read", {"file": "main.go", "offset": 1, "limit": 2})
        body = result("t1", "// main.go\n1\tone\n2\ttwo\n")
        got = self.analyze([read, read, body, body,
            use("m2", "t2", "Read", {"file_path": "/repo/main.go", "offset": 1, "limit": 2}),
            result("t2", "\u00e9")])
        self.assertEqual(got["turns"], 2)
        self.assertEqual(got["reads"], 2)
        self.assertEqual([r["kind"] for r in got["detail"]], ["cold", "duplicate"])
        self.assertEqual(got["detail"][1]["bytes"], 2)
        self.assertEqual(got["detail"][1]["tool_use_id"], "t2")

    def test_partial_window_cannot_prove_whole_file_read_duplicate(self):
        got = self.analyze([
            use("m1", "t1", "mcp__prism__prism_lookup", {"name": "Foo"}),
            result("t1", "// main.go\n4\tfunc Foo() {}\n"),
            use("m2", "t2", "Read", {"file_path": "/repo/main.go"}),
            result("t2", "whole file")])
        self.assertEqual(got["detail"][0]["kind"], "located")

    def test_edit_invalidates_old_lines_before_partial_redelivery(self):
        got = self.analyze([
            use("m1", "t1", "mcp__prism__prism_lookup", {"name": "Foo"}),
            result("t1", "// main.go\n1\tone\n2\ttwo\n"),
            use("m2", "t2", "Edit", {"file_path": "/repo/main.go"}),
            result("t2", "edited"),
            use("m3", "t3", "mcp__prism__prism_lookup", {"name": "Foo"}),
            result("t3", "// main.go\n2\tchanged\n"),
            use("m4", "t4", "Read", {"file_path": "/repo/main.go", "offset": 1, "limit": 2}),
            result("t4", "new file")])
        self.assertEqual(got["detail"][0]["kind"], "located")

    def test_basename_suffix_is_not_file_identity(self):
        got = self.analyze([
            use("m1", "t1", "mcp__prism__prism_search", {"query": "Foo"}),
            result("t1", "main.go:1: Foo"),
            use("m2", "t2", "Read", {"file_path": "/repo/domain.go"}),
            result("t2", "different file")])
        self.assertEqual(got["detail"][0]["kind"], "cold")

    def test_search_context_is_delivered_source_and_compaction_invalidates_it(self):
        events = [use("m1", "t1", "mcp__prism__prism_search", {"query": "Foo"}),
                  result("t1", "// root: /repo\nmain.go:\n  1- before\n  2: Foo\n  3- after\n")]
        read = [use("m2", "t2", "Read", {"file_path": "/repo/main.go", "offset": 1, "limit": 3}),
                result("t2", "source")]
        self.assertEqual(self.analyze(events + read)["detail"][0]["kind"], "duplicate")
        compact = {"type": "system", "subtype": "compact_boundary"}
        self.assertEqual(self.analyze(events + [compact] + read)["detail"][0]["kind"], "located")

    def test_shell_uncertainty_does_not_turn_location_into_a_confirmed_edit(self):
        for command in ("rg Foo main.go", "./rewrite.sh", "python3 -c 'run_hidden_edits()'"):
            events = [use("m1", "t1", "mcp__prism__prism_search", {"query": "Foo"}),
                      result("t1", "main.go:1: Foo"),
                      use("m2", "t2", "Bash", {"command": command}), result("t2", "done"),
                      use("m3", "t3", "Read", {"file_path": "/repo/main.go", "offset": 1, "limit": 1}),
                      result("t3", "source")]
            got = self.analyze(events)
            read = got["detail"][0]
            self.assertEqual(read["kind"], "located")
            self.assertEqual(read["freshness"], "unknown")
            self.assertEqual(got["located_then_read"], {"reads": 1, "bytes": 6})
            self.assertNotIn("duplicate", got["by_kind"])
            self.assertNotIn("reread", got["by_kind"])

    def test_successful_edit_is_reread_but_failed_edit_is_only_uncertain(self):
        for failed in (False, True):
            edited = result("t2", "edit result")
            edited["message"]["content"][0]["is_error"] = failed
            got = self.analyze([
                use("m1", "t1", "mcp__prism__prism_lookup", {"name": "Foo"}),
                result("t1", "// main.go\n1\tFoo\n"),
                use("m2", "t2", "Edit", {"file_path": "/repo/main.go"}), edited,
                use("m3", "t3", "Read", {"file_path": "/repo/main.go", "offset": 1, "limit": 1}),
                result("t3", "source")])
            self.assertEqual(got["detail"][0]["kind"], "located" if failed else "reread")
            self.assertEqual(got["detail"][0]["freshness"], "unknown" if failed else "changed")

    def test_fresh_source_after_shell_restores_range_coverage(self):
        got = self.analyze([
            use("m1", "t1", "mcp__prism__prism_search", {"query": "Foo"}),
            result("t1", "main.go:1: Foo"),
            use("m2", "t2", "Bash", {"command": "./rewrite.sh"}), result("t2", "done"),
            use("m3", "t3", "mcp__prism__prism_lookup", {"name": "Foo"}),
            result("t3", "// main.go\n1\tnew Foo\n"),
            use("m4", "t4", "Read", {"file_path": "/repo/main.go", "offset": 1, "limit": 1}),
            result("t4", "source")])
        self.assertEqual(got["detail"][0]["kind"], "duplicate")
        self.assertEqual(got["detail"][0]["freshness"], "no_observed_change")


if __name__ == "__main__":
    unittest.main()
