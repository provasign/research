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

# Bump when matching semantics change; ab_gate keys its cell cache on it so
# cells scored under an older contract are never compared with fresh ones.
SCORER_VERSION = 3  # v3 (2026-09-06): weak (pathless/bare) sites cost precision


def _parts(p: str) -> list[str]:
    return [x for x in p.strip().replace("\\", "/").split("/") if x not in ("", ".")]


def _bare(p: str) -> bool:
    """A basename with no directory: underspecified, never a strong match."""
    return len(_parts(p)) == 1


def _file_agree(gt: str, ans: str) -> bool:
    """Path components must agree over the shorter path's whole length.

    `pkg/worker.go` vs `/abs/worktree/pkg/worker.go` agree (agents cite
    absolute paths); `pkg/worker.go` vs `wrong/worker.go` do NOT — until
    2026-09-05 a basename match was enough, and a same-named file in another
    directory scored as the right site. A bare basename answer never agrees
    strongly (see `_bare`) unless the ground truth itself is bare.
    """
    if not gt or not ans:
        return False
    g, a = _parts(gt), _parts(ans)
    if not g or not a:
        return False
    if len(a) == 1 and len(g) > 1:
        return False
    n = min(len(g), len(a))
    return g[-n:] == a[-n:]


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


def _match(gt: Site, answer_sites: list[Site],
           used: set[Site] = frozenset()) -> tuple[Site | None, bool]:
    """Return (matched answer site, strong?) for a ground-truth site.

    Strong = symbol + file agree. Weak = symbol agrees and the answer gave
    NO path, or only a bare basename that matches (underspecified, not
    wrong). A same-named site with a conflicting path is neither -- it is a
    wrong answer and falls to `extra`.
    """
    weak: Site | None = None
    for a in answer_sites:
        if a.symbol != gt.symbol or a in used:
            continue  # one answer site credits at most one ground-truth site
        if _file_agree(gt.relpath, a.relpath):
            return a, True
        if weak is None and _underspecified(gt.relpath, a.relpath):
            weak = a
    return (weak, False) if weak else (None, False)


def _underspecified(gt: str, ans: str) -> bool:
    return not ans or (_bare(ans) and Path(gt).name == Path(ans).name)


def score(task: Task, answer: Answer, arm: str, trial: int) -> Scorecard:
    gt = task.ground_truth
    found: list[Site] = []
    missed: list[Site] = []
    weak: list[Site] = []
    matched_answer: set[Site] = set()

    strong_matched: set[Site] = set()
    for site in gt:
        m, strong = _match(site, answer.sites, matched_answer)
        if m is None:
            missed.append(site)
        elif strong:
            found.append(site)
            matched_answer.add(m)
            strong_matched.add(m)
        else:
            missed.append(site)
            weak.append(site)
            matched_answer.add(m)

    # An agent site is "extra" (false positive) if it is not a STRONG match
    # for a ground-truth site. A right-symbol/wrong-file site names a place
    # that must not change; a pathless or bare-basename site is unverified
    # evidence -- it earns `weak_recall`, never precision (until 2026-09-06
    # it was excused from `extra`, so an answer made of bare names looked
    # precise). Only test files are neutral.
    extra: list[Site] = []
    for a in answer.sites:
        if a in strong_matched:
            continue
        if _is_test_path(a.relpath):
            continue  # test sites are neutral (see _is_test_path)
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
