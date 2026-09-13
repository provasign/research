"""Scoring dispatcher: coding-style tasks (patch + docker_eval) versus
impact-style tasks (structured site-list answer + oracle).

Callers add `scoring` (and `aggregate`) to `sys.path` first -- this module
follows the same flat-import convention as the rest of the harness
(`docker_eval`, `schema`, `score` are top-level modules, not a package).
"""
from __future__ import annotations

from pathlib import Path

CODING = "coding"
IMPACT = "impact"


def score_coding_cell(task: dict, diff: str) -> dict:
    """Score a coding/patch task: apply the diff and run held-out
    FAIL_TO_PASS/PASS_TO_PASS tests in Docker. An empty diff scores as
    unresolved without touching Docker."""
    import docker_eval  # noqa: PLC0415

    if not diff.strip():
        return {"resolved": False, "empty_diff": True}
    try:
        return docker_eval.score(task, diff)
    except Exception as exc:  # pragma: no cover - exercised via runner integration
        return {"resolved": False, "harness_error": repr(exc)}


def score_impact_cell(task, answer, arm: str, trial: int):
    """Score an impact/localization task: the agent's structured site list
    against the task's ground-truth change-sites."""
    from score import score as score_answer  # noqa: PLC0415

    return score_answer(task, answer, arm, trial)


def dispatch(kind: str, **kwargs) -> dict:
    if kind == CODING:
        return score_coding_cell(kwargs["task"], kwargs["diff"])
    if kind == IMPACT:
        card = score_impact_cell(kwargs["task"], kwargs["answer"], kwargs["arm"], kwargs["trial"])
        return card.to_dict() if hasattr(card, "to_dict") else card
    raise ValueError(f"unknown scoring kind: {kind!r}")


def read_diff(evidence_dir: Path) -> str:
    path = evidence_dir / "agent.diff"
    return path.read_text() if path.exists() else ""
