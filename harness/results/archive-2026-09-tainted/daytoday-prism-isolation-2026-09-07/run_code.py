"""Forced-first-call Prism isolation: two hidden-test coding tasks x two models."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

RESEARCH = Path("/Users/tapabratapal/Projects/provasign/research")
HARNESS = RESEARCH / "harness"
TASK_ROOT = HARNESS / "tasks-e2e-meaningful"
PRISM_SOURCE = Path("/Users/tapabratapal/bin/prism")
READ_RUNNER = Path("/private/tmp/prism-daytoday-readonly.py")
sys.path.insert(0, str(HARNESS))
import docker_eval  # noqa: E402

spec = importlib.util.spec_from_file_location("readonly_runner", READ_RUNNER)
ro = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(ro)

TASK_IDS = ["pallets__click__pr3244", "pallets__werkzeug__pr3081"]
ARMS = ["sonnet_prism", "gpt55_prism"]
SONNET_MODEL = "claude-sonnet-5"
GPT_MODEL = "gpt-5.5"
LIMIT_S = 180
SEED = 20260907
PRISM_TOOLS = ro.PRISM_TOOLS


def dump(path: Path, value) -> None:
    ro.dump(path, value)


def command(args: list[str], cwd=None, check=True) -> bytes:
    return subprocess.run(args, cwd=cwd, capture_output=True, check=check).stdout


def is_steering(path: Path) -> bool:
    return ro.is_steering(path)


def repo_for(task: dict) -> Path:
    return Path("/Users/tapabratapal/gvg-corpus/e2e-2026") / task["repo"].replace("/", "__")


def pristine_archive(task: dict) -> tuple[bytes, dict[str, str], list[str]]:
    repo = repo_for(task)
    resolved = command(["git", "-C", str(repo), "rev-parse", task["base_commit"] + "^{commit}"]).decode().strip()
    if resolved != task["base_commit"]:
        raise RuntimeError(f"{task['instance_id']}: pin mismatch {resolved}")
    archive = command(["git", "-C", str(repo), "archive", task["base_commit"]])
    files, excluded = {}, []
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        for member in tf:
            path = Path(member.name)
            if is_steering(path):
                excluded.append(member.name)
            elif member.isfile():
                files[member.name] = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
    return archive, files, excluded


def extract_archive(archive: bytes, dest: Path) -> None:
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        def filt(member, _destination):
            return None if is_steering(Path(member.name)) else member
        tf.extractall(dest, filter=filt)


def make_templates(root: Path, binary: Path, task: dict, archive: bytes) -> tuple[Path, Path, str]:
    key = task["instance_id"]
    base = root / "templates" / key / "base"
    prism = root / "templates" / key / "prism"
    extract_archive(archive, base)
    command(["git", "init", "-q"], base)
    command(["git", "add", "-A"], base)
    command(["git", "-c", "user.name=Benchmark", "-c", "user.email=benchmark@invalid",
             "commit", "-qm", "pinned baseline"], base)
    baseline = command(["git", "rev-parse", "HEAD"], base).decode().strip()
    shutil.copytree(base, prism)
    t0 = time.monotonic()
    indexed = subprocess.run([str(binary), "index", str(prism)], cwd=prism,
                             capture_output=True, text=True, timeout=300)
    dump(root / "templates" / key / "index.json",
         {"wall_s": time.monotonic() - t0, "exit_code": indexed.returncode,
          "stdout": indexed.stdout, "stderr": indexed.stderr})
    if indexed.returncode:
        raise RuntimeError(f"{key}: indexing failed")
    return base, prism, baseline


def prompt_for(task: dict, has_prism: bool) -> str:
    terms = ("CliRunner,fileno,isolation" if task["instance_id"] == "pallets__click__pr3244"
             else "MultipartDecoder,_parse_data,receive_data")
    forced = (f"BEFORE ANY OTHER TOOL, make exactly one prism_query call using the issue as the query "
              f"and these terms: {terms}. Use that returned context first. Do not call another Prism "
              "tool; after the one required call, use native reads/searches only when needed.\n\n"
              if has_prism else "")
    prompt = """Work only in the repository in your current directory. Do not use the network,
