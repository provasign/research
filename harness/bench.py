#!/usr/bin/env python3
"""Standard benchmark runner CLI.

**This is the standard way to run a Prism benchmark. Do not write a new
one-off runner script -- add a flag here or a suite under `harness/tasks/`
instead.** See `harness/docs/BENCH.md` for invocation examples.

Subcommands:
  bench.py run          --suite <name> [--tasks id1,id2] [--agents claude,codex]
                         [--models claude=...,codex=...] [--prism both|on|off]
                         [--trials N] [--phase pilot|remaining|full]
                         [--concurrency N] [--out DIR] [--preflight-only]
  bench.py list-suites
  bench.py list-tasks   --suite <name>
  bench.py index        [--results-dir DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
for _d in (HARNESS, HARNESS / "runners", HARNESS / "aggregate",
          HARNESS / "build", HARNESS / "scoring"):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from lib import runner_core as rc  # noqa: E402
from lib import scoring as sc  # noqa: E402
from lib import suites  # noqa: E402
from lib.pricing import GPT55_PRICING, add_gpt55_cost  # noqa: E402

AGENT_ARM_PREFIX = {"claude": "sonnet", "codex": "gpt55"}
DEFAULT_MODELS = {"claude": "claude-sonnet-5", "codex": "gpt-5.5"}
CORPUS_ROOT = Path(os.environ.get("GVG_CORPUS_ROOT", Path.home() / "gvg-corpus/e2e-2026"))
SEED = 20260908


def arms_for(agents: list[str], prism: str) -> list[str]:
    """Build the arm list from agent x prism selection.

    prism "both" -> native+prism per agent (the standard 2x2 matrix);
    "on"/"off" -> a single Prism state per agent, for a narrowed/smoke run.
    """
    suffixes = {"both": ["native", "prism"], "on": ["prism"], "off": ["native"]}[prism]
    # Suffix-major, agent-minor -- matches the legacy ARMS ordering used by
    # coding_suite.py/product_impact_suite.py: all natives, then all prisms.
    return [f"{AGENT_ARM_PREFIX[agent]}_{suffix}" for suffix in suffixes for agent in agents]


def parse_kv(value: str | None, defaults: dict[str, str]) -> dict[str, str]:
    result = dict(defaults)
    if not value:
        return result
    for pair in value.split(","):
        key, _, val = pair.partition("=")
        if key and val:
            result[key] = val
    return result


def repo_for(task: dict) -> Path:
    return CORPUS_ROOT / task["repo"].replace("/", "__")


def pristine_archive_for_task(task: dict) -> tuple[bytes, dict[str, str], list[str]]:
    return rc.pristine_archive(repo_for(task), task["base_commit"], task["instance_id"])


def prompt_for_coding(task: dict) -> str:
    return """Work only in the repository in your current directory. Do not use the network,
git history, benchmark files, saved answers, memory, skills, or delegated agents. Fix the SOURCE
code so the issue below is resolved. Do not modify tests, docs, changelogs, or configuration.
Make the smallest robust change. Investigate, edit, and run a narrow relevant test if time permits;
do not commit. Dependencies are preinstalled; use `python -m pytest` for narrow tests. You have a
strict five-minute work budget. A patch present at timeout will still be scored.

