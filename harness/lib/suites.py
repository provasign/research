"""Task-suite discovery: given a suite name, list its tasks with
category/pilot metadata from `harness/tasks/<suite>/*.json`.

A suite may carry a `SUITE.json` file (e.g. `harness/tasks/e2e/SUITE.json`)
mapping task id -> {category, pilot}. That file replaces hardcoded Python
dicts like `coding_suite.py`'s old `TASK_SPECS`/`PILOT_TASKS`: adding a task
to a suite that already has one means editing SUITE.json, not runner code.
A suite without SUITE.json is discovered by scanning its directory for
`*.json` task files (excluding `SUITE.json`, `manifest*.json`, and any
`excluded/` subdirectory), with no category/pilot metadata.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
TASKS_ROOT = HARNESS / "tasks"


@dataclass(frozen=True)
class TaskRef:
    id: str
    path: Path
    category: str | None = None
    pilot: bool = False


def list_suites(tasks_root: Path = TASKS_ROOT) -> list[str]:
    if not tasks_root.is_dir():
        return []
    return sorted(p.name for p in tasks_root.iterdir() if p.is_dir())


def suite_dir(name: str, tasks_root: Path = TASKS_ROOT) -> Path:
    return tasks_root / name


def load_suite_meta(name: str, tasks_root: Path = TASKS_ROOT) -> dict:
    meta_path = suite_dir(name, tasks_root) / "SUITE.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return {}


def list_tasks(name: str, tasks_root: Path = TASKS_ROOT) -> list[TaskRef]:
    directory = suite_dir(name, tasks_root)
    meta = load_suite_meta(name, tasks_root)
    tasks: list[TaskRef] = []
    if meta.get("tasks"):
        for task_id, info in meta["tasks"].items():
            path = directory / f"{task_id}.json"
            tasks.append(TaskRef(id=task_id, path=path,
                                 category=info.get("category"),
                                 pilot=bool(info.get("pilot"))))
        return sorted(tasks, key=lambda t: t.id)
    if not directory.is_dir():
        return []
    for path in sorted(directory.glob("*.json")):
        if path.name in ("SUITE.json",) or path.name.startswith("manifest"):
            continue
        tasks.append(TaskRef(id=path.stem, path=path))
    return tasks


def suite_kind(name: str, tasks_root: Path = TASKS_ROOT) -> str | None:
    """"coding" (patch + docker_eval) or "impact" (site-list + oracle), from
    SUITE.json's "kind" field. None when undeclared."""
    return load_suite_meta(name, tasks_root).get("kind")


def pilot_task_ids(name: str, tasks_root: Path = TASKS_ROOT) -> list[str]:
    return [t.id for t in list_tasks(name, tasks_root) if t.pilot]


def task_ids_for_phase(name: str, phase: str, tasks_root: Path = TASKS_ROOT) -> list[str]:
    tasks = list_tasks(name, tasks_root)
    all_ids = [t.id for t in tasks]
    pilot = [t.id for t in tasks if t.pilot]
    if phase == "pilot":
        return pilot or all_ids
    if phase == "remaining":
        return [i for i in all_ids if i not in pilot]
    return all_ids


def resolve_task_path(name: str, task_id: str, tasks_root: Path = TASKS_ROOT) -> Path:
    for ref in list_tasks(name, tasks_root):
        if ref.id == task_id:
            return ref.path
    return suite_dir(name, tasks_root) / f"{task_id}.json"
