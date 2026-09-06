"""Unit tests for the wide-bed site scorer -- synthetic diffs, no git.

Run: cd research/harness && python -m pytest -p no:asyncio -p no:pytest_asyncio tests/test_wide_score.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wide_score as W  # noqa: E402

TASK = {"gt_files": ["a/x.go"], "gt_symbols": ["OldFn"]}


def _diff(file, hunks):
    """hunks: list of (old_start, [('-'|'+', text), ...]) in -U0 shape."""
    out = [f"diff --git a/{file} b/{file}", f"--- a/{file}", f"+++ b/{file}"]
    for start, lines in hunks:
        n_minus = sum(1 for k, _ in lines if k == "-")
        n_plus = sum(1 for k, _ in lines if k == "+")
        out.append(f"@@ -{start},{n_minus} +{start},{n_plus} @@")
        out += [k + t for k, t in lines]
    return "\n".join(out) + "\n"


# gold: two distant sites in one file, each replacing a call
GOLD = _diff("a/x.go", [
    (10, [("-", "\tOldFn(a)"), ("+", "\tNewFn(a)")]),
    (80, [("-", "\tOldFn(b)"), ("+", "\tNewFn(b)")]),
])


def test_gold_against_itself_is_perfect():
    s = W.score_diff(TASK, GOLD, GOLD)
    assert s["sites_expected"] == 2
    assert s["site_recall"] == 1.0 and s["symbol_recall_strict"] == 1.0


def test_one_of_two_sites_in_a_file_is_half():
    # Reviewer probe 2026-09-05: this scored 1.0 when sites were files.
    agent = _diff("a/x.go", [(10, [("-", "\tOldFn(a)"), ("+", "\tNewFn(a)")])])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["site_recall"] == 0.5
    assert s["missed_sites"] == ["a/x.go:80"]


def test_todo_in_place_of_the_change_is_not_exact():
    # Reviewer probe 2026-09-05: a TODO comment at the right line scored 1.0.
    agent = _diff("a/x.go", [
        (10, [("-", "\tOldFn(a)"), ("+", "\t// TODO migrate")]),
        (80, [("-", "\tOldFn(b)"), ("+", "\t// TODO migrate")]),
    ])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["site_recall"] == 0.0            # headline (substituted)
    assert s["site_recall_exact"] == 0.0
    assert s["site_recall_removed"] == 1.0    # old contract line is gone
    assert s["site_recall_proximity"] == 1.0


def test_equivalent_but_textually_different_replacement_is_substituted():
    agent = _diff("a/x.go", [
        (10, [("-", "\tOldFn(a)"), ("+", "\tNewFn(a) // migrated")]),
        (80, [("-", "\tOldFn(b)"), ("+", "\tNewFn(b)")]),
    ])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["site_recall"] == 1.0
    assert s["site_recall_exact"] == 0.5


def test_touching_the_file_elsewhere_is_missed():
    agent = _diff("a/x.go", [(40, [("+", "\t// unrelated")])])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["site_recall"] == 0.0 and s["site_recall_proximity"] == 0.0


def test_wrong_place_in_right_file_costs_precision():
    # Reviewer 2026-09-06: a false edit inside a ground-truth file paid
    # nothing — only whole extra files counted.
    agent = _diff("a/x.go", [
        (10, [("-", "\tOldFn(a)"), ("+", "\tNewFn(a)")]),
        (40, [("-", "\tkeep()"), ("+", "\tbroken()")]),
        (80, [("-", "\tOldFn(b)"), ("+", "\tNewFn(b)")]),
    ])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["site_recall"] == 1.0
    assert s["false_edit_regions"] == 1 and s["false_edit_sites"] == ["a/x.go:40"]
    assert s["site_precision"] == round(2 / 3, 3)
    assert s["extra_files_strict"] == 0  # the old metric still says "clean"


def test_files_complete_requires_every_site_in_the_file():
    # Review 2026-09-06: one substituted site out of two used to count the
    # file as complete.
    agent = _diff("a/x.go", [(10, [("-", "\tOldFn(a)"), ("+", "\tNewFn(a)")])])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["files_complete"] == 0 and s["files_expected_strict"] == 1
    s = W.score_diff(TASK, GOLD, GOLD)
    assert s["files_complete"] == 1


def test_clean_sweep_has_full_site_precision():
    s = W.score_diff(TASK, GOLD, GOLD)
    assert s["site_precision"] == 1.0 and s["false_edit_regions"] == 0


def test_u3_context_diff_agrees_with_u0():
    # Same change expressed with context lines: old-side walk must line up.
    u3 = "\n".join([
        "diff --git a/a/x.go b/a/x.go", "--- a/a/x.go", "+++ b/a/x.go",
        "@@ -7,7 +7,7 @@", " ctx7", " ctx8", " ctx9",
        "-\tOldFn(a)", "+\tNewFn(a)", " ctx11", " ctx12", " ctx13",
        "@@ -77,7 +77,7 @@", " c77", " c78", " c79",
        "-\tOldFn(b)", "+\tNewFn(b)", " c81", " c82", " c83", ""])
    s = W.score_diff(TASK, u3, GOLD)
    assert s["site_recall"] == 1.0


def test_whitespace_differences_do_not_matter():
    agent = _diff("a/x.go", [
        (10, [("-", "    OldFn(a)"), ("+", "    NewFn( a )")]),
        (80, [("-", "\tOldFn(b)"), ("+", "\tNewFn(b)")]),
    ])
    s = W.score_diff(TASK, agent, GOLD)
    # first site: removed line matches after normalisation; added line does
    # not ("NewFn( a )" != "NewFn(a)") -> substituted, not exact
    assert s["site_recall"] == 1.0 and s["site_recall_exact"] == 0.5


def test_symbol_only_in_context_line_does_not_count():
    agent = "\n".join([
        "diff --git a/a/x.go b/a/x.go", "--- a/a/x.go", "+++ b/a/x.go",
        "@@ -9,3 +9,4 @@", " ctx", " \tOldFn(a)", "+\t// note", " ctx", ""])
    s = W.score_diff(TASK, agent, GOLD)
    assert s["symbol_recall_strict"] == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
