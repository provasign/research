"""Mode-A scorer: agent answer set vs PR-derived ground truth (design §6).

Recall/precision/F1 over change-sites, plus the two calibration signals the
paper hinges on (design §6, RQ3):

  * over-confidence rate  = P(agent asserts complete AND is incomplete)
  * gap-surfacing rate    = did the answer expose unresolved/ambiguous edges

Matching follows grove-eval's matched-universe discipline: a ground-truth
site matches an agent site when the bare symbol names agree AND the files
agree (basename is enough -- agents cite paths inconsistently).

Until 2026-09-05 a symbol-only match (no file agreement) still counted toward
recall, merely flagged `weak`. That is a false-credit path: a same-named
method in a deliberately wrong file scored as found. Now:

  * recall counts STRONG matches (symbol + file) only;
  * an answer site with the right symbol and NO path is `weak` -- reported
    in `weak_recall`, never in `recall`;
  * an answer site with the right symbol and the WRONG path is a false
    positive (`extra`) -- it names a site that must not change.
"""
from __future__ import annotations

from pathlib import Path

from schema import Answer, Scorecard, Site, Task


def _file_agree(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return Path(a).name == Path(b).name or a.endswith(b) or b.endswith(a)


def _is_test_path(relpath: str) -> bool:
    """Test-file heuristic (Go/Py/TS/Java). Test sites are scored as neutral.

    Production change-site completeness is the headline metric; whether the
    agent also enumerates test call sites is a separate concern (and for a
    rename the tests legitimately must change, so listing them is not a false
    positive). We therefore exclude test-file answer sites from precision
    rather than count them as errors -- and ground truth holds prod sites only.
    """
    name = Path(relpath).name
    return (
        relpath.endswith("_test.go")  # Go test files (NOT test_helpers.go)
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
        or "/tests/" in relpath
        or relpath.startswith("tests/")  # root-level tests/ dir (Django, etc.)
        or name.endswith("Test.java")
        or name.endswith("Tests.java")
    )


def _match(gt: Site, answer_sites: list[Site]) -> tuple[Site | None, bool]:
    """Return (matched answer site, strong?) for a ground-truth site.

    Strong = symbol + file agree. Weak = symbol agrees and the answer gave
    NO path at all (underspecified, not wrong). A same-named site with a
    different path is neither -- it is a wrong answer and falls to `extra`.
    """
    weak: Site | None = None
    for a in answer_sites:
        if a.symbol != gt.symbol:
            continue
        if _file_agree(gt.relpath, a.relpath):
            return a, True
        if not a.relpath and weak is None:
            weak = a
    return (weak, False) if weak else (None, False)


def score(task: Task, answer: Answer, arm: str, trial: int) -> Scorecard:
    gt = task.ground_truth
    found: list[Site] = []
    missed: list[Site] = []
    weak: list[Site] = []
    matched_answer: set[Site] = set()

    for site in gt:
        m, strong = _match(site, answer.sites)
        if m is None:
            missed.append(site)
        elif strong:
            found.append(site)
            matched_answer.add(m)
        else:
            missed.append(site)
            weak.append(site)
            matched_answer.add(m)

    # An agent site is "extra" (false positive) if it matched no ground-truth
    # site. A right-symbol/wrong-file site is extra too -- it names a place
    # that must not change. Only pathless right-symbol sites (already `weak`)
    # and test files are excused.
    extra: list[Site] = []
    for a in answer.sites:
        if a in matched_answer:
            continue
        if _is_test_path(a.relpath):
            continue  # test sites are neutral (see _is_test_path)
        if not a.relpath and any(a.symbol == s.symbol for s in gt):
            continue  # pathless duplicate of a weak match
        extra.append(a)

    recall = len(found) / len(gt) if gt else 0.0
    weak_recall = (len(found) + len(weak)) / len(gt) if gt else 0.0
    answered = len(found) + len(extra)
    precision = len(found) / answered if answered else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    overconfident = answer.complete and recall < 1.0
    surfaced_gap = bool(answer.unresolved) or not answer.complete

    return Scorecard(
        task_id=task.id,
        arm=arm,
        trial=trial,
        recall=round(recall, 4),
        precision=round(precision, 4),
        f1=round(f1, 4),
        found=[str(s) for s in found],
        missed=[str(s) for s in missed],
        extra=[str(s) for s in extra],
        weak_matches=[str(s) for s in weak],
        claimed_complete=answer.complete,
        overconfident=overconfident,
        surfaced_gap=surfaced_gap,
        weak_recall=round(weak_recall, 4),
    )
