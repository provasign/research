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


VALID_TOOLS = ("native", "prism", "codegraph")


def prism_flag_to_tools(prism: str) -> list[str]:
    """Back-compat mapping for the old `--prism both|on|off` flag to the
    generalized `--tools` list."""
    return {"both": ["native", "prism"], "on": ["prism"], "off": ["native"]}[prism]


def arms_for(agents: list[str], tools: list[str]) -> list[str]:
    """Build the arm list from agent x tools selection.

    `tools` is a list drawn from `{"native", "prism", "codegraph"}`, e.g.
    `["native", "prism"]` for the standard 2x2(x3) matrix, or a single tool
    for a narrowed/smoke run.
    """
    # Tool-major, agent-minor -- matches the legacy ARMS ordering used by
    # coding_suite.py/product_impact_suite.py: all natives, then all prisms
    # (and now, any further tools, in the order given).
    return [f"{AGENT_ARM_PREFIX[agent]}_{tool}" for tool in tools for agent in agents]


def parse_kv(value: str | None, defaults: dict[str, str]) -> dict[str, str]:
    result = dict(defaults)
    if not value:
        return result
    for pair in value.split(","):
        key, _, val = pair.partition("=")
        if key and val:
            result[key] = val
    return result


def run_status(rows: list[dict], planned_cells: int) -> str:
    """A scored run is complete only when every planned cell passed its audit."""
    if (len(rows) != planned_cells or
            any(not row.get("audited_valid") or
                "resolved" not in (row.get("score") or {}) or
                (row.get("score") or {}).get("harness_error") for row in rows)):
        return "audit_incomplete"
    return "complete"


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
            tool = rc.active_tool(arm)
            # Legacy "prism" field: "on" for a prism arm, "off" otherwise
            # (including codegraph, which didn't exist when this field was
            # designed -- "off" is the least-surprising value for it). New
            # code should read "tool" instead.
            prism = "on" if tool == "prism" else "off"
            rows.append({
                "suite": manifest.get("study"), "task": row.get("task"), "agent": agent,
                "model": models.get("sonnet") if agent == "claude" else models.get("gpt"),
                "prism": prism, "tool": tool, "trial": row.get("trial", 1),
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
    # --tools takes precedence when given; --prism both|on|off is kept as a
    # back-compat alias mapped to the equivalent --tools list.
    if args.tools:
        tools = [value.strip() for value in args.tools.split(",") if value.strip()]
    else:
        tools = prism_flag_to_tools(args.prism)
    for tool in tools:
        if tool not in VALID_TOOLS:
            raise SystemExit(f"unknown tool: {tool!r} (expected one of {VALID_TOOLS})")
    arms = arms_for(agents, tools)

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

    # Only resolve/copy a tool's binary when that tool is actually selected
    # -- a prism-only or native-only run must not require codegraph (or vice
    # versa) to be installed.
    tool_binaries: dict[str, Path] = {}
    tool_cli_dirs: dict[str, Path] = {}
    if "prism" in tools:
        prism_source = rc.resolve_prism_binary(args.prism_binary)
        binary = root / "prism-bin"
        shutil.copy2(prism_source, binary)
        cli_dir = root / "bin" / "prism"
        cli_dir.mkdir(parents=True)
        shutil.copy2(binary, cli_dir / "prism")
        tool_binaries["prism"] = binary
        tool_cli_dirs["prism"] = cli_dir
    if "codegraph" in tools:
        # Unlike prism (a self-contained static binary, safe to byte-copy),
        # codegraph's installed executable is a shell wrapper that locates a
        # sibling `node` runtime and `lib/dist/bin/codegraph.js` relative to
        # its own real location (`$(dirname "$(readlink resolved) ")/..`) --
        # byte-copying it elsewhere breaks that lookup ("No such file or
        # directory" for node). The wrapper explicitly chases symlinks back
        # to the real bundle dir, so symlink instead of copy.
        codegraph_source = rc.resolve_codegraph_binary(args.codegraph_binary)
        codegraph_binary = root / "codegraph-bin"
        codegraph_binary.symlink_to(codegraph_source)
        cli_dir = root / "bin" / "codegraph"
        cli_dir.mkdir(parents=True)
        (cli_dir / "codegraph").symlink_to(codegraph_source)
        tool_binaries["codegraph"] = codegraph_binary
        tool_cli_dirs["codegraph"] = cli_dir

    cfg = rc.AgentConfig(sonnet_model=models["claude"], gpt_model=models["codex"],
                        timeout_s=300, max_budget_usd="1.50", permission_mode="skip",
                        tools="Read,Grep,Glob,Bash,Edit,Write",
                        allowed_tools="Read,Grep,Glob,Bash,Edit,Write,mcp__prism,mcp__codegraph",
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
        tool_templates: dict[str, tuple[Path, list[str]]] = {"native": (base, base_setup_files)}
        if "prism" in tools:
            tool_templates["prism"] = rc.make_prism_template(
                root, tool_binaries["prism"], task_id, base)
        if "codegraph" in tools:
            tool_templates["codegraph"] = rc.make_codegraph_template(
                root, tool_binaries["codegraph"], task_id, base)
        tasks[task_id] = task
        templates[task_id] = (baseline, env_dir, tool_templates)
        task_manifest.append(build_task_manifest_entry(
            task_id, task, path, ref.category if ref else None, validation,
            archive, pristine, excluded))

    versions = {
        "claude": rc.command(["claude", "--version"]).decode().strip(),
        "codex": rc.command(["codex", "--version"]).decode().strip(),
    }
    hashes = {"runner": rc.sha(Path(__file__))}
    if "prism" in tools:
        versions["prism"] = rc.command([str(tool_binaries["prism"]), "version"]).decode().strip()
        hashes["prism_binary"] = rc.sha(tool_binaries["prism"])
    if "codegraph" in tools:
        versions["codegraph"] = rc.command(
            [str(tool_binaries["codegraph"]), "--version"]).decode().strip()
        hashes["codegraph_binary"] = rc.sha(tool_binaries["codegraph"])
    manifest = {
        "schema_version": 1, "study": f"bench-{args.suite}", "status": "preflight",
        "phase": args.phase, "suite": args.suite,
        "tasks": task_manifest, "arms": arms, "models": models, "tools": tools,
        "planned_cells": len(task_ids) * len(arms) * args.trials, "timeout_s": cfg.timeout_s,
        "concurrency": args.concurrency, "trials": args.trials, "retries": 0,
        # Claude-arm reasoning capture (see AgentConfig.thinking_display). Per
        # cell, measurement.json `thinking_chars` says whether it actually
        # landed -- the flag can be silently dropped server-side.
        "thinking_display": cfg.thinking_display,
        "versions": versions,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hashes": hashes,
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
            "task": cell.extra["task_id"], "trial": cell.extra["trial"],
            "changed_files": changed_files,
            "non_source_changes": non_source, "diff_lines": diff.count("\n"),
            "has_diff": bool(diff.strip()),
        }

    # One wave per (task, trial): each trial gets its own freshly-shuffled
    # task order and its own arm-rotation offset, matching
    # product_impact_suite.py's scheme, so --trials N actually schedules N
    # independent repeats per task/arm instead of only recording N in the
    # manifest while running each cell once.
    waves = []
    for trial in range(1, args.trials + 1):
        order = list(task_ids)
        rng.shuffle(order)
        for task_id in order:
            offset = (task_ids.index(task_id) + trial - 1) % len(arms)
            waves.append((task_id, trial, arms[offset:] + arms[:offset]))

    for wave_number, (task_id, trial, order) in enumerate(waves, 1):
        baseline, env_dir, tool_templates = templates[task_id]
        print(f"WAVE {wave_number}/{len(waves)} {task_id} trial={trial} order={order}", flush=True)
        cells = []
        for arm in order:
            tool = rc.active_tool(arm)
            template, setup_files = tool_templates[tool]
            key = f"{task_id}.r{trial}.{arm}"
            prompt = prompt_for_coding(tasks[task_id])
            cell = rc.prepare_cell(root, key, arm, template, cfg, tool_binaries.get(tool), prompt,
                                   env_dir=env_dir,
                                   tool_cli_dir=tool_cli_dirs.get(tool),
                                   extra={"task_id": task_id, "trial": trial, "baseline": baseline,
                                          "setup_files": setup_files, "allow_source_edits": True})
            cells.append(cell)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(rc.run_cell, cell, cfg, finalize_coding) for cell in cells]
            for future in concurrent.futures.as_completed(futures):
                rows.append(future.result())
        rc.dump(root / "summary.json", {"status": "agents_complete", "rows": rows})
        if any(not row.get("audited_valid") for row in rows[-len(cells):]):
            print("STOP: invalid agent cell; later waves will not run", flush=True)
            break

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
    status = run_status(rows, manifest["planned_cells"])
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
    run_p.add_argument("--tools", default=None,
                       help="comma-separated tool selection from {native, prism, codegraph} "
                            "-- each arm gets access to ONLY its own tool. Takes precedence "
                            "over --prism when both are given. Default (neither given): "
                            "native,prism (today's --prism both).")
    run_p.add_argument("--prism", choices=("both", "on", "off"), default="both",
                       help="back-compat alias for --tools (both -> native,prism; on -> "
                            "prism; off -> native); ignored when --tools is given")
    run_p.add_argument("--prism-binary", default=None,
                       help="path to the prism binary to use -- a system install, a pinned "
                            "release, or one built on the fly (default: $PRISM_BINARY, "
                            "PATH, or ~/bin/prism -- see lib.runner_core.resolve_prism_binary). "
                            "Only resolved when prism is among the selected --tools.")
    run_p.add_argument("--codegraph-binary", default=None,
                       help="path to the codegraph binary to use (default: $CODEGRAPH_BINARY "
                            "or PATH -- see lib.runner_core.resolve_codegraph_binary). Only "
                            "resolved when codegraph is among the selected --tools.")
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