ISSUE:
""" + task["problem_statement"]


def build_task_manifest_entry(task_id: str, task: dict, path: Path, category: str | None,
                              validation: dict, archive: bytes, pristine: dict, excluded: list[str]) -> dict:
    return {
        "task": task_id, "pin": task["base_commit"], "category": category,
        "validation": validation, "task_sha256": rc.sha(path),
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "source_files": len(pristine), "excluded_steering_files": excluded,
    }


def cmd_list_suites(args: argparse.Namespace) -> int:
    for name in suites.list_suites():
        kind = suites.suite_kind(name) or "(undeclared)"
        n = len(suites.list_tasks(name))
        print(f"{name}\t{kind}\t{n} tasks")
    return 0


def cmd_list_tasks(args: argparse.Namespace) -> int:
    for ref in suites.list_tasks(args.suite):
        print(f"{ref.id}\t{ref.category or '-'}\t{'pilot' if ref.pilot else ''}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    results_dir = Path(args.results_dir).resolve()
    out_path = Path(args.out).resolve()
    seen = set()
    rows = []
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("run_dir"), row.get("cell_id"))
            if key not in seen:
                seen.add(key)
                rows.append(row)
    for summary_path in sorted(results_dir.rglob("summary.json")):
        run_dir = summary_path.parent
        try:
            manifest = json.loads((run_dir / "manifest.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            manifest = {}
        try:
            summary = json.loads(summary_path.read_text())
        except json.JSONDecodeError:
            continue
        models = manifest.get("models", {})
        for row in summary.get("rows", []):
            cell_id = row.get("cell_id")
            key = (str(run_dir), cell_id)
            if key in seen:
                continue
            seen.add(key)
            arm = row.get("arm", "")
            agent = "claude" if arm.startswith("sonnet") else "codex" if arm.startswith("gpt55") else arm
            prism = "on" if arm.endswith("prism") else "off" if arm.endswith("native") else None
            rows.append({
                "suite": manifest.get("study"), "task": row.get("task"), "agent": agent,
                "model": models.get("sonnet") if agent == "claude" else models.get("gpt"),
                "prism": prism, "trial": row.get("trial", 1),
                "tokens": row.get("total_tokens"), "turns": row.get("turns"),
                "wall_s": row.get("wall_s"), "cost_usd": row.get("cost_usd"),
                "resolved": row.get("resolved"), "run_dir": str(run_dir),
                "cell_id": cell_id,
                "timestamp": manifest.get("started_utc"),
            })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"INDEXED {len(rows)} cells -> {out_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    kind = suites.suite_kind(args.suite)
    if kind != "coding":
        raise SystemExit(
            f"bench.py run: suite {args.suite!r} has kind={kind!r}; only 'coding' suites "
            "(patch + docker_eval) are supported by `run` today. Impact/localization suites "
            "(structured site-list answers) are scored via harness/lib/scoring.py but are not "
            "yet wired into `bench.py run` -- use harness/runners/product_impact_suite.py for "
            "those until that support lands."
        )
    import docker_eval  # noqa: E402 (kind=coding only; avoids an unconditional docker dependency)

    agents = args.agents.split(",")
    for agent in agents:
        if agent not in AGENT_ARM_PREFIX:
            raise SystemExit(f"unknown agent: {agent!r} (expected claude, codex)")
    models = parse_kv(args.models, DEFAULT_MODELS)
    arms = arms_for(agents, args.prism)

    if args.tasks:
        task_ids = args.tasks.split(",")
    else:
        task_ids = suites.task_ids_for_phase(args.suite, args.phase)
    refs = {ref.id: ref for ref in suites.list_tasks(args.suite)}

    out = args.out or str(HARNESS / "results" / f"bench-{args.suite}-{time.strftime('%Y%m%d-%H%M%S')}")
    root = Path(out).resolve()
    if root.exists():
        raise SystemExit(f"run dir already exists: {root}")
    root.mkdir(parents=True)
    prism_source = rc.resolve_prism_binary(args.prism_binary)
    binary = root / "prism-bin"
    shutil.copy2(prism_source, binary)
    prism_cli = root / "bin" / "prism"
    prism_cli.parent.mkdir()
    shutil.copy2(binary, prism_cli)

    cfg = rc.AgentConfig(sonnet_model=models["claude"], gpt_model=models["codex"],
                        timeout_s=300, max_budget_usd="1.50", permission_mode="skip",
                        tools="Read,Grep,Glob,Bash,Edit,Write",
                        allowed_tools="Read,Grep,Glob,Bash,Edit,Write,mcp__prism",
                        project_doc_max_bytes=32768, output_schema=False,
                        concurrency=args.concurrency)

    tasks, templates, task_manifest = {}, {}, []
    for task_id in task_ids:
        ref = refs.get(task_id)
        path = ref.path if ref else suites.resolve_task_path(args.suite, task_id)
        task = json.loads(path.read_text())
        validation = docker_eval.validate(task)
        if not validation["valid"]:
            raise RuntimeError(f"{task_id}: validation failed: {validation}")
        task.update(fail_to_pass=validation["fail_to_pass"], pass_to_pass=validation["pass_to_pass"])
        archive, pristine, excluded = pristine_archive_for_task(task)
        rc.dump(root / "tasks" / path.name, task)
        base, baseline = rc.make_git_template(root, task_id, archive)
        env_dir = rc.prepare_environment(root, task_id, base)
        base_setup_files = rc.template_setup_files(base)
        prism, prism_setup_files = rc.make_prism_template(root, binary, task_id, base)
        tasks[task_id] = task
        templates[task_id] = (base, prism, baseline, base_setup_files, prism_setup_files, env_dir)
        task_manifest.append(build_task_manifest_entry(
            task_id, task, path, ref.category if ref else None, validation,
            archive, pristine, excluded))

    versions = {
        "claude": rc.command(["claude", "--version"]).decode().strip(),
        "codex": rc.command(["codex", "--version"]).decode().strip(),
        "prism": rc.command([str(binary), "version"]).decode().strip(),
    }
    manifest = {
        "schema_version": 1, "study": f"bench-{args.suite}", "status": "preflight",
        "phase": args.phase, "suite": args.suite,
        "tasks": task_manifest, "arms": arms, "models": models,
        "planned_cells": len(task_ids) * len(arms), "timeout_s": cfg.timeout_s,
        "concurrency": args.concurrency, "trials": args.trials, "retries": 0,
        "versions": versions,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hashes": {"runner": rc.sha(Path(__file__)), "prism_binary": rc.sha(binary)},
        "gpt55_pricing": GPT55_PRICING,
        "scoring": "Every patch, including timeout patches, is scored with held-out FAIL_TO_PASS/PASS_TO_PASS tests",
        "prompt_pairing": "identical within task across all selected arms",
        "setup_timing": "dependency installation and Prism initialization recorded outside agent wall time",
    }
    rc.dump(root / "manifest.json", manifest)
    print(f"PREFLIGHT PASS: {len(task_ids)} tasks, {manifest['planned_cells']} cells, {versions}", flush=True)
    if args.preflight_only:
        manifest["status"] = "preflight_only"
        rc.dump(root / "manifest.json", manifest)
        return 0

    rows = []
    rng = random.Random(SEED)
    task_order = list(task_ids)
    rng.shuffle(task_order)
    manifest["status"] = "running"
    rc.dump(root / "manifest.json", manifest)

    def finalize_coding(cell: rc.Cell, rec: dict, final: str) -> dict:
        if cell.arm.startswith("gpt55"):
            add_gpt55_cost(rec)
        baseline = cell.extra["baseline"]
        setup_files = cell.extra["setup_files"]
        diff, changed_files, non_source = rc.source_diff(cell.work, baseline, setup_files)
        (cell.out / "agent.diff").write_text(diff)
        rec["task"] = cell.extra["task_id"]
        return {
            "task": cell.extra["task_id"], "changed_files": changed_files,
            "non_source_changes": non_source, "diff_lines": diff.count("\n"),
            "has_diff": bool(diff.strip()),
        }

    for wave, task_id in enumerate(task_order, 1):
        base, prism, baseline, base_setup_files, prism_setup_files, env_dir = templates[task_id]
        offset = (task_ids.index(task_id) + wave - 1) % len(arms)
        order = arms[offset:] + arms[:offset]
        print(f"WAVE {wave}/{len(task_ids)} {task_id} order={order}", flush=True)
        cells = []
        for arm in order:
            template = prism if arm.endswith("prism") else base
            setup_files = prism_setup_files if arm.endswith("prism") else base_setup_files
            key = f"{task_id}.{arm}"
            prompt = prompt_for_coding(tasks[task_id])
            cell = rc.prepare_cell(root, key, arm, template, cfg, binary, prompt,
                                   env_dir=env_dir,
                                   prism_cli_dir=(root / "bin") if arm.endswith("prism") else None,
                                   extra={"task_id": task_id, "baseline": baseline,
                                          "setup_files": setup_files})
            cells.append(cell)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(rc.run_cell, cell, cfg, finalize_coding) for cell in cells]
            for future in concurrent.futures.as_completed(futures):
                rows.append(future.result())
        rc.dump(root / "summary.json", {"status": "agents_complete", "rows": rows})

    print(f"SCORING {len(rows)} cells with held-out tests", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        def score_one(row):
            diff = sc.read_diff(root / "evidence" / row["cell_id"])
            t0 = time.monotonic()
            result = sc.score_coding_cell(tasks[row["task"]], diff)
            row["score_wall_s"] = round(time.monotonic() - t0, 3)
            row["score"] = result
            row["resolved"] = bool(result.get("resolved"))
            rc.dump(root / "evidence" / row["cell_id"] / "measurement.json", row)
            return row
        rows = [f.result() for f in concurrent.futures.as_completed(
            [pool.submit(score_one, row) for row in rows])]

    valid = sum(bool(r.get("audited_valid")) for r in rows)
    harness_errors = sum(bool((r.get("score") or {}).get("harness_error")) for r in rows)
    protocol_violations = sum(bool(r.get("violations")) for r in rows)
    status = ("complete" if len(rows) == len(task_ids) * len(arms) and
              not harness_errors and not protocol_violations else "audit_incomplete")
    rc.dump(root / "summary.json", {
        "status": status, "completed": len(rows), "valid": valid,
        "timeouts": sum(bool(r.get("timed_out")) for r in rows),
        "measurement_incomplete": sum(not bool(r.get("measurement_complete")) for r in rows),
        "agent_errors": sum(bool(r.get("agent_error")) for r in rows),
        "protocol_violations": protocol_violations, "harness_errors": harness_errors,
        "resolved": sum(r["resolved"] for r in rows), "rows": rows,
    })
    manifest.update(status=status, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rc.dump(root / "manifest.json", manifest)
    print(f"FINISHED {status}: {root}", flush=True)
    return 0 if status == "complete" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run a benchmark suite")
    run_p.add_argument("--suite", required=True)
    run_p.add_argument("--tasks", help="comma-separated task ids (overrides --phase)")
    run_p.add_argument("--agents", default="claude,codex")
    run_p.add_argument("--models", help="claude=<model>,codex=<model>")
    run_p.add_argument("--prism", choices=("both", "on", "off"), default="both")
    run_p.add_argument("--prism-binary", default=None,
                       help="path to the prism binary to use -- a system install, a pinned "
                            "release, or one built on the fly (default: $PRISM_BINARY, "
                            "PATH, or ~/bin/prism -- see lib.runner_core.resolve_prism_binary)")
    run_p.add_argument("--trials", type=int, default=1)
    run_p.add_argument("--phase", choices=("pilot", "remaining", "full"), default="pilot")
    run_p.add_argument("--concurrency", type=int, default=4)
    run_p.add_argument("--out", dest="out", default=None,
                       help="run directory (default: harness/results/bench-<suite>-<timestamp>)")
    run_p.add_argument("--preflight-only", action="store_true")
    run_p.set_defaults(func=cmd_run)

    ls_p = sub.add_parser("list-suites", help="list available suites")
    ls_p.set_defaults(func=cmd_list_suites)

    lt_p = sub.add_parser("list-tasks", help="list task ids in a suite")
    lt_p.add_argument("--suite", required=True)
    lt_p.set_defaults(func=cmd_list_tasks)

    idx_p = sub.add_parser("index", help="rebuild the results index")
    idx_p.add_argument("--results-dir", default=str(HARNESS / "results"))
    idx_p.add_argument("--out", default=str(HARNESS / "results" / "index.jsonl"))
    idx_p.set_defaults(func=cmd_index)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
