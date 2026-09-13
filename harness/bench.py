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
  bench.py rescore      --out DIR [--concurrency N]
                         (rebuild/score cells from an existing run dir's
                         transcripts after a crash; no agents run)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import re
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
from lib.cell_metrics import claude_navigation_metrics  # noqa: E402
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


TEST_CMD_BY_LANGUAGE = {
    "python": "python -m pytest", "go": "go test ./...",
    "rust": "cargo test", "ts": "npx jest", "js": "npx jest",
}


def prompt_for_coding(task: dict, timeout_s: int = 300) -> str:
    test_cmd = TEST_CMD_BY_LANGUAGE.get(task.get("language", "python"), "the project's own test runner")
    budget = f"{round(timeout_s / 60)}-minute" if timeout_s >= 60 else f"{timeout_s}-second"
    return f"""Work only in the repository in your current directory. Do not use the network,
git history, benchmark files, saved answers, memory, skills, or delegated agents. Fix the SOURCE
code so the issue below is resolved. Do not modify tests, docs, changelogs, or configuration.
Make the smallest robust change. Investigate, edit, and run a narrow relevant test if time permits;
do not commit. Dependencies are preinstalled; use `{test_cmd}` for narrow tests. You have a
strict {budget} work budget. A patch present at timeout will still be scored.

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
    rows_by_key = {}
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("run_dir"), row.get("cell_id"))
            rows_by_key[key] = row
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
            arm = row.get("arm", "")
            agent = "claude" if arm.startswith("sonnet") else "codex" if arm.startswith("gpt55") else arm
            tool = rc.active_tool(arm)
            # Legacy "prism" field: "on" for a prism arm, "off" otherwise
            # (including codegraph, which didn't exist when this field was
            # designed -- "off" is the least-surprising value for it). New
            # code should read "tool" instead.
            prism = "on" if tool == "prism" else "off"
            indexed = {
                "suite": manifest.get("study"), "task": row.get("task"), "agent": agent,
                "model": models.get("sonnet") if agent == "claude" else models.get("gpt"),
                "prism": prism, "tool": tool, "trial": row.get("trial", 1),
                "tokens": row.get("total_tokens"), "turns": row.get("turns"),
                "wall_s": row.get("wall_s"), "cost_usd": row.get("cost_usd"),
                "resolved": row.get("resolved"), "run_dir": str(run_dir),
                "cell_id": cell_id,
                "timestamp": manifest.get("started_utc"),
                "audited_valid": row.get("audited_valid"),
                "blocked_attempts": len(row.get("network_attempts_blocked") or []),
            }
            transcript = run_dir / "evidence" / str(cell_id) / "stdout.jsonl"
            if agent == "claude" and transcript.is_file():
                indexed.update(claude_navigation_metrics(transcript))
            rows_by_key[key] = indexed
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for key in sorted(rows_by_key):
            fh.write(json.dumps(rows_by_key[key], sort_keys=True) + "\n")
    print(f"INDEXED {len(rows_by_key)} cells -> {out_path}")
    return 0


# --- shared by `run` and `rescore` -------------------------------------------

CELL_KEY_RE = re.compile(r"^(?P<task>.+)\.r(?P<trial>\d+)\.(?P<arm>[a-z0-9]+_[a-z0-9]+)$")


def cell_key_parts(key: str) -> tuple[str, int, str]:
    """`<task>.r<trial>.<arm>` -> (task, trial, arm)."""
    m = CELL_KEY_RE.match(key)
    if not m:
        raise ValueError(f"not a cell key: {key!r}")
    return m.group("task"), int(m.group("trial")), m.group("arm")


def planned_cell_keys(manifest: dict) -> list[str]:
    tasks = [t["task"] for t in manifest.get("tasks", [])]
    return [f"{task}.r{trial}.{arm}"
            for trial in range(1, int(manifest.get("trials", 1)) + 1)
            for task in tasks for arm in manifest.get("arms", [])]


def finalize_coding(cell: rc.Cell, rec: dict, final: str) -> dict:
    """Coding-suite finalize hook for rc.run_cell: the source-only diff
    against the pinned baseline, excluding dependency-setup files."""
    if cell.arm.startswith("gpt55"):
        add_gpt55_cost(rec)
    diff, changed_files, non_source = rc.source_diff(
        cell.work, cell.extra["baseline"], cell.extra["setup_files"])
    (cell.out / "agent.diff").write_text(diff)
    rec["task"] = cell.extra["task_id"]
    return {
        "task": cell.extra["task_id"], "trial": cell.extra["trial"],
        "changed_files": changed_files,
        "non_source_changes": non_source, "diff_lines": diff.count("\n"),
        "has_diff": bool(diff.strip()),
    }


def harness_error_row(cell: rc.Cell, exc: BaseException) -> dict:
    """A cell whose summarize/audit/finalize raised. Keep the run alive, mark
    the cell invalid, record the error; `bench.py rescore` rebuilds it from
    the transcript once the cause is fixed. (A permission_denied event with a
    string `message` killed a 6-cell run before scoring on 2026-09-13.)"""
    row = {"cell_id": cell.key, "arm": cell.arm, "task": cell.extra.get("task_id"),
           "trial": cell.extra.get("trial"), "audited_valid": False, "resolved": False,
           "violations": [], "harness_error": repr(exc), "measurement_complete": False}
    rc.dump(cell.out / "measurement.json", row)
    return row


def stop_reason(row: dict) -> str | None:
    """Why a finished cell should halt submission of new cells, or None.

    Only conditions that mean the *run* is broken stop it: a harness error
    (summarize/audit raised) or a protocol violation (cross-tool use, no
    successful own-tool call, approval-blocked call) -- those repeat in every
    later cell and waste money. A timeout, an agent error, or an incomplete
    measurement is an outcome of that one cell; it is recorded as invalid and
    the run continues. (2026-09-13: a sequential click cell hit the 300 s
    budget and halted a 6-cell run after 2.)"""
    if row.get("harness_error"):
        return f"harness error: {row['harness_error']}"
    if row.get("violations"):
        return "protocol violation: " + "; ".join(map(str, row["violations"]))
    return None


def score_and_summarize(root: Path, rows: list[dict], tasks: dict, manifest: dict,
                        concurrency: int) -> str:
    """Docker-score every row without a verdict, write summary.json, update
    the manifest, return the run status. Shared by `run` and `rescore`."""
    pending = [r for r in rows if r.get("resolved") is None and not r.get("harness_error")]
    print(f"SCORING {len(pending)} cells with held-out tests", flush=True)

    def score_one(row):
        diff = sc.read_diff(root / "evidence" / row["cell_id"])
        t0 = time.monotonic()
        result = sc.score_coding_cell(tasks[row["task"]], diff)
        row["score_wall_s"] = round(time.monotonic() - t0, 3)
        row["score"] = result
        row["resolved"] = bool(result.get("resolved"))
        rc.dump(root / "evidence" / row["cell_id"] / "measurement.json", row)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for future in concurrent.futures.as_completed([pool.submit(score_one, r) for r in pending]):
            future.result()
    valid = sum(bool(r.get("audited_valid")) for r in rows)
    harness_errors = sum(bool(r.get("harness_error") or (r.get("score") or {}).get("harness_error"))
                         for r in rows)
    protocol_violations = sum(bool(r.get("violations")) for r in rows)
    status = run_status(rows, manifest["planned_cells"])
    rc.dump(root / "summary.json", {
        "status": status, "completed": len(rows), "valid": valid,
        "timeouts": sum(bool(r.get("timed_out")) for r in rows),
        "measurement_incomplete": sum(not bool(r.get("measurement_complete")) for r in rows),
        "agent_errors": sum(bool(r.get("agent_error")) for r in rows),
        "protocol_violations": protocol_violations, "harness_errors": harness_errors,
        "resolved": sum(bool(r.get("resolved")) for r in rows), "rows": rows,
    })
    manifest.update(status=status, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rc.dump(root / "manifest.json", manifest)
    print(f"FINISHED {status}: {root}", flush=True)
    return status


def cmd_rescore(args: argparse.Namespace) -> int:
    """Rebuild measurement.json for any cell whose transcript exists but was
    never summarized (a crash mid-run), then score every unscored cell and
    rewrite summary.json -- all from what is already on disk, no agents run.
    Missing planned cells are reported, not started."""
    root = Path(args.out).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    tasks = {p.stem: json.loads(p.read_text()) for p in (root / "tasks").glob("*.json")}
    models = manifest.get("models", {})
    gpt_model = models.get("codex", rc.AgentConfig.gpt_model)
    rows, recovered = [], []
    for out in sorted((root / "evidence").iterdir()):
        if not (out / "stdout.jsonl").exists():
            continue
        key = out.name
        mpath = out / "measurement.json"
        if mpath.exists():
            rows.append(json.loads(mpath.read_text()))
            continue
        task_id, trial, arm = cell_key_parts(key)
        tool = rc.active_tool(arm)
        work = root / "work" / key
        template = root / "templates" / task_id / ("base" if tool == "native" else tool)
        # The work copy was cloned from the template, whose only commit is the
        # pinned baseline; the agent is told not to commit, so the root commit
        # is the baseline either way.
        baseline = rc.command(["git", "rev-list", "--max-parents=0", "HEAD"], work).decode().split()[0]
        cell = rc.Cell(key=key, out=out, work=work,
                       cmd=json.loads((out / "command.json").read_text()), arm=arm,
                       invocation_id="recovered",
                       extra={"task_id": task_id, "trial": trial, "baseline": baseline,
                              "setup_files": rc.template_setup_files(template),
                              "allow_source_edits": True})
        events = rc.read_events(out / "stdout.jsonl")
        if arm.startswith("sonnet"):
            rec, final, calls = rc.summarize_sonnet(events, out)
        else:
            rec, final, calls = rc.summarize_codex(events, out, gpt_model)
        (out / "final.txt").write_text(final)
        rec["allow_source_edits"] = True
        rc.audit_calls(rec, calls, arm)
        rec["successful_own_tool_actions"] = rc.successful_own_tool_actions(events, calls, arm)
        if tool != "native" and not rec["successful_own_tool_actions"]:
            rec["violations"].append("own tool had no successful calls")
        if any("requires approval" in str(err.get("error") or err.get("content") or "")
               for err in rec.get("tool_errors", [])):
            rec["violations"].append("tool call blocked by approval policy")
        rec.update(finalize_coding(cell, rec, final))
        rec.update(
            cell_id=key, arm=arm, invocation_id="recovered", started_at=None, wall_s=None,
            exit_code=None, timed_out=False, recovered=True,
            audited_valid_basis=("recovered from transcript after a harness crash; CLI exit code "
                                 "unknown -- validity rests on a complete result event, no agent "
                                 "error, and no violations"),
        )
        rec["audited_valid"] = bool(rec.get("measurement_complete") and not rec.get("agent_error")
                                    and not rec["violations"])
        rc.dump(mpath, rec)
        rows.append(rec)
        recovered.append(key)
    rows.sort(key=lambda r: r.get("cell_id", ""))
    present = {r.get("cell_id") for r in rows}
    missing = [k for k in planned_cell_keys(manifest) if k not in present]
    print(f"RESCORE: {len(rows)} cells on disk, {len(recovered)} rebuilt from transcript: {recovered}",
          flush=True)
    if missing:
        print(f"MISSING planned cells (never ran; rescore does not start agents): {missing}", flush=True)
    manifest["rescored_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    status = score_and_summarize(root, rows, tasks, manifest, args.concurrency)
    return 0 if status == "complete" else 1


def cmd_run(args: argparse.Namespace) -> int:
    if args.concurrency < 1 or args.trials < 1:
        raise SystemExit("--concurrency and --trials must be positive")
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
                        timeout_s=args.timeout_s, max_budget_usd=args.max_budget_usd, permission_mode="skip",
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
        env_dir = rc.prepare_environment(root, task_id, base, task.get("language", "python"))
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
        # Network policy: blocked on Claude arms by --disallowedTools, on
        # Codex arms by the workspace-write sandbox; git's network path is
        # closed for both via GIT_ALLOW_PROTOCOL=file. Any shell fetch that
        # gets through is a recorded violation (measurement.json
        # `network_commands`); bare URL literals are recorded as
        # `network_suspects`, never asserted.
        "disallowed_tools": cfg.disallowed_tools,
        "network_policy": "blocked (disallowedTools / codex sandbox / GIT_ALLOW_PROTOCOL=file); shell fetches audited as violations",
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

    # A single bounded pool spans all task/trial waves. Submit lazily so an
    # invalid cell stops new work; already-running cells finish and retain
    # their evidence for rescore. This also makes a one-arm run concurrent.
    scheduled = [(task_id, trial, arm) for task_id, trial, order in waves for arm in order]
    next_cell = 0
    stopped = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending = {}
        while next_cell < len(scheduled) or pending:
            while not stopped and next_cell < len(scheduled) and len(pending) < args.concurrency:
                task_id, trial, arm = scheduled[next_cell]
                baseline, env_dir, tool_templates = templates[task_id]
                tool = rc.active_tool(arm)
                template, setup_files = tool_templates[tool]
                key = f"{task_id}.r{trial}.{arm}"
                print(f"CELL {next_cell + 1}/{len(scheduled)} {key}", flush=True)
                cell = rc.prepare_cell(
                    root, key, arm, template, cfg, tool_binaries.get(tool),
                    prompt_for_coding(tasks[task_id], args.timeout_s), env_dir=env_dir,
                    tool_cli_dir=tool_cli_dirs.get(tool),
                    extra={"task_id": task_id, "trial": trial, "baseline": baseline,
                           "setup_files": setup_files, "allow_source_edits": True},
                )
                pending[pool.submit(rc.run_cell, cell, cfg, finalize_coding)] = cell
                next_cell += 1
            if not pending:
                break
            done, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                cell = pending.pop(future)
                try:
                    row = future.result()
                except Exception as exc:  # preserve evidence and allow rescore
                    print(f"HARNESS ERROR in {cell.key}: {exc!r} -- cell marked invalid; "
                          f"rebuild with `bench.py rescore --out {root}` once fixed", flush=True)
                    row = harness_error_row(cell, exc)
                rows.append(row)
                if not row.get("audited_valid"):
                    print(f"INVALID {cell.key}: timed_out={row.get('timed_out')} "
                          f"agent_error={row.get('agent_error')} violations={row.get('violations')}",
                          flush=True)
                reason = stop_reason(row)
                if reason and not stopped:
                    stopped = True
                    print(f"STOP: {cell.key}: {reason}; no new cells submitted", flush=True)
            rc.dump(root / "summary.json", {"status": "agents_running", "rows": rows})
    order_by_key = {f"{task}.r{trial}.{arm}": i for i, (task, trial, arm) in enumerate(scheduled)}
    rows.sort(key=lambda row: order_by_key[row["cell_id"]])

    status = score_and_summarize(root, rows, tasks, manifest, args.concurrency)
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
    run_p.add_argument("--timeout-s", type=int, default=300,
                       help="per-cell wall-clock budget in seconds (default: 300, the "
                            "value every prior study used). A model that would keep working "
                            "past this is truncated regardless of task complexity -- turns "
                            "observed at 300s do not show whether a task is 'high-turn', "
                            "only what fits in 5 minutes. Raise this, not the task set, to "
                            "test whether turns grow when the cap is not binding.")
    run_p.add_argument("--max-budget-usd", default="1.50",
                       help="per-cell Claude Code spend cap (default: 1.50). Raise together "
                            "with --timeout-s -- a longer wall clock is moot if the session "
                            "hits this cap first.")
    run_p.add_argument("--phase", choices=("pilot", "remaining", "full"), default="pilot")
    run_p.add_argument("--concurrency", type=int, default=4)
    run_p.add_argument("--out", dest="out", default=None,
                       help="run directory (default: harness/results/bench-<suite>-<timestamp>)")
    run_p.add_argument("--preflight-only", action="store_true")
    run_p.set_defaults(func=cmd_run)

    rs_p = sub.add_parser("rescore", help="rebuild/score cells from an existing run dir's "
                                          "transcripts after a crash (no agents run)")
    rs_p.add_argument("--out", required=True, help="run directory to rescore")
    rs_p.add_argument("--concurrency", type=int, default=4)
    rs_p.set_defaults(func=cmd_rescore)

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