git history, benchmark files, saved answers, memory, skills, or delegated agents. Fix the SOURCE
code so the issue below is resolved. Do not modify tests, docs, changelogs, or configuration.
Make the smallest robust change. Investigate, edit, and run a narrow relevant test if time permits;
do not commit. You have a strict three-minute work budget.

""" + forced + """

ISSUE:
""" + task["problem_statement"]
    if has_prism:
        prompt += "\nPrism MCP and native reads/searches are available under the rule above.\n"
    else:
        prompt += "\nUse native file reads and text searches for investigation.\n"
    return prompt


def build_command(root: Path, out: Path, work: Path, arm: str, prompt: str) -> list[str]:
    has_prism = arm.endswith("prism")
    if arm.startswith("sonnet"):
        settings = {"claudeMdExcludes": ["/**"], "autoMemoryEnabled": False,
                    "disableAllHooks": True, "enabledPlugins": {}}
        return [
            shutil.which("claude"), "-p", prompt, "--model", SONNET_MODEL,
            "--effort", "medium", "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", "0.75", "--dangerously-skip-permissions",
            "--strict-mcp-config", "--mcp-config", str(out / "mcp.json"),
            "--settings", json.dumps(settings), "--setting-sources", "",
            "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
            "--tools", "Read,Grep,Glob,Bash,Edit,Write",
            "--allowedTools", "Read,Grep,Glob,Bash,Edit,Write,mcp__prism",
        ]
    cmd = [
        shutil.which("codex"), "exec", "--ignore-user-config", "--ephemeral",
        "-s", "workspace-write", "-C", str(work), "--json", "--skip-git-repo-check",
        "-m", GPT_MODEL, "-o", str(out / "final.txt"),
    ]
    cfg = [
        'approval_policy="never"', 'model_reasoning_effort="medium"',
        "project_doc_max_bytes=0", 'web_search="disabled"',
        "features.multi_agent=false", "features.memories=false", "features.hooks=false",
        "features.apps=false", "skills.max_context_tokens=1",
    ]
    if has_prism:
        cfg += [
            "mcp_servers.prism.command=" + json.dumps(str(root / "prism-v0.72.0")),
            "mcp_servers.prism.args=" + json.dumps(["mcp", str(work)]),
            "mcp_servers.prism.required=true",
        ]
        cfg += [f'mcp_servers.prism.tools.{name}.approval_mode="approve"' for name in PRISM_TOOLS]
    for value in cfg:
        cmd += ["-c", value]
    return cmd + [prompt]


def prepare_cell(root: Path, task: dict, arm: str, template: Path, baseline: str) -> dict:
    key = task["instance_id"] + "." + arm
    out, work = root / "evidence" / key, root / "work" / key
    out.mkdir(parents=True)
    shutil.copytree(template, work)
    has_prism = arm.endswith("prism")
    mcp = {"mcpServers": {}}
    if has_prism:
        mcp["mcpServers"]["prism"] = {"type": "stdio", "command": str(root / "prism-v0.72.0"),
                                             "args": ["mcp", str(work)]}
    dump(out / "mcp.json", mcp)
    prompt = prompt_for(task, has_prism)
    (out / "prompt.txt").write_text(prompt)
    cmd = build_command(root, out, work, arm, prompt)
    dump(out / "command.json", cmd)
    return {"key": key, "out": out, "work": work, "task": task, "arm": arm,
            "cmd": cmd, "baseline": baseline, "invocation_id": str(uuid.uuid4())}


def diff_for(cell: dict) -> str:
    work, task = cell["work"], cell["task"]
    command(["git", "add", "-A"], work, check=False)
    excludes = [f":(exclude){p}" for p in task.get("test_modules", [])]
    excludes += [":(exclude).grove", ":(exclude).prism", ":(exclude).shale"]
    return command(["git", "diff", "--cached", "--binary", cell["baseline"], "--", ".", *excludes],
                   work, check=False).decode(errors="replace")


def audit(rec: dict, calls: list[dict], arm: str) -> None:
    prism_calls, native_commands, signatures = [], [], []
    if arm.startswith("sonnet"):
        for call in calls:
            name, value = call.get("name", ""), call.get("input") or {}
            if name.startswith("mcp__prism__"):
                prism_calls.append(name); signatures.append(name + json.dumps(value, sort_keys=True))
            elif name == "Bash":
                native_commands.append(value.get("command", ""))
    else:
        for call in calls:
            if call.get("type") == "mcp_tool_call" and call.get("server") == "prism":
                name = call.get("tool", ""); value = call.get("arguments") or {}
                prism_calls.append(name); signatures.append(name + json.dumps(value, sort_keys=True))
            elif call.get("type") == "command_execution":
                native_commands.append(call.get("command", ""))
    violations = []
    if arm.endswith("native") and (prism_calls or any(ro.invokes_prism(x) for x in native_commands)):
        violations.append("native arm used Prism")
    elif arm.endswith("prism") and len(prism_calls) != 1:
        violations.append(f"forced-first-call arm made {len(prism_calls)} Prism calls, expected exactly 1")
    rec.update(prism_calls=prism_calls, native_commands=native_commands,
               duplicate_prism_calls=len(signatures) - len(set(signatures)), violations=violations)


def run_cell(cell: dict) -> dict:
    out, work, arm = cell["out"], cell["work"], cell["arm"]
    env = os.environ.copy(); env.pop("CLAUDECODE", None)
    rg = shutil.which("rg")
    env["PATH"] = ":".join(dict.fromkeys(([str(Path(rg).parent)] if rg else []) +
                                          ["/opt/homebrew/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    t0, started, timed_out = time.monotonic(), time.time(), False
    print("START " + cell["key"], flush=True)
    with (out / "stdout.jsonl").open("w") as stdout, (out / "stderr.txt").open("w") as stderr:
        proc = subprocess.Popen(cell["cmd"], cwd=work, env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            proc.wait(timeout=LIMIT_S)
        except subprocess.TimeoutExpired:
            timed_out = True; ro.stop(proc)
    events = ro.read_events(out / "stdout.jsonl")
    if arm.startswith("sonnet"):
        rec, final, calls = ro.summarize_sonnet(events, out)
    else:
        rec, final, calls = ro.summarize_codex(events, out)
    (out / "final.txt").write_text(final)
    audit(rec, calls, arm)
    diff = diff_for(cell)
    (out / "agent.diff").write_text(diff)
    changed_files = command(["git", "diff", "--cached", "--name-only", cell["baseline"]], work,
                            check=False).decode().splitlines()
    rec.update(cell_id=cell["key"], task=cell["task"]["instance_id"], arm=arm,
               invocation_id=cell["invocation_id"], started_at=started,
               wall_s=round(time.monotonic() - t0, 3), exit_code=proc.returncode,
               timed_out=timed_out, changed_files=changed_files,
               diff_lines=diff.count("\n"), has_diff=bool(diff.strip()),
               audited_valid=bool(proc.returncode == 0 and not timed_out and
                                  rec.get("measurement_complete") and not rec.get("agent_error") and
                                  not rec["violations"]))
    dump(out / "measurement.json", rec)
    print("DONE " + json.dumps({"cell": cell["key"], "valid": rec["audited_valid"],
          "diff": rec["diff_lines"], "turns": rec.get("turns"), "tokens": rec.get("total_tokens"),
          "cost": rec.get("cost_usd"), "tools": rec.get("tool_calls"),
          "prism": len(rec.get("prism_calls", []))}), flush=True)
    return rec


def score_cell(root: Path, row: dict, task: dict) -> dict:
    diff = (root / "evidence" / row["cell_id"] / "agent.diff").read_text()
    t0 = time.monotonic()
    try:
        result = docker_eval.score(task, diff) if diff.strip() else {"resolved": False, "empty_diff": True}
    except Exception as exc:
        result = {"resolved": False, "harness_error": repr(exc)}
    row["score_wall_s"] = round(time.monotonic() - t0, 3)
    row["score"] = result
    row["resolved"] = bool(result.get("resolved"))
    dump(root / "evidence" / row["cell_id"] / "measurement.json", row)
    print("SCORED " + json.dumps({"cell": row["cell_id"], "resolved": row["resolved"],
                                  "wall": row["score_wall_s"], "detail": result}), flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--run-dir", required=True)
    ap.add_argument("--preflight-only", action="store_true"); args = ap.parse_args()
    root = Path(args.run_dir).resolve()
    if root.exists(): raise SystemExit(f"run dir exists: {root}")
    root.mkdir(parents=True); binary = root / "prism-v0.72.0"; shutil.copy2(PRISM_SOURCE, binary)
    shutil.copy2(Path(__file__), root / "run_code.py")
    tasks, templates, task_manifest = {}, {}, []
    for task_id in TASK_IDS:
        path = TASK_ROOT / (task_id + ".json"); task = json.loads(path.read_text())
        archive, pristine, excluded = pristine_archive(task)
        base, prism, baseline = make_templates(root, binary, task, archive)
        tasks[task_id] = task; templates[task_id] = (base, prism, baseline)
        dump(root / "tasks" / path.name, task)
        task_manifest.append({"task": task_id, "pin": task["base_commit"],
                              "task_sha256": ro.sha(path), "archive_sha256": hashlib.sha256(archive).hexdigest(),
                              "source_files": len(pristine), "excluded_steering_files": excluded})
    versions = {"claude": command(["claude", "--version"]).decode().strip(),
                "codex": command(["codex", "--version"]).decode().strip(),
                "prism": command([str(binary), "version"]).decode().strip()}
    manifest = {"schema_version": 1, "study": "forced-first-call-prism-isolation-code", "status": "preflight",
                "tasks": task_manifest, "arms": ARMS, "models": {"sonnet": SONNET_MODEL, "gpt": GPT_MODEL},
                "planned_cells": 4, "timeout_s": LIMIT_S, "concurrency": 2, "trials": 1,
                "retries": 0, "versions": versions, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "scoring": "held-out test_patch + FAIL_TO_PASS/PASS_TO_PASS via docker_eval"}
    dump(root / "manifest.json", manifest)
    print(f"PREFLIGHT PASS: 2 tasks, 4 cells, {versions}", flush=True)
    if args.preflight_only: return 0
    rows = []; rng = random.Random(SEED); task_order = list(TASK_IDS); rng.shuffle(task_order)
    manifest["status"] = "running"; dump(root / "manifest.json", manifest)
    for wave, task_id in enumerate(task_order, 1):
        task = tasks[task_id]; base, prism, baseline = templates[task_id]
        offset = (TASK_IDS.index(task_id) + wave - 1) % len(ARMS)
        order = ARMS[offset:] + ARMS[:offset]
        print(f"WAVE {wave}/2 {task_id} order={order}", flush=True)
        cells = [prepare_cell(root, task, arm, prism if arm.endswith("prism") else base, baseline)
                 for arm in order]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for fut in concurrent.futures.as_completed([pool.submit(run_cell, c) for c in cells]):
                rows.append(fut.result())
        dump(root / "summary.json", {"status": "agents_complete", "rows": rows})
    print("SCORING 4 cells with held-out tests", flush=True)
    by_id = {task_id: tasks[task_id] for task_id in TASK_IDS}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(score_cell, root, row, by_id[row["task"]]) for row in rows]
        rows = [f.result() for f in concurrent.futures.as_completed(futures)]
    valid = sum(bool(r.get("audited_valid")) for r in rows)
    harness_errors = sum(bool((r.get("score") or {}).get("harness_error")) for r in rows)
    status = "complete" if valid == 4 and not harness_errors else "audit_incomplete"
    dump(root / "summary.json", {"status": status, "completed": len(rows), "valid": valid,
                                 "resolved": sum(r["resolved"] for r in rows), "rows": rows})
    manifest.update(status=status, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    dump(root / "manifest.json", manifest)
    print(f"FINISHED {status}: {root}", flush=True)
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
