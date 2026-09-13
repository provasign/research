#!/usr/bin/env python3
"""Backward-compatible API and entry point for the deterministic impact oracle.

``impact_oracle.py`` supersedes this script with pinned snapshots, official
precision/F1 scoring, payload and completeness thresholds, reproducible JSON
artifacts, and meaningful exit codes. Existing engine-ceiling commands keep
working through this alias.
"""

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

from pathlib import Path

from impact_oracle import change_impact, main as impact_main, task_anchor
from schema import Task

PRISM = Path.home() / "bin" / "prism"


def prism_query(task: Task) -> str:
    """Compatibility name for the explicit task-metadata query parser."""
    return task_anchor(task)


def engine_sites(query: str, workdir: Path) -> tuple[list[str], dict]:
    """Compatibility adapter for callers that manage their own snapshots."""
    result = change_impact(str(PRISM), workdir, query)
    sites = [str(site) for site in result.pop("sites")]
    flags = {
        "completeness": result["completeness"],
        "externalSupers": result["external_supers"],
        "overridesExternal": result["overrides_external"],
    }
    return sites, {key: value for key, value in flags.items() if value}


def main() -> None:
    code = impact_main()
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
