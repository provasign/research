"""Normal-product change-impact suite: identical prompts, native versus Prism."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import uuid


RESEARCH = Path(__file__).resolve().parents[1]
HARNESS = RESEARCH / "harness"
BASE_RUNNER = HARNESS / "runs/four-head-impact-2026-09-07-stopped/run_panel.py"
PRISM_SOURCE = Path(os.environ.get("PRISM_V072_BINARY", Path.home() / "bin/prism"))

spec = importlib.util.spec_from_file_location("impact_base", BASE_RUNNER)
base = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(base)

TASK_IDS = [
    "jackson-jsonnode-get",
    "jackson-settable-set",
    "typeorm-driver-escape",
    "django-quotename",
    "jackson-writetypeprefix",
    "guava-forwarding-delegate",
    "jackson-serialize",
    "grafana-checkhealth-impact",
    "grafana-querydata-impact",
]
PILOT_TASKS = ["jackson-jsonnode-get", "grafana-checkhealth-impact"]
ARMS = ["sonnet_native", "gpt55_native", "sonnet_prism", "gpt55_prism"]
SONNET_MODEL = "claude-sonnet-5"
GPT_MODEL = "gpt-5.5"
LIMIT_S = 300
SEED = 20260908


def prompt_for(task: base.Task) -> str:
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


def build_command(root: Path, out: Path, work: Path, arm: str, prompt: str) -> list[str]:
    has_prism = arm.endswith("prism")
    if arm.startswith("sonnet"):
        settings = {"autoMemoryEnabled": False, "disableAllHooks": True, "enabledPlugins": {}}
        return [
            shutil.which("claude"), "-p", prompt, "--model", SONNET_MODEL,
            "--effort", "medium", "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", "1.50", "--dangerously-skip-permissions",
            "--strict-mcp-config", "--mcp-config", str(out / "mcp.json"),
            "--settings", json.dumps(settings), "--setting-sources", "",
            "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
            "--tools", "Read,Grep,Glob,Bash",
            "--allowedTools", "Read,Grep,Glob,Bash,mcp__prism",
        ]
    cmd = [
        shutil.which("codex"), "exec", "--ignore-user-config", "--ephemeral",
        "-s", "workspace-write", "-C", str(work), "--json", "--skip-git-repo-check",
        "-m", GPT_MODEL, "--output-schema", str(root / "answer-schema.json"),
        "-o", str(out / "final.txt"),
    ]
    cfg = [
        'approval_policy="never"', 'model_reasoning_effort="medium"',
        "project_doc_max_bytes=32768", 'web_search="disabled"',
        "features.multi_agent=false", "features.memories=false",
        "features.hooks=false", "features.apps=false", "skills.max_context_tokens=1",
    ]
    if has_prism:
        cfg += [
            "mcp_servers.prism.command=" + json.dumps(str(root / "prism-v0.72.0")),
            "mcp_servers.prism.args=" + json.dumps(["mcp", str(work)]),
            "mcp_servers.prism.required=true",
        ]
        cfg += [f'mcp_servers.prism.tools.{name}.approval_mode="approve"'
                for name in base.PRISM_TOOLS]
    for value in cfg:
        cmd += ["-c", value]
    return cmd + [prompt]


def snapshot_files(work: Path) -> dict[str, str]:
    files = {}
    for path in work.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(work)
        if any(part in (".git", ".prism", ".grove") for part in rel.parts):
            continue
        files[str(rel)] = base.sha(path)
    return files


def prepare_cell(root: Path, binary: Path, task: base.Task, archive: bytes,
                 pristine: dict[str, str], trial: int, arm: str) -> dict:
    cell = base.prepare_cell(root, binary, task, archive, pristine, trial, arm)
    has_prism = arm.endswith("prism")
    if has_prism:
        started = time.monotonic()
        initialized = subprocess.run(
            [str(binary), "init", "--no-permissions", str(cell["work"])],
            cwd=cell["work"], input="n\n", capture_output=True, text=True, timeout=300,
        )
        base.dump(cell["out"] / "product-init.json", {
            "wall_s": round(time.monotonic() - started, 3),
            "exit_code": initialized.returncode,
            "stdout": initialized.stdout,
            "stderr": initialized.stderr,
        })
        if initialized.returncode:
            raise RuntimeError(f"{cell['key']}: product init failed")
    cell["pristine"] = snapshot_files(cell["work"])
    prompt = prompt_for(task)
    (cell["out"] / "prompt.txt").write_text(prompt)
    cmd = build_command(root, cell["out"], cell["work"], arm, prompt)
    if has_prism:
        product_path = os.pathsep.join([
            str(root / "bin"), "/opt/homebrew/bin", "/usr/bin", "/bin",
            "/usr/sbin", "/sbin",
        ])
        cmd = ["/usr/bin/env", "PATH=" + product_path, *cmd]
    cell["cmd"] = cmd
    cell["invocation_id"] = str(uuid.uuid4())
    base.dump(cell["out"] / "command.json", cmd)
    return cell


def audit_calls(rec: dict, calls: list[dict], arm: str) -> None:
    prism_calls, native_commands, signatures, violations = [], [], [], []
    if arm.startswith("sonnet"):
        for call in calls:
            name, value = call.get("name", ""), call.get("input") or {}
            if name.startswith("mcp__prism__"):
                prism_calls.append(name)
                signatures.append(name + json.dumps(value, sort_keys=True))
            elif name == "Bash":
                native_commands.append(value.get("command", ""))
            elif name in ("Agent", "Task", "WebFetch", "WebSearch"):
                violations.append("delegation or network tool used")
    else:
        for call in calls:
            kind = call.get("type")
            if kind == "mcp_tool_call" and call.get("server") == "prism":
                name, value = call.get("tool", ""), call.get("arguments") or {}
                prism_calls.append(name)
                signatures.append(name + json.dumps(value, sort_keys=True))
            elif kind == "command_execution":
                native_commands.append(call.get("command", ""))
            elif kind in ("collab_tool_call", "web_search", "file_change"):
                violations.append("delegation, network tool, or edit used")
    prism_cli_commands = [value for value in native_commands if base.invokes_prism(value)]
    if arm.endswith("native") and (prism_calls or prism_cli_commands):
        violations.append("native arm used Prism")
    rec.update(
        calls=calls, tool_calls=len(calls), prism_calls=prism_calls,
        prism_cli_commands=prism_cli_commands,
        prism_actions=len(prism_calls) + len(prism_cli_commands),
        duplicate_prism_calls=len(signatures) - len(set(signatures)),
        native_commands=native_commands, violations=violations,
    )


original_codex_summary = base.summarize_codex


def summarize_codex(events: list[dict], out: Path) -> tuple[dict, str, list[dict]]:
    rec, final, calls = original_codex_summary(events, out)
    if rec.get("measurement_complete"):
        from coding_suite import add_gpt55_cost
        add_gpt55_cost(rec)
    return rec, final, calls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--phase", choices=("pilot", "remaining", "full"), default="pilot")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.phase == "pilot":
        task_ids = PILOT_TASKS
    elif args.phase == "remaining":
        task_ids = [task_id for task_id in TASK_IDS if task_id not in PILOT_TASKS]
    else:
        task_ids = TASK_IDS
    root = Path(args.run_dir).resolve()
    if root.exists():
        raise SystemExit(f"run dir already exists: {root}")
    root.mkdir(parents=True)
    binary = root / "prism-v0.72.0"
    shutil.copy2(PRISM_SOURCE, binary)
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
    base.dump(root / "answer-schema.json", schema)
    prepared, task_manifest = {}, []
    for task_id in task_ids:
        path = HARNESS / "tasks" / f"{task_id}.json"
        task = base.Task.load(path)
        archive, pristine, excluded = base.pristine_archive(task)
        base.dump(root / "tasks" / path.name, json.loads(path.read_text()))
        prepared[task_id] = (task, archive, pristine)
        task_manifest.append({
            "task": task_id, "pin": task.pin, "task_sha256": base.sha(path),
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
        "claude": base.command(["claude", "--version"]).decode().strip(),
        "codex": base.command(["codex", "--version"]).decode().strip(),
        "prism": base.command([str(binary), "version"]).decode().strip(),
    }
    manifest = {
        "schema_version": 1, "study": "product-impact-suite-v1", "status": "preflight",
        "phase": args.phase, "seed": SEED, "tasks": task_manifest, "arms": ARMS,
        "trials": args.trials, "waves": waves,
        "planned_cells": len(waves) * len(ARMS),
        "models": {"sonnet": SONNET_MODEL, "gpt": GPT_MODEL},
        "effort": "medium", "timeout_s": LIMIT_S, "concurrency": 4, "retries": 0,
        "prompt_pairing": "identical task prompt across all four arms",
        "integration": "Prism init generated product files; normal tool choice; MCP and CLI available",
        "scorer_version": base.SCORER_VERSION,
        "hashes": {"runner": base.sha(Path(__file__)), "prism_binary": base.sha(binary)},
        "versions": versions,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    base.dump(root / "manifest.json", manifest)
    print(f"PREFLIGHT PASS: {len(task_ids)} tasks, {manifest['planned_cells']} cells, {versions}", flush=True)
    if args.preflight_only:
        manifest["status"] = "preflight_only"
        base.dump(root / "manifest.json", manifest)
        return 0

    base.GPT_MODEL = GPT_MODEL
    base.LIMIT_S = LIMIT_S
    base.audit_calls = audit_calls
    base.summarize_codex = summarize_codex
    rows = []
    manifest["status"] = "running"
    base.dump(root / "manifest.json", manifest)
    for number, (task_id, trial, arm_order) in enumerate(waves, 1):
        task, archive, pristine = prepared[task_id]
        print(f"WAVE {number}/{len(waves)} {task_id} trial={trial} order={arm_order}", flush=True)
        cells = [prepare_cell(root, binary, task, archive, pristine, trial, arm)
                 for arm in arm_order]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(base.run_cell, cell) for cell in cells]
            for future in concurrent.futures.as_completed(futures):
                rows.append(future.result())
                base.dump(root / "summary.json", {
                    "status": "running", "completed": len(rows),
                    "planned": manifest["planned_cells"], "rows": rows,
                })
    valid = sum(bool(row.get("audited_valid")) for row in rows)
    status = "complete" if valid == manifest["planned_cells"] else "audit_incomplete"
    base.dump(root / "summary.json", {
        "status": status, "completed": len(rows), "valid": valid,
        "planned": manifest["planned_cells"], "rows": rows,
    })
    manifest.update(status=status,
                    finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    base.dump(root / "manifest.json", manifest)
    print(f"FINISHED {status}: {root}", flush=True)
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
