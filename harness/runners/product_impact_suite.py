"""Normal-product change-impact suite: identical prompts, native versus Prism.

Agent invocation, event parsing, and protocol audit now live in
`harness/lib/runner_core.py` (the same module `harness/bench.py` and
`harness/runners/coding_suite.py` use) instead of being re-implemented or
importlib-loaded from a `harness/results/*` snapshot. Task selection comes
from `harness/tasks/manual/SUITE.json` (migrated from the old
`TASK_IDS`/`PILOT_TASKS` constants) via `harness/lib/suites`.

This suite answers with a structured JSON site-list, scored against an
oracle (`scoring/score.py`), not a code patch -- `harness/bench.py run`
does not yet support that task shape (see its `cmd_run` docstring/error),
so this remains a standalone entrypoint for now.
"""
from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, _H)

from lib import runner_core as rc  # noqa: E402
from lib import scoring as sc  # noqa: E402
from lib import suites  # noqa: E402
from lib.pricing import add_gpt55_cost  # noqa: E402
from schema import Answer, Task  # noqa: E402
from score import SCORER_VERSION  # noqa: E402

SUITE = "manual"
PILOT_TASKS = suites.pilot_task_ids(SUITE)
TASK_IDS = [ref.id for ref in suites.list_tasks(SUITE)]
ARMS = ["sonnet_native", "gpt55_native", "sonnet_prism", "gpt55_prism"]
SONNET_MODEL = "claude-sonnet-5"
GPT_MODEL = "gpt-5.5"
LIMIT_S = 300
SEED = 20260908


def prompt_for(task: Task) -> str:
    return """Analyze only the repository in your current working directory. Do not edit source files.
Do not use the network, other repository copies, benchmark files, git history, saved answers,
memory, skills, or delegated agents. Use local repository evidence to solve this task.
Return ONLY one JSON object with keys sites (array of strings), complete (boolean),
and unresolved (array of strings). Each site must be <repo-relative-path>:<FunctionOrMethodName>.
Enumerate production-source methods/functions containing every affected call, declaration, and
override. Deduplicate the same path and method. Do not include tests, types, fields, or the same
edit location twice. Claim complete only if justified.

ISSUE:
""" + task.prompt


