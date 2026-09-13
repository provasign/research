"""Forced-first-call Prism isolation: two search tasks x two model heads."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import uuid

RESEARCH = Path("/Users/tapabratapal/Projects/provasign/research")
HARNESS = RESEARCH / "harness"
PRISM_SOURCE = Path("/Users/tapabratapal/bin/prism")
sys.path.insert(0, str(HARNESS))

from rescore_java import load_index, normalize  # noqa: E402
from schema import Answer, Site, Task  # noqa: E402
from score import SCORER_VERSION, score  # noqa: E402
from usage_account import cli_usage  # noqa: E402

TASK_IDS = [
    "flaskcov-frompyfile",
    "flaskcov-tag",
]
ARMS = ["sonnet_prism", "gpt55_prism"]
SONNET_MODEL = "claude-sonnet-5"
GPT_MODEL = "gpt-5.5"
PRISM_TOOLS = [
    "prism_search", "prism_query", "prism_read", "prism_lookup",
    "prism_change_impact", "prism_verify",
]
SEED = 20260907
LIMIT_S = 90


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args: list[str], cwd: Path | str | None = None) -> bytes:
    return subprocess.run(args, cwd=cwd, capture_output=True, check=True).stdout


def read_events(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def invokes_prism(value: str) -> bool:
    try:
        tokens = shlex.split(value)
    except ValueError:
        tokens = value.split()
    return any(Path(token).name.startswith("prism") for token in tokens)


def result_bytes(value) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.encode())
    return len(json.dumps(value, sort_keys=True).encode())


def line_index(task_id: str) -> dict | None:
    prefix = task_id.split("-", 1)[0]
    path = HARNESS / "java-oracle" / f"{prefix}-lineindex.json"
    return load_index(path) if path.exists() else None


def normalize_answer(answer: Answer, task_id: str) -> list[str]:
    before = [str(site) for site in answer.sites]
    index = line_index(task_id)
    if index is not None:
        answer.sites = [Site.parse(normalize(str(site), index)) for site in answer.sites]
    return before


def summarize_sonnet(events: list[dict], out: Path) -> tuple[dict, str, list[dict]]:
    finals = [e for e in events if e.get("type") == "result"]
    inits = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    rec: dict = {"session_id": inits[-1].get("session_id") if inits else None,
                 "init": inits[-1] if inits else None}
    final = ""
    if finals:
        raw = finals[-1]
        dump(out / "result.raw.json", raw)
        usage = cli_usage(raw)
        rec.update(
            model_observed=sorted((raw.get("modelUsage") or {}).keys()),
            usage=usage,
            input_tokens=usage["input_total"],
            output_tokens=usage["tokens"]["output"],
            total_tokens=(usage["input_total"] + usage["tokens"]["output"]
                          if usage["input_total"] is not None
                          and usage["tokens"]["output"] is not None else None),
            cost_usd=usage["cost_usd_cli"],
            cost_basis="Claude CLI estimate (not invoice)",
            turns=raw.get("num_turns"),
            measurement_complete=usage["usage_complete"],
            agent_error=bool(raw.get("is_error")),
        )
        final = raw.get("result") or ""
    else:
        rec.update(measurement_complete=False, agent_error=True, cost_usd=None)

    calls, seen = [], set()
    call_names = {}
    tool_result_bytes = {}
    tool_errors = []
    for event in events:
        for block in (event.get("message") or {}).get("content", []):
            if block.get("type") == "tool_use":
                identity = block.get("id")
                call_names[identity] = block.get("name", "")
                if identity not in seen:
                    seen.add(identity)
                    calls.append(block)
            elif block.get("type") == "tool_result":
                identity = block.get("tool_use_id")
                tool_result_bytes[identity] = result_bytes(block.get("content"))
                if block.get("is_error"):
                    tool_errors.append({"tool": call_names.get(identity, ""),
                                        "content": block.get("content")})
    rec["tool_errors"] = tool_errors
    rec["prism_result_bytes"] = sum(
        tool_result_bytes.get(call.get("id"), 0) for call in calls
        if str(call.get("name", "")).startswith("mcp__prism__")
    )
    return rec, final, calls


def summarize_codex(events: list[dict], out: Path) -> tuple[dict, str, list[dict]]:
    starts = [e for e in events if e.get("type") == "thread.started"]
    turns = [e for e in events if e.get("type") == "turn.completed"]
    valid_usage = bool(turns) and all(
        all(type(e.get("usage", {}).get(k)) is int and e["usage"][k] >= 0
            for k in ("input_tokens", "cached_input_tokens", "output_tokens"))
        for e in turns
    )
    rec: dict = {
        "session_id": starts[-1].get("thread_id") if starts else None,
        "model_observed": GPT_MODEL,
        "usage_raw": [e.get("usage") for e in turns],
        "turns": len(turns),
        "measurement_complete": valid_usage,
        "agent_error": any(e.get("type") in ("turn.failed", "error") for e in events),
        "cost_usd": None,
        "cost_basis": "Not estimated in-run",
    }
    if valid_usage:
        usage = {k: sum(e["usage"][k] for e in turns)
                 for k in ("input_tokens", "cached_input_tokens", "output_tokens")}
        rec.update(
            input_tokens=usage["input_tokens"],
            cache_read_tokens=usage["cached_input_tokens"],
            output_tokens=usage["output_tokens"],
            total_tokens=usage["input_tokens"] + usage["output_tokens"],
        )
        if usage["cached_input_tokens"] > usage["input_tokens"]:
            rec["measurement_complete"] = False
    calls = []
    final = ""
    for event in events:
        item = event.get("item") or {}
        if event.get("type") == "item.completed":
            if item.get("type") in (
                "command_execution", "mcp_tool_call", "web_search",
                "collab_tool_call", "file_change",
            ):
                calls.append(item)
            elif item.get("type") == "agent_message":
                final = item.get("text") or final
    if (out / "final.txt").exists():
        final = (out / "final.txt").read_text()
    rec["tool_errors"] = [
        {"tool": call.get("tool"), "error": call.get("error")}
        for call in calls if call.get("type") == "mcp_tool_call"
        and (call.get("error") or call.get("status") != "completed")
    ]
    rec["prism_result_bytes"] = sum(
        result_bytes(call.get("result")) for call in calls
        if call.get("type") == "mcp_tool_call" and call.get("server") == "prism"
    )
    return rec, final, calls


def audit_calls(rec: dict, calls: list[dict], arm: str) -> None:
    prism_calls = []
    native_commands = []
    signatures = []
    violations = []
    if arm.startswith("sonnet"):
        for call in calls:
            name = call.get("name", "")
            value = call.get("input") or {}
            if name.startswith("mcp__prism__"):
                prism_calls.append(name)
                signatures.append(name + ":" + json.dumps(value, sort_keys=True))
            elif name == "Bash":
                native_commands.append(value.get("command", ""))
            elif name in ("Agent", "Task", "WebFetch", "WebSearch"):
                violations.append("delegation or network tool used")
    else:
        for call in calls:
            kind = call.get("type")
            if kind == "mcp_tool_call" and call.get("server") == "prism":
                prism_calls.append(call.get("tool", ""))
                signatures.append(call.get("tool", "") + ":" +
                                  json.dumps(call.get("arguments") or {}, sort_keys=True))
            elif kind == "command_execution":
                native_commands.append(call.get("command", ""))
            elif kind in ("collab_tool_call", "web_search", "file_change"):
                violations.append("delegation, network tool, or edit used")
    if arm.endswith("native"):
        if prism_calls or any(invokes_prism(command) for command in native_commands):
            violations.append("native arm used Prism")
    elif len(prism_calls) != 1:
        violations.append(f"forced-first-call arm made {len(prism_calls)} Prism calls, expected exactly 1")
    rec.update(
        calls=calls,
        tool_calls=len(calls),
        prism_calls=prism_calls,
        duplicate_prism_calls=len(signatures) - len(set(signatures)),
        native_commands=native_commands,
        violations=violations,
    )


def prompt_for(task: Task, has_prism: bool) -> str:
    target_rules = ("Each site must be <repo-relative-path>:<test_function>. Enumerate test functions "
                    "only, including indirect call-chain coverage; do not emit production helpers."
                    if task.task_type == "coverage" else
                    "Each site must be <repo-relative-path>:<FunctionOrMethodName>. Enumerate only the "
                    "production-source functions/methods that must change; do not include tests or types.")
    forced = ("BEFORE ANY OTHER TOOL, make exactly one prism_change_impact call for the named target "
              "method. Use that returned context first. Do not call another Prism tool; after the one "
              "required call, use native reads/searches only when needed.\n\n" if has_prism else "")
    common = """Analyze only the repository in your current working directory. Do not edit source files.
