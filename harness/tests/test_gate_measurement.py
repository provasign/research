import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ab_gate as gate
from schema import Site, Task


def cell(**changes):
    return {"invocation_id": "fixture", "recall": 1.0, "precision": 1.0, "turns": 3,
            "cost_usd": 1.0, "tokens_request": 60, "tokens_in": 40,
            "tokens_out": 4, "scorer_version": gate.SCORER_VERSION, **changes}


class GateMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = Task("test", str(self.root), "go", "HEAD", "local", "impact", "find Foo", [Site("main.go", "Foo")])

    def main(self, rows, tasks=None, loaded=None):
        args = ["ab_gate.py", "--baseline", "base", "--candidate", "cand", "--out", str(self.root/"out"), "--require-cheaper"]
        output = io.StringIO()
        with patch.object(sys, "argv", args), patch.object(gate, "TASKS", tasks or ["one"]), \
                patch.object(gate.Task, "load", side_effect=loaded or [self.task]), \
                patch.object(gate, "binary_sha", side_effect=["b", "c"]), \
                patch.object(gate, "arm_for", side_effect=["base", "cand"]), \
                patch.object(gate, "run_cell", side_effect=rows) as run, contextlib.redirect_stdout(output):
            return gate.main(), output.getvalue(), run.call_args_list

    def test_unknown_cost_and_skipped_tasks_cannot_pass(self):
        rc, text, _ = self.main([cell(), cell(cost_usd=None)])
        self.assertEqual(rc, 2, text)
        self.assertNotIn("PASS", text)
        missing = replace(self.task, repo=str(self.root/"absent"))
        rc, text, _ = self.main([cell(), cell(cost_usd=.5)], ["one", "two"], [self.task, missing])
        self.assertEqual(rc, 2, text)
        self.assertIn("1/2", text)

    def test_retries_count_first_cost_and_tokens_and_fail_when_still_broken(self):
        retry = cell(cost_usd=.6, attempts=[cell(cost_usd=.6), cell(cost_usd=.6)])
        rc, text, calls = self.main([cell(), cell(recall=.5), retry])
        self.assertEqual(rc, 1, text)  # total 1.2, not .6, so not cheaper
        self.assertTrue(calls[-1].kwargs["fresh"])
        self.assertIn("request tokens +100%", text)
        rc, text, _ = self.main([cell(), cell(recall=.5), cell(recall=.5)])
        self.assertEqual(rc, 1, text)
        self.assertIn("reproduced", text)

    def test_equal_quality_cheaper_complete_bed_passes(self):
        rc, text, _ = self.main([cell(), cell(cost_usd=.5)])
        self.assertEqual(rc, 0, text)
        self.assertIn("not-broken", text)
        self.assertIn("this invocation's new spend", text)
        self.assertIn("reused at $0 new spend", text)
        self.assertIn("selected measurement cost", text)

    def test_missing_retry_usage_and_baseline_failure_are_harness_errors(self):
        for rows in ([cell(), cell(recall=.5), cell(measurement_error="unknown")],
                     [cell(error="provider failure"), cell()]):
            rc, text, _ = self.main(rows)
            self.assertEqual(rc, 2, text)

    def test_attempts_are_immutable_and_unknowns_not_zeroed(self):
        path = self.root/"cell.json"
        first = gate.record_attempt(path, cell(cost_usd=.4), [])
        evidence = self.root/first["attempts"][0]["record"]
        original = evidence.read_bytes()
        retry = gate.record_attempt(path, cell(cost_usd=.6), first["attempts"])
        self.assertEqual(evidence.read_bytes(), original)
        self.assertEqual(len(list(self.root.glob("*.attempt.json"))), 2)
        self.assertEqual(gate.attempt_total(retry, "cost_usd"), 1)
        self.assertEqual(gate.attempt_total(retry, "tokens_request"), 120)
        retry["attempts"][0]["cost_usd"] = None
        self.assertIsNone(gate.attempt_total(retry, "cost_usd"))

    def test_run_cell_isolates_corpus_and_invalidates_changed_manifest(self):
        real_run = subprocess.run
        def git(*args):
            return real_run(["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True).stdout.strip()
        git("init", "--quiet")
        source = self.root/"main.go"
        source.write_text("package main\nfunc Foo() {}\n")
        git("add", "main.go")
        git("-c", "user.name=test", "-c", "user.email=test@localhost", "-c", "core.hooksPath=/dev/null",
            "-c", "commit.gpgsign=false", "commit", "-qm", "base")
        original_head = git("rev-parse", "HEAD")
        source.write_text("uncommitted user change\n")
        binary = self.root/"binary"
        binary.write_text("not executed")
        out = self.root/"out"
        out.mkdir()
        snapshots = []
        def invoke(arm, task, snapshot, model):
            snapshots.append(snapshot)
            self.assertNotEqual(snapshot, self.root)
            self.assertEqual((snapshot/"main.go").read_text(), "package main\nfunc Foo() {}\n")
            (snapshot/"main.go").write_text("agent change")
            return cell()
        def commands(args, **kwargs):
            if args[0] == str(binary):
                return subprocess.CompletedProcess(args, 0, "", "")
            return real_run(args, **kwargs)
        with patch.object(gate.usage_account, "claude_version", return_value="fixed-test-version"), \
                patch.object(gate.subprocess, "run", side_effect=commands), \
                patch.object(gate.bed, "run_arm", side_effect=invoke) as run:
            first_run = gate.RunAccounting(out, {})
            one = gate.run_cell("baseline", self.task, self.root, "fixed-model", out, str(binary), "sha", accounting=first_run)
            second_run = gate.RunAccounting(out, {})
            cached = gate.run_cell("baseline", self.task, self.root, "fixed-model", out, str(binary), "sha", accounting=second_run)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(one, cached)
            self.assertEqual(first_run.totals()["cost_usd"], 1)
            self.assertEqual(second_run.totals()["cost_usd"], 0)
            two = gate.run_cell("baseline", self.task, self.root, "fixed-model", out, str(binary), "sha", fresh=True, accounting=second_run)
            self.assertEqual(len(two["attempts"]), 2)
            self.assertEqual(second_run.totals()["cost_usd"], 1)
            self.assertEqual(gate.measurement_total(two, "cost_usd"), 1)
            self.assertEqual(gate.attempt_total(two, "cost_usd"), 2)
            changed = replace(self.task, prompt="find Bar")
            gate.run_cell("baseline", changed, self.root, "fixed-model", out, str(binary), "sha")
            self.assertEqual(run.call_count, 3)
            third_run = gate.RunAccounting(out, {})
            with patch.object(gate.bed, "run_arm", side_effect=subprocess.TimeoutExpired("claude", 1)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    gate.run_cell("baseline", self.task, self.root, "fixed-model", out, str(binary), "sha", fresh=True, accounting=third_run)
            self.assertIsNone(third_run.totals()["cost_usd"])
            self.assertEqual(len(third_run.attempts), 1)
        self.assertEqual(source.read_text(), "uncommitted user change\n")
        self.assertEqual(git("rev-parse", "HEAD"), original_head)
        self.assertEqual(len(set(snapshots)), 3)
        self.assertTrue(all(not p.exists() for p in snapshots))

    def test_run_arm_records_full_usage_and_marks_provider_errors(self):
        aggregate = {"input_tokens": 10, "cache_creation_input_tokens": 20, "cache_read_input_tokens": 30, "output_tokens": 4}
        raw = {"usage": aggregate, "total_cost_usd": .1, "num_turns": 3,
               "result": '{"sites": ["main.go:Foo"], "complete": true}'}
        for invalid in (False, True):
            data = copy.deepcopy(raw)
            if invalid:
                data["usage"].pop("cache_creation_input_tokens")
            completed = subprocess.CompletedProcess([], 0, json.dumps(data), "")
            with patch.object(gate.bed.subprocess, "run", return_value=completed), \
                    patch.object(gate.usage_account, "claude_version", return_value="test"):
                rec = gate.bed.run_arm("baseline", self.task, self.root, "test-model")
            self.assertEqual(rec["recall"], 1)
            if invalid:
                self.assertIn("measurement_error", rec)
                self.assertIsNone(rec["tokens_request"])
            else:
                self.assertEqual(rec["tokens_request"], 60)
                self.assertNotIn("error", rec)

    def test_measurement_excludes_other_invocations_and_keeps_current_retries(self):
        rec = cell(invocation_id="current", attempts=[
            cell(invocation_id="old", cost_usd=90, tokens_request=9000),
            cell(invocation_id="old-unknown", cost_usd=None),
            cell(invocation_id="current", cost_usd=.3, tokens_request=30),
            cell(invocation_id="current", cost_usd=.4, tokens_request=40)])
        self.assertIsNone(gate.attempt_total(rec, "cost_usd"))
        self.assertAlmostEqual(gate.measurement_total(rec, "cost_usd"), .7)
        self.assertEqual(gate.measurement_total(rec, "tokens_request"), 70)
        self.assertEqual(gate.attempt_total(rec, "cost_usd", "next-run"), 0)
        rec["attempts"][-1]["cost_usd"] = None
        self.assertIsNone(gate.measurement_total(rec, "cost_usd"))

    def test_legacy_or_inconsistent_measurement_identity_is_unknown(self):
        self.assertIsNone(gate.measurement_total(cell(invocation_id=None), "cost_usd"))
        self.assertIsNone(gate.measurement_total(cell(attempts=[cell(invocation_id="different")]), "cost_usd"))

    def test_invocation_spend_is_fresh_only_and_saved_before_fail_fast(self):
        first = gate.RunAccounting(self.root, {"candidate": "before-code-change"})
        path = self.root / "cell.json"
        rec = gate.record_attempt(path, cell(invocation_id=first.id, cost_usd=.4), [])
        first.capture(rec)
        first.capture(rec)
        self.assertEqual(first.totals()["cost_usd"], .4)
        second = gate.RunAccounting(self.root, {"candidate": "after-code-change"})
        second.capture(rec)
        self.assertEqual(second.totals()["cost_usd"], 0)
        self.assertTrue(next(iter(second.cells.values()))["reused"])
        self.assertEqual(next(iter(second.cells.values()))["measurement_cost_usd"], .4)
        retry = gate.record_attempt(path, cell(invocation_id=second.id, cost_usd=.6), rec["attempts"])
        second.capture(retry)
        self.assertEqual(second.totals()["cost_usd"], .6)
        self.assertEqual(gate.measurement_total(retry, "cost_usd"), .6)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(second.finish(1), 1)
        self.assertIn("new spend $0.6000", output.getvalue())
        saved = json.loads(second.path.read_text())
        self.assertEqual(saved["status"], "fail")
        self.assertEqual(saved["new_spend"]["cost_usd"], .6)
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(json.loads(first.path.read_text())["new_spend"]["cost_usd"], .4)

    def test_invocation_unknown_attempt_never_becomes_free(self):
        accounting = gate.RunAccounting(self.root, {})
        rec = gate.record_attempt(self.root / "cell.json",
                                  cell(invocation_id=accounting.id, cost_usd=None, tokens_request=None), [])
        accounting.capture(rec)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            accounting.finish(2)
        self.assertIn("new spend unknown", output.getvalue())
        saved = json.loads(accounting.path.read_text())
        self.assertIsNone(saved["new_spend"]["cost_usd"])
        self.assertIsNone(saved["new_spend"]["tokens_request"])

    def test_old_manifest_spend_does_not_decide_cheaper_gate(self):
        base = cell(invocation_id="base-now", attempts=[
            cell(invocation_id="base-before", cost_usd=.001),
            cell(invocation_id="base-now", cost_usd=1)])
        candidate = cell(invocation_id="candidate-now", attempts=[
            cell(invocation_id="candidate-before", cost_usd=100),
            cell(invocation_id="candidate-now", cost_usd=.5)])
        rc, text, _ = self.main([base, candidate])
        self.assertEqual(rc, 0, text)
        self.assertIn("selected measurement cost $0.50 vs $1.00", text)


if __name__ == "__main__":
    unittest.main()
