"""java_eval._parse_surefire: surefire XML reports -> classname::name outcomes."""
import sys
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
for _d in (HARNESS / "scoring", HARNESS / "build"):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))
import java_eval  # noqa: E402

HDR = '<?xml version="1.0" encoding="UTF-8"?>\n'


def suite(name, body):
    return (f'{HDR}<testsuite xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" name="{name}" '
            f'tests="3"><properties><property name="a" value="b"/></properties>{body}</testsuite>\n')


class ParseSurefireTests(unittest.TestCase):
    def parse(self, *suites, prefix="[INFO] BUILD SUCCESS\n"):
        return java_eval._parse_surefire(prefix + "---SUREFIRE---\n" + "".join(suites))

    def test_self_closing_pass_followed_by_failure(self):
        # the old regex returned {'C::A': 'FAILED'} and lost B
        res = self.parse(suite("C", '<testcase name="A" classname="C" time="0.1"/>'
                                    '<testcase name="B" classname="C"><failure message="x"/></testcase>'))
        self.assertEqual(res, {"C::A": "PASSED", "C::B": "FAILED"})

    def test_skipped_and_error(self):
        res = self.parse(suite("C", '<testcase name="S" classname="C"><skipped/></testcase>'
                                    '<testcase name="E" classname="C" time="0">'
                                    '<error type="java.lang.NPE">trace</error>'
                                    '<system-out><![CDATA[<b>not xml</b>]]></system-out></testcase>'
                                    '<testcase name="P" classname="C"><system-out>hi</system-out></testcase>'))
        self.assertEqual(res, {"C::S": "SKIPPED", "C::E": "FAILED", "C::P": "PASSED"})

    def test_multiple_suites_and_malformed_chunk(self):
        good1 = suite("a.X", '<testcase name="t1" classname="a.X"/>')
        broken = HDR + '<testsuite name="a.Bad"><testcase name="t" classname="a.Bad"></testsuite>\n'
        good2 = suite("b.Y", '<testcase name="t2" classname="b.Y"><failure/></testcase>'
                              '<testcase name="t3" classname="b.Y"/>')
        res = self.parse(good1, broken, good2)
        self.assertEqual(res, {"a.X::t1": "PASSED", "b.Y::t2": "FAILED", "b.Y::t3": "PASSED"})

    def test_flaky_rerun_counts_as_pass_and_duplicate_failure_wins(self):
        res = self.parse(suite("C", '<testcase name="F" classname="C"><flakyFailure message="m"/></testcase>'
                                    '<testcase name="D" classname="C"/>'
                                    '<testcase name="D" classname="C"><failure/></testcase>'
                                    '<testcase name="D" classname="C"/>'))
        self.assertEqual(res, {"C::F": "PASSED", "C::D": "FAILED"})

    def test_empty_self_closing_suite_and_no_reports(self):
        self.assertEqual(self.parse(HDR + '<testsuite name="E" tests="0"/>\n'), {})
        self.assertEqual(java_eval._parse_surefire("BUILD FAILURE\n---SUREFIRE---\n"), {})

    def test_entry_ok_class_level_ignores_skips(self):
        res = {"C::a": "PASSED", "C::b": "SKIPPED", "D::a": "SKIPPED"}
        self.assertTrue(java_eval._entry_ok(res, "src:C"))
        self.assertFalse(java_eval._entry_ok(res, "D"))
        self.assertFalse(java_eval._entry_ok(res, "C::b"))


if __name__ == "__main__":
    unittest.main()
