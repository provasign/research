"""The one implementation of "invoke claude/codex with optional Prism and
parse the result".

This is the generalized descendant of
`harness/results/daytoday-four-head-2026-09-07/run_readonly.py` (frozen,
never edited -- historical `run_code.py`/`run_panel.py` snapshots under
`harness/results/*` import it directly and must keep working) merged with
the safety properties `harness/runners/coding_suite.py` layered on top:
per-task git-archive template prep, a real venv + dependency install,
a Prism-instrumented template with a byte-identical-except-Prism content
hash check, PATH isolation so native arms cannot exec the `prism` binary,
and the protocol-violation audit.

Every parameter that used to be a hardcoded module constant (model names,
timeouts, tool lists, budgets) is now a field on `AgentConfig` so a new
suite/runner needs zero code changes here -- only a different config.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

PRISM_TOOLS = [
    "prism_search", "prism_query", "prism_read", "prism_lookup",
    "prism_change_impact", "prism_verify",
]

# Env vars checked, in order, when no --prism-binary is given on the CLI.
# PRISM_BINARY is the current name; PRISM_V072_BINARY is kept only because
# older run scripts/docs still reference it.
PRISM_BINARY_ENV_VARS = ("PRISM_BINARY", "PRISM_V072_BINARY")


def resolve_prism_binary(explicit: str | None = None) -> Path:
    """Resolve the Prism binary to use for a run.

    Prism is sometimes a system install (`which prism`), sometimes a pinned
    release fetched to a fixed path, sometimes a copy built on the fly by CI
    -- callers must be able to say "use exactly this one" rather than the
    runner guessing. Resolution order: explicit CLI flag, then env var
    (`PRISM_BINARY`, legacy `PRISM_V072_BINARY`), then `PATH` (`which
    prism`), then the historical `~/bin/prism` convention. Raises a clear
    error rather than silently falling through to a binary that doesn't
    exist.
    """
    candidates: list[tuple[str, Path]] = []
    if explicit:
        candidates.append(("--prism-binary", Path(explicit).expanduser()))
    for var in PRISM_BINARY_ENV_VARS:
        value = os.environ.get(var)
        if value:
            candidates.append((f"${var}", Path(value).expanduser()))
    found = shutil.which("prism")
    if found:
        candidates.append(("PATH", Path(found)))
    candidates.append(("~/bin/prism convention", Path.home() / "bin" / "prism"))
    for source, path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    tried = "; ".join(f"{source}: {path}" for source, path in candidates)
    raise RuntimeError(
        "no usable Prism binary found. Pass --prism-binary explicitly, set "
        f"PRISM_BINARY, or install prism on PATH. Tried: {tried}"
    )


def prism_init_args(binary: Path, target: Path, *, no_permissions: bool = True) -> list[str]:
    """Build a `prism init` invocation that stays non-interactive across
    Prism versions. Older Prism releases init non-interactively by default;
    newer ones require `--harness <ids>` or they prompt (see
    `prism init --help`). Passing `--harness claude,codex` unconditionally
    is a no-op on old versions and required on new ones."""
    args = [str(binary), "init", "--harness", "claude,codex"]
    if no_permissions:
        args.append("--no-permissions")
    args.append(str(target))
    return args


# --- small shared utilities (identical to run_readonly.py) -----------------

def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args: list[str], cwd: Path | str | None = None, check: bool = True) -> bytes:
    return subprocess.run(args, cwd=cwd, capture_output=True, check=check).stdout


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


def is_steering(path: Path) -> bool:
    return path.name in ("AGENTS.md", "CLAUDE.md", ".mcp.json") or any(
        part in (".codex", ".claude") for part in path.parts
    )


# --- event-stream summarization (identical semantics to run_readonly.py) ---

def summarize_sonnet(events: list[dict], out: Path) -> tuple[dict, str, list[dict]]:
    from usage_account import cli_usage  # noqa: PLC0415 (lazy; needs aggregate/ on sys.path)

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


def summarize_codex(events: list[dict], out: Path, gpt_model: str = "gpt-5.5") -> tuple[dict, str, list[dict]]:
    starts = [e for e in events if e.get("type") == "thread.started"]
    turns = [e for e in events if e.get("type") == "turn.completed"]
    valid_usage = bool(turns) and all(
        all(type(e.get("usage", {}).get(k)) is int and e["usage"][k] >= 0
            for k in ("input_tokens", "cached_input_tokens", "output_tokens"))
        for e in turns
    )
    rec: dict = {
        "session_id": starts[-1].get("thread_id") if starts else None,
        "model_observed": gpt_model,
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
    """Protocol-violation audit: catches a native arm invoking Prism (MCP or
    CLI), delegated/networked tools, and duplicate Prism call signatures."""
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
    prism_cli_commands = [value for value in native_commands if invokes_prism(value)]
    if arm.endswith("native") and (prism_calls or prism_cli_commands):
        violations.append("native arm used Prism")
    rec.update(
        calls=calls,
        tool_calls=len(calls),
        prism_calls=prism_calls,
        prism_cli_commands=prism_cli_commands,
        prism_actions=len(prism_calls) + len(prism_cli_commands),
        duplicate_prism_calls=len(signatures) - len(set(signatures)),
        native_commands=native_commands,
        violations=violations,
    )


# --- agent invocation config -------------------------------------------------

@dataclass
class AgentConfig:
    """Everything that used to be a hardcoded module constant in
    run_readonly.py / coding_suite.py / product_impact_suite.py."""

    sonnet_model: str = "claude-sonnet-5"
    gpt_model: str = "gpt-5.5"
    effort: str = "medium"
    timeout_s: int = 300
    max_budget_usd: str = "1.50"
    # "skip" -> --dangerously-skip-permissions (coding/product suites, which
    # must edit files); "restricted" -> --restricted --permission-mode dontAsk
    # --permission-prompts none (readonly/impact suites, which must not edit).
    permission_mode: str = "skip"
    tools: str = "Read,Grep,Glob,Bash,Edit,Write"
    allowed_tools: str = "Read,Grep,Glob,Bash,Edit,Write,mcp__prism"
    project_doc_max_bytes: int = 32768
    output_schema: bool = False  # codex --output-schema <root>/answer-schema.json
    prism_tools: list[str] = field(default_factory=lambda: list(PRISM_TOOLS))
    concurrency: int = 4


def build_command(cfg: AgentConfig, root: Path, out: Path, work: Path, arm: str,
                  prompt: str, prism_binary: Path) -> list[str]:
    has_prism = arm.endswith("prism")
    if arm.startswith("sonnet"):
        settings = {"autoMemoryEnabled": False, "disableAllHooks": True, "enabledPlugins": {}}
        cmd = [
            shutil.which("claude"), "-p", prompt, "--model", cfg.sonnet_model,
            "--effort", cfg.effort, "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", cfg.max_budget_usd,
        ]
        if cfg.permission_mode == "restricted":
            cmd += ["--restricted", "--permission-mode", "dontAsk", "--permission-prompts", "none"]
        else:
            cmd += ["--dangerously-skip-permissions"]
        cmd += [
            "--strict-mcp-config", "--mcp-config", str(out / "mcp.json"),
            "--settings", json.dumps(settings), "--setting-sources", "",
            "--disable-slash-commands", "--no-chrome", "--no-session-persistence",
            "--tools", cfg.tools, "--allowedTools", cfg.allowed_tools,
        ]
        return cmd
    cmd = [
        shutil.which("codex"), "exec", "--ignore-user-config", "--ephemeral",
        "-s", "workspace-write", "-C", str(work), "--json", "--skip-git-repo-check",
        "-m", cfg.gpt_model,
    ]
    if cfg.output_schema:
        cmd += ["--output-schema", str(root / "answer-schema.json")]
    cmd += ["-o", str(out / "final.txt")]
    fcfg = [
        'approval_policy="never"', f'model_reasoning_effort="{cfg.effort}"',
        f"project_doc_max_bytes={cfg.project_doc_max_bytes}", 'web_search="disabled"',
        "features.multi_agent=false", "features.memories=false", "features.hooks=false",
        "features.apps=false", "skills.max_context_tokens=1",
    ]
    if has_prism:
        fcfg += [
            "mcp_servers.prism.command=" + json.dumps(str(prism_binary)),
            "mcp_servers.prism.args=" + json.dumps(["mcp", str(work)]),
            "mcp_servers.prism.required=true",
        ]
        fcfg += [f'mcp_servers.prism.tools.{name}.approval_mode="approve"' for name in cfg.prism_tools]
    for value in fcfg:
        cmd += ["-c", value]
    return cmd + [prompt]


# --- git archive / template preparation -------------------------------------

def pristine_archive(repo: str | Path, pin: str, task_id: str = "") -> tuple[bytes, dict[str, str], list[str]]:
    resolved = command(["git", "-C", str(repo), "rev-parse", f"{pin}^{{commit}}"]).decode().strip()
    if not resolved.startswith(pin):
        raise RuntimeError(f"{task_id or repo}: pin resolves to {resolved}, expected {pin}")
    archive = command(["git", "-C", str(repo), "archive", pin])
    files: dict[str, str] = {}
    excluded: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        for member in tf:
            path = Path(member.name)
            if is_steering(path):
                excluded.append(member.name)
                continue
            if member.isfile():
                files[member.name] = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
    return archive, files, excluded


def extract_archive(archive: bytes, dest: Path) -> None:
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
        def filt(member, _destination):
            return None if is_steering(Path(member.name)) else member
        tf.extractall(dest, filter=filt)


def template_setup_files(path: Path) -> list[str]:
    return [line[3:] for line in command(
        ["git", "status", "--porcelain", "--untracked-files=all"], path
    ).decode().splitlines()]


def template_content(path: Path) -> dict[str, str]:
    """Hash the prepared project tree, excluding VCS and Prism's index databases."""
    values = {}
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(path)
        if any(part in (".git", ".grove", ".prism") for part in rel.parts):
            continue
        values[str(rel)] = hashlib.sha256(item.read_bytes()).hexdigest()
    return values