Do not use the network, other repository copies, benchmark files, git history, saved answers,
memory, skills, or delegated agents. Use local repository evidence to solve this task.
""" + forced + """
Return ONLY one JSON object with keys sites (array of strings), complete (boolean),
and unresolved (array of strings). """ + target_rules + """ Deduplicate the same path and
function. Claim complete only if justified.

ISSUE:
""" + task.prompt
    if not has_prism:
        return common + "\nTOOLS: Use native file reads and text searches to investigate.\n"
    return common + "\nPrism MCP and native reads/searches are available under the rule above.\n"


def is_steering(path: Path) -> bool:
    return path.name in ("AGENTS.md", "CLAUDE.md", ".mcp.json") or any(
        part in (".codex", ".claude") for part in path.parts
    )


def pristine_archive(task: Task) -> tuple[bytes, dict[str, str], list[str]]:
    repo = task.repo
    if task.id == "gin-4645":
        repo = "/Users/tapabratapal/gvg-corpus/gin"
    elif task.id.startswith("grafana-"):
        repo = "/Users/tapabratapal/gvg-corpus/grafana"
    pin = command(["git", "-C", repo, "rev-parse", f"{task.pin}^{{commit}}"])
    resolved = pin.decode().strip()
    if not resolved.startswith(task.pin):
        raise RuntimeError(f"{task.id}: task pin resolves to {resolved}, expected {task.pin}")
    archive = command(["git", "-C", repo, "archive", task.pin])
    files = {}
    excluded = []
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        for member in tf:
            path = Path(member.name)
            if is_steering(path):
                excluded.append(member.name)
                continue
            if member.isfile():
                files[member.name] = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
    return archive, files, excluded


def build_command(root: Path, out: Path, work: Path, arm: str, prompt: str) -> list[str]:
    has_prism = arm.endswith("prism")
    if arm.startswith("sonnet"):
        settings = {
            "claudeMdExcludes": ["/**"], "autoMemoryEnabled": False,
            "disableAllHooks": True, "enabledPlugins": {},
        }
        return [
            shutil.which("claude"), "-p", prompt, "--model", SONNET_MODEL,
            "--effort", "medium", "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", "0.75", "--restricted", "--permission-mode", "dontAsk",
            "--permission-prompts", "none", "--strict-mcp-config", "--mcp-config",
            str(out / "mcp.json"), "--settings", json.dumps(settings),
            "--setting-sources", "", "--disable-slash-commands", "--no-chrome",
            "--no-session-persistence", "--tools", "Read,Grep,Glob,Bash",
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
        "project_doc_max_bytes=0", 'web_search="disabled"',
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
                for name in PRISM_TOOLS]
    for value in cfg:
        cmd += ["-c", value]
    return cmd + [prompt]


def prepare_cell(root: Path, binary: Path, task: Task, archive: bytes,
                 pristine: dict[str, str], trial: int, arm: str,
                 base_template: Path, prism_template: Path) -> dict:
    key = f"{task.id}.r{trial}.{arm}"
    out = root / "evidence" / key
    work = root / "work" / key
    out.mkdir(parents=True)
    shutil.copytree(prism_template if arm.endswith("prism") else base_template, work)
    command(["git", "init", "-q"], work)
    has_prism = arm.endswith("prism")
    mcp = {"mcpServers": {}}
    if has_prism:
        dump(out / "index.json", {"wall_s": 0, "exit_code": 0,
                                   "shared_preindexed_snapshot": str(prism_template)})
        mcp["mcpServers"]["prism"] = {
            "type": "stdio", "command": str(binary), "args": ["mcp", str(work)],
        }
    dump(out / "mcp.json", mcp)
    prompt = prompt_for(task, has_prism)
    (out / "prompt.txt").write_text(prompt)
    cmd = build_command(root, out, work, arm, prompt)
    dump(out / "command.json", cmd)
    return {
        "key": key, "out": out, "work": work, "cmd": cmd, "task": task,
        "trial": trial, "arm": arm, "pristine": pristine,
        "invocation_id": str(uuid.uuid4()),
    }


def run_cell(cell: dict) -> dict:
    out, work, arm, task = cell["out"], cell["work"], cell["arm"], cell["task"]
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    rg = shutil.which("rg")
    path_parts = ([str(Path(rg).parent)] if rg else []) + [
        "/opt/homebrew/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin",
    ]
    env["PATH"] = ":".join(dict.fromkeys(path_parts))
    start = time.monotonic()
    started = time.time()
    print("START " + cell["key"], flush=True)
    timed_out = False
    with (out / "stdout.jsonl").open("w") as stdout, (out / "stderr.txt").open("w") as stderr:
        proc = subprocess.Popen(
            cell["cmd"], cwd=work, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, start_new_session=True,
        )
        try:
            proc.wait(timeout=LIMIT_S)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(proc)
    events = read_events(out / "stdout.jsonl")
    if arm.startswith("sonnet"):
        rec, final, calls = summarize_sonnet(events, out)
    else:
        rec, final, calls = summarize_codex(events, out)
    (out / "final.txt").write_text(final)
    audit_calls(rec, calls, arm)
    answer = Answer.parse(final)
    rec["answer_before_normalization"] = normalize_answer(answer, task.id)
    rec["answer"] = {
        "sites": [str(site) for site in answer.sites], "complete": answer.complete,
        "unresolved": answer.unresolved,
    }
    card = score(task, answer, arm, cell["trial"])
    changed = [path for path, digest in cell["pristine"].items()
               if not (work / path).exists() or sha(work / path) != digest]
    known = set(cell["pristine"])
    unexpected = []
    for path in work.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(work)
        if any(part in (".git", ".prism", ".grove", ".pytest_cache", "__pycache__") for part in rel.parts):
            continue
        if str(rel) not in known:
            unexpected.append(str(rel))
    rec.update(
        cell_id=cell["key"], task=task.id, arm=arm, trial=cell["trial"],
        invocation_id=cell["invocation_id"], started_at=started,
        wall_s=round(time.monotonic() - start, 3), exit_code=proc.returncode,
        timed_out=timed_out, scorer_version=SCORER_VERSION,
        source_changed=changed, unexpected_files=unexpected, score=card.to_dict(),
    )
    rec["audited_valid"] = bool(
        proc.returncode == 0 and not timed_out and rec.get("measurement_complete")
        and not rec.get("agent_error") and not rec["violations"]
        and not changed and not unexpected and answer.sites
    )
    dump(out / "measurement.json", rec)
    print("DONE " + json.dumps({
        "cell": cell["key"], "valid": rec["audited_valid"],
        "R": card.recall, "P": card.precision, "turns": rec.get("turns"),
        "tokens": rec.get("total_tokens"), "cost": rec.get("cost_usd"),
        "tools": rec.get("tool_calls"), "prism": len(rec.get("prism_calls", [])),
        "duplicate_prism": rec.get("duplicate_prism_calls"),
        "prism_bytes": rec.get("prism_result_bytes"),
    }), flush=True)
    return rec


def latin_waves(tasks: list[str], trials: int) -> list[tuple[str, int, list[str]]]:
    rng = random.Random(SEED)
    waves = []
    for trial in range(1, trials + 1):
        order = list(tasks)
        rng.shuffle(order)
        for task_id in order:
            offset = (tasks.index(task_id) + trial - 1) % len(ARMS)
            arms = ARMS[offset:] + ARMS[:offset]
            waves.append((task_id, trial, arms))
    return waves


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.run_dir).resolve()
    if root.exists():
        raise SystemExit(f"run dir already exists: {root}")
    root.mkdir(parents=True)
    binary = root / "prism-v0.72.0"
    shutil.copy2(PRISM_SOURCE, binary)
    shutil.copy2(Path(__file__), root / "run_panel.py")
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
    dump(root / "answer-schema.json", schema)
    prepared = {}
    shared_templates = {}
    task_manifest = []
    for task_id in TASK_IDS:
        path = HARNESS / "tasks" / f"{task_id}.json"
        task = Task.load(path)
        archive, pristine, excluded = pristine_archive(task)
        dump(root / "tasks" / path.name, json.loads(path.read_text()))
        template_key = hashlib.sha256((task.repo + "\0" + task.pin).encode()).hexdigest()[:12]
        if template_key not in shared_templates:
            base_template = root / "templates" / template_key / "base"
            prism_template = root / "templates" / template_key / "prism"
            base_template.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
                def filter_member(member, _destination):
                    return None if is_steering(Path(member.name)) else member
                tf.extractall(base_template, filter=filter_member)
            shutil.copytree(base_template, prism_template)
            start = time.monotonic()
            indexed = subprocess.run([str(binary), "index", str(prism_template)],
                                     cwd=prism_template, capture_output=True, text=True,
                                     timeout=300)
            dump(root / "templates" / template_key / "index.json",
                 {"wall_s": time.monotonic() - start, "exit_code": indexed.returncode,
                  "stdout": indexed.stdout, "stderr": indexed.stderr})
            if indexed.returncode:
                raise RuntimeError(f"{task.id}: shared indexing failed")
            shared_templates[template_key] = (base_template, prism_template)
        prepared[task_id] = (task, archive, pristine, *shared_templates[template_key])
        task_manifest.append({
            "task": task_id, "pin": task.pin, "task_sha256": sha(path),
            "archive_sha256": hashlib.sha256(archive).hexdigest(),
            "source_files": len(pristine), "excluded_steering_files": excluded,
        })
    waves = latin_waves(TASK_IDS, args.trials)
    versions = {
        "claude": command(["claude", "--version"]).decode().strip(),
        "codex": command(["codex", "--version"]).decode().strip(),
        "prism": command([str(binary), "version"]).decode().strip(),
    }
    manifest = {
        "schema_version": 1, "study": "forced-first-call-prism-isolation-readonly", "status": "preflight", "seed": SEED,
        "tasks": task_manifest, "arms": ARMS, "trials": args.trials,
        "waves": waves, "planned_cells": len(waves) * len(ARMS),
        "counterbalancing": "seeded task shuffle per trial; cyclic arm rotation per task/trial",
        "models": {"sonnet": SONNET_MODEL, "gpt": GPT_MODEL},
        "effort": "medium", "timeout_s": LIMIT_S, "concurrency": 2,
        "retries": 0,
        "failure_policy": "Archive every attempt; no quality retries. Explicit transport/setup failures remain invalid and require a separately labeled rerun.",
        "scorer_version": SCORER_VERSION,
        "hashes": {
            "runner": sha(Path(__file__)), "prism_binary": sha(binary),
            **{name: sha(HARNESS / name)
               for name in ("schema.py", "score.py", "usage_account.py", "rescore_java.py")},
        },
        "versions": versions,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    dump(root / "manifest.json", manifest)
    print(f"RUN_DIR={root}", flush=True)
    print(f"PREFLIGHT PASS: {len(TASK_IDS)} tasks, {manifest['planned_cells']} cells, {versions}", flush=True)
    if args.preflight_only:
        manifest["status"] = "preflight_only"
        dump(root / "manifest.json", manifest)
        return 0

    rows = []
    manifest["status"] = "running"
    dump(root / "manifest.json", manifest)
    for wave_number, (task_id, trial, arm_order) in enumerate(waves, 1):
        task, archive, pristine, base_template, prism_template = prepared[task_id]
        print(f"WAVE {wave_number}/{len(waves)} {task_id} trial={trial} order={arm_order}", flush=True)
        cells = [prepare_cell(root, binary, task, archive, pristine, trial, arm,
                              base_template, prism_template)
                 for arm in arm_order]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_cell, cell) for cell in cells]
            for future in concurrent.futures.as_completed(futures):
                rows.append(future.result())
                dump(root / "summary.json", {
                    "status": "running", "completed": len(rows),
                    "planned": manifest["planned_cells"], "rows": rows,
                })
        print(f"WAVE DONE {len(rows)}/{manifest['planned_cells']}", flush=True)
    valid = sum(bool(row.get("audited_valid")) for row in rows)
    status = "complete" if valid == manifest["planned_cells"] else "audit_incomplete"
    dump(root / "summary.json", {
        "status": status, "completed": len(rows), "valid": valid,
        "planned": manifest["planned_cells"], "rows": rows,
    })
    manifest["status"] = status
    manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dump(root / "manifest.json", manifest)
    print(f"FINISHED {status}: {root}", flush=True)
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
