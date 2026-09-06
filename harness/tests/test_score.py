"""Unit tests for the Mode-A scorer -- no agent, no network.

Run: cd research/harness && python -m pytest tests/ -q
(or: python tests/test_score.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema import Answer, Site, Task  # noqa: E402
from score import score  # noqa: E402

TASK = Task(
    id="t",
    repo="/tmp/x",
    lang="go",
    pin="abc",
    pr="#1",
    task_type="localization",
    prompt="fix it",
    ground_truth=[
        Site("response_writer.go", "Hijack"),
        Site("response_writer.go", "CloseNotify"),
    ],
)


def _ans(text):
    return Answer.parse(text)


def test_perfect_and_complete():
    a = _ans('{"sites":["response_writer.go:Hijack","response_writer.go:CloseNotify"],'
             '"complete":true,"unresolved":[]}')
    c = score(TASK, a, "T", 1)
    assert c.recall == 1.0 and c.precision == 1.0 and c.f1 == 1.0
    assert not c.overconfident
    assert not c.surfaced_gap  # complete and nothing unresolved


def test_incomplete_but_confident_is_overconfident():
    a = _ans('{"sites":["response_writer.go:Hijack"],"complete":true}')
    c = score(TASK, a, "T", 1)
    assert c.recall == 0.5
    assert c.overconfident  # the calibration failure the paper targets
    assert c.missed == ["response_writer.go:CloseNotify"]


def test_incomplete_and_honest_not_overconfident():
    a = _ans('{"sites":["response_writer.go:Hijack"],"complete":false,'
             '"unresolved":["dispatch through interface unclear"]}')
    c = score(TASK, a, "G", 1)
    assert c.recall == 0.5
    assert not c.overconfident
    assert c.surfaced_gap


def test_false_positive_lowers_precision():
    a = _ans('{"sites":["response_writer.go:Hijack","response_writer.go:CloseNotify",'
             '"response_writer.go:Flush"],"complete":true}')
    c = score(TASK, a, "T", 1)
    assert c.recall == 1.0
    assert c.precision == round(2 / 3, 4)
    assert c.extra == ["response_writer.go:Flush"]


def test_wrong_file_same_symbol_is_a_false_positive():
    # 2026-09-05: a same-named symbol in the WRONG file used to count toward
    # recall (flagged weak). It is a wrong answer: no recall credit, and it
    # costs precision like any other extra site.
    a = _ans('{"sites":["other.go:Hijack","response_writer.go:CloseNotify"],'
             '"complete":true}')
    c = score(TASK, a, "T", 1)
    assert c.recall == 0.5
    assert c.extra == ["other.go:Hijack"]
    assert c.weak_matches == []
    assert c.overconfident  # claimed complete, missed Hijack


DIR_TASK = Task(
    id="t2", repo="/tmp/x", lang="go", pin="abc", pr="#1",
    task_type="localization", prompt="fix it",
    ground_truth=[Site("pkg/worker.go", "Run"), Site("cmd/worker.go", "Run")],
)


def test_wrong_directory_same_basename_is_not_a_match():
    # Reviewer probe 2026-09-05: wrong/worker.go:Run scored 1.0 recall AND
    # precision against two sites in other directories (basename match).
    a = _ans('{"sites":["wrong/worker.go:Run"],"complete":true}')
    c = score(DIR_TASK, a, "T", 1)
    assert c.recall == 0.0
    assert c.extra == ["wrong/worker.go:Run"]
    assert c.overconfident


def test_absolute_worktree_prefix_still_agrees():
    a = _ans('{"sites":["/private/tmp/wt/pkg/worker.go:Run",'
             '"/private/tmp/wt/cmd/worker.go:Run"],"complete":true}')
    c = score(DIR_TASK, a, "T", 1)
    assert c.recall == 1.0 and c.precision == 1.0


def test_bare_basename_is_weak_when_ambiguous():
    a = _ans('{"sites":["worker.go:Run"],"complete":false}')
    c = score(DIR_TASK, a, "T", 1)
    assert c.recall == 0.0
    assert c.weak_recall == 0.5  # credits at most one site, as weak evidence
    assert c.extra == []


def test_pathless_symbol_is_weak_evidence_only():
    # No path at all is underspecified, not wrong: reported in weak_recall,
    # excluded from recall, not penalised as extra.
    a = _ans('{"sites":["Hijack","response_writer.go:CloseNotify"],"complete":false}')
    c = score(TASK, a, "T", 1)
    assert c.recall == 0.5
    assert c.weak_recall == 1.0
    assert "response_writer.go:Hijack" in c.weak_matches
    assert c.extra == []


def test_test_sites_are_neutral_not_false_positives():
    # A rename task: listing the _test.go call site is correct, not an FP.
    a = _ans('{"sites":["response_writer.go:Hijack","response_writer.go:CloseNotify",'
             '"response_writer_test.go:TestHijack"],"complete":true}')
    c = score(TASK, a, "G", 1)
    assert c.recall == 1.0
    assert c.precision == 1.0  # test site excluded from precision, not penalized
    assert c.extra == []


def test_no_json_yields_zero():
    c = score(TASK, _ans("I could not determine the sites."), "T", 1)
    assert c.recall == 0.0 and c.precision == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
