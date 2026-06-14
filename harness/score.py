"""Mode-A scorer: agent answer set vs PR-derived ground truth (design §6).

Recall/precision/F1 over change-sites, plus the two calibration signals the
paper hinges on (design §6, RQ3):

  * over-confidence rate  = P(agent asserts complete AND is incomplete)
  * gap-surfacing rate    = did the answer expose unresolved/ambiguous edges

Matching follows grove-eval's matched-universe discipline: a ground-truth
site matches an agent site when the bare symbol names agree AND the files
agree (basename is enough -- agents cite paths inconsistently). A symbol-only
match (no file agreement) still counts for recall but is flagged `weak`, so we
never silently credit a same-named symbol in the wrong file.
"""
from __future__ import annotations

from pathlib import Path

from schema import Answer, Scorecard, Site, Task


def _file_agree(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return Path(a).name == Path(b).name or a.endswith(b) or b.endswith(a)


def _match(gt: Site, answer_sites: list[Site]) -> tuple[Site | None, bool]:
    """Return (matched answer site, strong?) for a ground-truth site.

    Prefers a strong match (symbol + file agree); falls back to symbol-only.
    """
    weak: Site | None = None
    for a in answer_sites:
        if a.symbol != gt.symbol:
            continue
        if _file_agree(gt.relpath, a.relpath):
            return a, True
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
        else:
            found.append(site)
            matched_answer.add(m)
            if not strong:
                weak.append(site)

    # An agent site is "extra" (false positive) if it matched no ground-truth
    # site. Match each answer site against the ground truth symmetrically.
    extra: list[Site] = []
    gt_symbols = {(s.symbol, Path(s.relpath).name if s.relpath else "") for s in gt}
    for a in answer.sites:
        if a in matched_answer:
            continue
        key = (a.symbol, Path(a.relpath).name if a.relpath else "")
        sym_only = any(a.symbol == s.symbol for s in gt)
        if key in gt_symbols or sym_only:
            continue
        extra.append(a)

    recall = len(found) / len(gt) if gt else 0.0
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
    )
