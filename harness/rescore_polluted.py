"""One-shot repair: rescore cells whose persisted agent diff contains tool
artifacts (.grove/ etc.). git apply is atomic, so those binary stubs made the
WHOLE patch unappliable — the agent's real fix never reached the test run and
the cell scored resolved=False regardless of fix quality.

For every runs/e2e/*.diff containing an artifact path: strip the artifact file
sections, re-run docker_eval.score on the clean patch, and update the matching
cell JSON in place (original score kept under `score_polluted` for audit).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import docker_eval
from run_e2e import TOOL_ARTIFACTS

OUT = Path("runs/e2e")
TASKS = Path("tasks-e2e")


def strip_artifacts(diff: str) -> tuple[str, bool]:
    """Remove per-file sections whose path starts with a tool artifact."""
    sections = re.split(r"(?m)^(?=diff --git )", diff)
    kept, dropped = [], False
    for s in sections:
        if not s.strip():
            continue
        m = re.match(r"diff --git a/(\S+) ", s)
        if m and any(m.group(1) == a or m.group(1).startswith(a + "/")
                     for a in TOOL_ARTIFACTS):
            dropped = True
            continue
        kept.append(s)
    return "".join(kept), dropped


def main():
    changed = 0
    for diff_file in sorted(OUT.glob("*.diff")):
        cell_file = diff_file.with_suffix(".json")
        if not cell_file.exists():
            print(f"  SKIP {diff_file.name}: no cell json")
            continue
        raw = diff_file.read_text()
        clean, dropped = strip_artifacts(raw)
        if not dropped:
            continue
        cell = json.loads(cell_file.read_text())
        task = json.loads((TASKS / f"{cell['task']}.json").read_text())
        sc = (docker_eval.score(task, clean) if clean.strip()
              else {"resolved": False, "empty_diff": True})
        before = cell.get("resolved")
        cell["score_polluted"] = cell.get("score")
        cell["score"] = sc
        cell["resolved"] = sc.get("resolved")
        cell["diff_lines"] = clean.count("\n")
        cell["rescored"] = "stripped tool artifacts (.grove etc.) 2026-07-14"
        cell_file.write_text(json.dumps(cell, indent=2))
        diff_file.write_text(clean)
        changed += 1
        flip = " <-- FLIPPED" if before != cell["resolved"] else ""
        print(f"  {cell_file.name}: resolved {before} -> {cell['resolved']}{flip}")
    print(f"# rescored {changed} cells")


if __name__ == "__main__":
    main()
