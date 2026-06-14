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


def test_weak_match_wrong_file_flagged():
    a = _ans('{"sites":["other.go:Hijack","response_writer.go:CloseNotify"],'
             '"complete":true}')
    c = score(TASK, a, "T", 1)
    assert c.recall == 1.0  # symbol-only match still credits recall
    assert "response_writer.go:Hijack" in c.weak_matches


def test_no_json_yields_zero():
    c = score(TASK, _ans("I could not determine the sites."), "T", 1)
    assert c.recall == 0.0 and c.precision == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