def snapshot_files(work: Path) -> dict[str, str]:
    files = {}
    for path in work.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(work)
        if any(part in (".git", ".prism", ".grove") for part in rel.parts):
            continue
        files[str(rel)] = rc.sha(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--phase", choices=("pilot", "remaining", "full"), default="pilot")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--prism-binary", default=None,
                        help="path to the prism binary to use (default: $PRISM_BINARY, "
                             "PATH, or ~/bin/prism -- see lib.runner_core.resolve_prism_binary)")
    args = parser.parse_args()
    task_ids = suites.task_ids_for_phase(SUITE, args.phase)
    root = Path(args.run_dir).resolve()
    if root.exists():
        raise SystemExit(f"run dir already exists: {root}")
    root.mkdir(parents=True)
    prism_source = rc.resolve_prism_binary(args.prism_binary)
    binary = root / "prism-bin"
    shutil.copy2(prism_source, binary)
    cli = root / "bin" / "prism"
    cli.parent.mkdir()
    shutil.copy2(binary, cli)
    shutil.copy2(Path(__file__), root / "run_impact.py")
    schema = {
        "type": "object",
        "properties": {
            "sites": {"type": "array", "items": {"type": "string"}},
            "complete": {"type": "boolean"},
            "unresolved": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["sites", "complete", "unresolved"],
        "additionalProperties": False,
    }
    rc.dump(root / "answer-schema.json", schema)

    cfg = rc.AgentConfig(sonnet_model=SONNET_MODEL, gpt_model=GPT_MODEL, timeout_s=LIMIT_S,
                        max_budget_usd="1.50", permission_mode="skip",
                        tools="Read,Grep,Glob,Bash", allowed_tools="Read,Grep,Glob,Bash,mcp__prism",
                        project_doc_max_bytes=32768, output_schema=True)

    prepared, task_manifest = {}, []
    for task_id in task_ids:
        path = suites.resolve_task_path(SUITE, task_id)
        task = Task.load(path)
        archive, pristine, excluded = rc.pristine_archive(task.repo, task.pin, task.id)
        rc.dump(root / "tasks" / path.name, json.loads(path.read_text()))
        prepared[task_id] = (task, archive, pristine)
        task_manifest.append({
            "task": task_id, "pin": task.pin, "task_sha256": rc.sha(path),
            "archive_sha256": hashlib.sha256(archive).hexdigest(),
            "source_files": len(pristine), "excluded_steering_files": excluded,
        })
    rng = random.Random(SEED)
    waves = []
    for trial in range(1, args.trials + 1):
        order = list(task_ids)
        rng.shuffle(order)
        for task_id in order:
            offset = (task_ids.index(task_id) + trial - 1) % len(ARMS)
            waves.append((task_id, trial, ARMS[offset:] + ARMS[:offset]))
    versions = {
        "claude": rc.command(["claude", "--version"]).decode().strip(),
        "codex": rc.command(["codex", "--version"]).decode().strip(),
        "prism": rc.command([str(binary), "version"]).decode().strip(),
    }
    manifest = {
        "schema_version": 1, "study": "product-impact-suite-v1", "status": "preflight",
        "phase": args.phase, "seed": SEED, "tasks": task_manifest, "arms": ARMS,
        "trials": args.trials, "waves": waves,
        "planned_cells": len(waves) * len(ARMS),
        "models": {"sonnet": SONNET_MODEL, "gpt": GPT_MODEL},
        "effort": cfg.effort, "timeout_s": LIMIT_S, "concurrency": 4, "retries": 0,
        "prompt_pairing": "identical task prompt across all four arms",
        "integration": "Prism init generated product files; normal tool choice; MCP and CLI available",
        "scorer_version": SCORER_VERSION,
        "hashes": {"runner": rc.sha(Path(__file__)), "prism_binary": rc.sha(binary)},
        "versions": versions,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rc.dump(root / "manifest.json", manifest)
    print(f"PREFLIGHT PASS: {len(task_ids)} tasks, {manifest['planned_cells']} cells, {versions}", flush=True)
    if args.preflight_only:
        manifest["status"] = "preflight_only"
        rc.dump(root / "manifest.json", manifest)
        return 0

    def finalize_impact(cell: rc.Cell, rec: dict, final: str) -> dict:
        if cell.arm.startswith("gpt55"):
            add_gpt55_cost(rec)
        task = cell.extra["task"]
        answer = Answer.parse(final)
        card_dict = sc.dispatch("impact", task=task, answer=answer, arm=cell.arm,
                                trial=cell.extra["trial"])
        return {
            "task": task.id,
            "answer": {"sites": [str(site) for site in answer.sites],
                      "complete": answer.complete, "unresolved": answer.unresolved},
            "scorer_version": SCORER_VERSION, "score": card_dict,
        }

    rows = []
    manifest["status"] = "running"
    rc.dump(root / "manifest.json", manifest)
    for number, (task_id, trial, arm_order) in enumerate(waves, 1):
        task, archive, pristine = prepared[task_id]
        print(f"WAVE {number}/{len(waves)} {task_id} trial={trial} order={arm_order}", flush=True)
        cells = []
        for arm in arm_order:
            key = f"{task_id}.r{trial}.{arm}"
            work = root / "work" / key
            rc.extract_archive(archive, work)
            rc.command(["git", "init", "-q"], work)
            has_prism = arm.endswith("prism")
            if has_prism:
                # Two Prism steps, matching the original product-impact
                # runner: `prism index` builds the graph used for MCP calls,
                # then `prism init --no-permissions` layers the product
                # integration (steering files, etc.) on top of that index.
                indexed = rc.command([str(binary), "index", str(work)], cwd=work, check=False)
                initialized = rc.command(
                    rc.prism_init_args(binary, work), cwd=work, check=False,
                )
            prompt = prompt_for(task)
            cell = rc.prepare_cell(root, key, arm, None, cfg, binary, prompt,
                                   prism_cli_dir=(root / "bin") if has_prism else None,
                                   extra={"task": task, "trial": trial})
            cell.extra["pristine"] = snapshot_files(cell.work)
            cells.append(cell)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(rc.run_cell, cell, cfg, finalize_impact) for cell in cells]
            for future in concurrent.futures.as_completed(futures):
                rows.append(future.result())
                rc.dump(root / "summary.json", {
                    "status": "running", "completed": len(rows),
                    "planned": manifest["planned_cells"], "rows": rows,
                })
    valid = sum(bool(row.get("audited_valid")) for row in rows)
    status = "complete" if valid == manifest["planned_cells"] else "audit_incomplete"
    rc.dump(root / "summary.json", {
        "status": status, "completed": len(rows), "valid": valid,
        "planned": manifest["planned_cells"], "rows": rows,
    })
    manifest.update(status=status, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rc.dump(root / "manifest.json", manifest)
    print(f"FINISHED {status}: {root}", flush=True)
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