def make_git_template(root: Path, key: str, archive: bytes) -> tuple[Path, str]:
    """Extract a pristine archive into a committed git template (the "base")."""
    base = root / "templates" / key / "base"
    extract_archive(archive, base)
    command(["git", "init", "-q"], base)
    command(["git", "add", "-A"], base)
    command(["git", "-c", "user.name=Benchmark", "-c", "user.email=benchmark@invalid",
             "commit", "-qm", "pinned baseline"], base)
    baseline = command(["git", "rev-parse", "HEAD"], base).decode().strip()
    return base, baseline


def make_prism_template(root: Path, binary: Path, key: str, base: Path) -> tuple[Path, list[str]]:
    """Copy the dependency-prepared base, install the Prism product
    integration, and verify the tree is byte-identical to `base` except for
    Prism's own files -- catches a broken install silently corrupting the
    task."""
    prism = root / "templates" / key / "prism"
    shutil.copytree(base, prism)
    t0 = time.monotonic()
    indexed = subprocess.run(prism_init_args(binary, prism), cwd=prism,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    dump(root / "templates" / key / "index.json",
         {"wall_s": time.monotonic() - t0, "exit_code": indexed.returncode,
          "stdout": indexed.stdout, "stderr": indexed.stderr})
    if indexed.returncode:
        raise RuntimeError(f"{key}: indexing failed")
    base_content = template_content(base)
    prism_content = template_content(prism)
    mismatched = sorted(path for path, digest in base_content.items()
                        if prism_content.get(path) != digest)
    if mismatched:
        raise RuntimeError(f"{key}: native/Prism template mismatch: {mismatched[:10]}")
    return prism, template_setup_files(prism)


def prepare_environment(root: Path, key: str, base: Path) -> Path:
    """Install dependencies before the timed cells and archive exact versions."""
    env_dir = root / "environments" / key
    python = shutil.which("python3.12") or shutil.which("python3")
    if not python:
        raise RuntimeError("Python is unavailable")
    t0 = time.monotonic()
    logs = []
    subprocess.run([python, "-m", "venv", str(env_dir)], check=True)
    env_python = env_dir / "bin/python"
    uv = shutil.which("uv")
    installed = False
    if uv and (base / "uv.lock").exists():
        sync_env = os.environ.copy()
        sync_env["UV_PROJECT_ENVIRONMENT"] = str(env_dir)
        result = subprocess.run(
            [uv, "sync", "--project", str(base), "--frozen", "--all-extras"],
            capture_output=True, text=True, env=sync_env,
        )
        logs.append({"target": "uv-lock", "exit_code": result.returncode,
                     "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]})
        installed = result.returncode == 0
    if not installed:
        for extra in ("dev", "test", "tests", None):
            target = str(base) if extra is None else f"{base}[{extra}]"
            result = subprocess.run(
                [str(env_python), "-m", "pip", "install", "-e", target],
                capture_output=True, text=True,
            )
            logs.append({"target": target, "exit_code": result.returncode,
                         "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]})
            if result.returncode == 0 and "does not provide the extra" not in result.stderr:
                installed = True
                break
    if not installed:
        raise RuntimeError(f"{key}: dependency installation failed")
    subprocess.run(
        [str(env_python), "-m", "pip", "install", "pytest", "pytest-timeout"],
        check=True, capture_output=True, text=True,
    )
    freeze = command([str(env_python), "-m", "pip", "freeze"]).decode()
    setup = {"wall_s": round(time.monotonic() - t0, 3), "attempts": logs,
             "python": command([str(env_python), "--version"]).decode().strip(),
             "freeze": freeze.splitlines()}
    dump(root / "environments" / key / "setup.json", setup)
    return env_dir


def agent_path(env_dir: Path | None, prism_cli_dir: Path | None, rg: str | None) -> str:
    """Return an isolated PATH, exposing the Prism CLI only to Prism arms."""
    parts = [str(env_dir / "bin")] if env_dir is not None else []
    if prism_cli_dir is not None:
        parts.append(str(prism_cli_dir))
    if rg:
        parts.append(str(Path(rg).parent))
    parts.extend(["/opt/homebrew/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    return os.pathsep.join(dict.fromkeys(parts))


def is_source_path(path: str, extra_suffixes: tuple[str, ...] = (".py", ".pyi")) -> bool:
    """Keep implementation files while rejecting tests and run artifacts."""
    value = Path(path)
    parts = set(value.parts)
    return (
        value.suffix in extra_suffixes
        and not parts.intersection({"test", "tests", ".grove", ".prism", ".shale"})
        and not value.name.startswith("test_")
        and not value.name.endswith("_test.py")
    )


def source_diff(work: Path, baseline: str, setup_files: list[str]) -> tuple[str, list[str], list[str]]:
    command(["git", "add", "-A"], work, check=False)
    all_changed = command(
        ["git", "diff", "--cached", "--name-only", baseline], work, check=False
    ).decode().splitlines()
    setup = set(setup_files)
    candidate_files = [path for path in all_changed if path not in setup]
    source_files = [path for path in candidate_files if is_source_path(path)]
    non_source_files = [path for path in candidate_files if path not in source_files]
    if not source_files:
        return "", [], non_source_files
    diff = command(
        ["git", "diff", "--cached", "--binary", baseline, "--", *source_files],
        work, check=False,
    ).decode(errors="replace")
    return diff, source_files, non_source_files


# --- cell execution ----------------------------------------------------------

@dataclass
class Cell:
    key: str
    out: Path
    work: Path
    cmd: list[str]
    arm: str
    invocation_id: str
    env_dir: Path | None = None
    prism_cli_dir: Path | None = None
    extra: dict = field(default_factory=dict)


def prepare_cell(root: Path, key: str, arm: str, template: Path | None, cfg: AgentConfig,
                 prism_binary: Path, prompt: str,
                 env_dir: Path | None = None, prism_cli_dir: Path | None = None,
                 extra: dict | None = None) -> Cell:
    """Assemble one cell's evidence dir, work copy, mcp.json, and command.

    `template` is copied into the cell's `work` dir; pass `None` when the
    caller has already materialized `work` itself (e.g. it needed to run
    `prism index`/`prism init` directly inside it before assembly).
    """
    out = root / "evidence" / key
    work = root / "work" / key
    out.mkdir(parents=True)
    if template is not None:
        shutil.copytree(template, work)
    has_prism = arm.endswith("prism")
    mcp = {"mcpServers": {}}
    if has_prism:
        mcp["mcpServers"]["prism"] = {"type": "stdio", "command": str(prism_binary),
                                             "args": ["mcp", str(work)]}
    dump(out / "mcp.json", mcp)
    (out / "prompt.txt").write_text(prompt)
    cmd = build_command(cfg, root, out, work, arm, prompt, prism_binary)
    dump(out / "command.json", cmd)
    return Cell(key=key, out=out, work=work, cmd=cmd, arm=arm,
               invocation_id=str(uuid.uuid4()), env_dir=env_dir,
               prism_cli_dir=(prism_cli_dir if has_prism else None),
               extra=extra or {})


def run_cell(cell: Cell, cfg: AgentConfig, finalize=None) -> dict:
    """Launch the agent, parse its event stream, and run the protocol audit.

    `finalize(cell, rec, final_text) -> dict` is called after the audit with
    the parsed record and the agent's final text, and should return the
    task-shape-specific fields to merge in (a source diff for coding tasks,
    a parsed structured answer for impact tasks). Keeping that one hook
    outside this function is what lets one `run_cell` serve both task
    shapes without a task-type branch buried in the invocation/audit logic.
    """
    out, work, arm = cell.out, cell.work, cell.arm
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    rg = shutil.which("rg")
    env["PATH"] = agent_path(cell.env_dir, cell.prism_cli_dir, rg)
    if cell.env_dir is not None:
        env["VIRTUAL_ENV"] = str(cell.env_dir)
        env["PYTHONPATH"] = os.pathsep.join([str(work / "src"), str(work)])
    t0, started, timed_out = time.monotonic(), time.time(), False
    print("START " + cell.key, flush=True)
    with (out / "stdout.jsonl").open("w") as stdout, (out / "stderr.txt").open("w") as stderr:
        proc = subprocess.Popen(cell.cmd, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            proc.wait(timeout=cfg.timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop(proc)
    events = read_events(out / "stdout.jsonl")
    if arm.startswith("sonnet"):
        rec, final, calls = summarize_sonnet(events, out)
    else:
        rec, final, calls = summarize_codex(events, out, cfg.gpt_model)
    (out / "final.txt").write_text(final)
    audit_calls(rec, calls, arm)
    extra_fields = finalize(cell, rec, final) if finalize else {}
    rec.update(
        cell_id=cell.key, arm=arm, invocation_id=cell.invocation_id,
        started_at=started, wall_s=round(time.monotonic() - t0, 3),
        exit_code=proc.returncode, timed_out=timed_out,
    )
    rec.update(extra_fields)
    rec["audited_valid"] = bool(
        proc.returncode == 0 and not timed_out and rec.get("measurement_complete")
        and not rec.get("agent_error") and not rec["violations"]
    )
    dump(out / "measurement.json", rec)
    return rec
