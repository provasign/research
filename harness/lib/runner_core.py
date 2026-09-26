"""The one implementation of "invoke claude/codex with optional Prism and
parse the result".

This is the generalized descendant of
`harness/results/archive-2026-09-tainted/daytoday-four-head-2026-09-07/run_readonly.py` (frozen,
never edited -- historical `run_code.py`/`run_panel.py` snapshots under
`harness/results/archive-2026-09-tainted/*` import it directly and must keep working) merged with
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

import ast
import hashlib
import io
import json
import os
import re
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
from typing import Callable

PRISM_TOOLS = [
    "prism_search", "prism_query", "prism_read", "prism_lookup",
    "prism_change_impact", "prism_verify",
]

# Env vars checked, in order, when no --prism-binary is given on the CLI.
# PRISM_BINARY is the current name; PRISM_V072_BINARY is kept only because
# older run scripts/docs still reference it.
PRISM_BINARY_ENV_VARS = ("PRISM_BINARY", "PRISM_V072_BINARY")

# Human-readable labels for cross-tool-violation messages.
TOOL_LABEL = {"prism": "Prism", "codegraph": "CodeGraph"}


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


def resolve_codegraph_binary(explicit: str | None = None) -> Path:
    """Resolve the CodeGraph binary to use for a run. Mirrors
    `resolve_prism_binary`: explicit CLI flag, then `$CODEGRAPH_BINARY`, then
    `PATH` (`which codegraph`). CodeGraph has no `~/bin/codegraph`
    convention to fall back to."""
    candidates: list[tuple[str, Path]] = []
    if explicit:
        candidates.append(("--codegraph-binary", Path(explicit).expanduser()))
    value = os.environ.get("CODEGRAPH_BINARY")
    if value:
        candidates.append(("$CODEGRAPH_BINARY", Path(value).expanduser()))
    found = shutil.which("codegraph")
    if found:
        candidates.append(("PATH", Path(found)))
    for source, path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    tried = "; ".join(f"{source}: {path}" for source, path in candidates)
    raise RuntimeError(
        "no usable CodeGraph binary found. Pass --codegraph-binary explicitly, set "
        f"CODEGRAPH_BINARY, or install codegraph on PATH. Tried: {tried}"
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


_SHELL_WRAPPERS = ("sh", "bash", "zsh")
_SHELL_C_FLAGS = ("-c", "-lc", "-cl")
_SHELL_OPERATORS = {";", "&&", "||", "|", "&"}


def _shell_segments(value: str) -> list[list[str]]:
    """Split a shell command line into argv-token segments (one list of
    tokens per `;`/`&&`/`||`/`|`/`&`-separated command), unwrapping one
    outer `<sh|bash|zsh> -c/-lc '<inner>'` layer first.

    Codex's `command_execution` events carry the full wrapper
    (`/bin/zsh -lc 'prism query ...'`); Claude Code's Bash tool gives the
    inner command directly. Without unwrapping, a naive single shlex.split
    of the wrapped form yields exactly 3 tokens -- the shell, the flag, and
    the ENTIRE inner command as one opaque token (single quotes suppress
    all splitting) -- so nothing inside it is ever seen as a real command.
    Caught 2026-09-13: every Codex+Prism cell that used the CLI instead of
    the MCP tool was invisible to `_invokes_cli`/`successful_own_tool_actions`
    this way, scoring as "own tool had no successful calls" regardless of
    what it actually ran (72 of 83 historical Codex+Prism cells show this;
    31 of those plainly mention `prism` in their own command list)."""
    try:
        tokens = shlex.split(value)
    except ValueError:
        tokens = value.split()
    if (len(tokens) >= 3 and Path(tokens[0]).name in _SHELL_WRAPPERS
            and tokens[1] in _SHELL_C_FLAGS):
        try:
            inner = shlex.split(tokens[2])
        except ValueError:
            inner = tokens[2].split()
        tokens = inner + tokens[3:]
    segments: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in _SHELL_OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def _invokes_cli(value: str, binary_name: str) -> bool:
    return any(seg and Path(seg[0]).name == binary_name for seg in _shell_segments(value))


def _invokes_command(value: str, name: str, subcommands: set[str] | None = None) -> bool:
    """True if `name` is actually run as a command (first token of some
    segment), optionally requiring its subcommand (second token) be one of
    `subcommands`. Unlike a plain substring/regex match over the raw text,
    this does not fire on `name` appearing inside a quoted argument to a
    DIFFERENT program -- caught on `cli/cli` (GitHub's own CLI) tasks,
    where a Prism query string like `"gh issue create --web ..."` matched
    the old regex `gh\\s+(?:pr|api|repo|issue)\\b` as a false "network
    access via shell" violation: the codebase being edited is gh itself,
    so its own subcommand names appear constantly as ordinary text, never
    as an actual invocation."""
    for seg in _shell_segments(value):
        if seg and Path(seg[0]).name == name:
            if subcommands is None or (len(seg) > 1 and seg[1] in subcommands):
                return True
    return False


def invokes_prism(value: str) -> bool:
    return _invokes_cli(value, "prism")


# Network use via the shell. The task prompt forbids it, and for the e2e
# suite it is not a mere efficiency leak: every task is a real merged PR whose
# fix is already published, so `pip download <pkg>` can fetch the answer (a
# prism cell did exactly that on 2026-09-12). Matched anywhere in the command,
# not as a prefix, so `cd /tmp && pip download ...` is caught -- the form it
# actually took.
#
# Two tiers, deliberately: DEFINITE is the narrow set of commands that fetch
# from outside the repo and is a protocol violation. SUSPECT is a bare URL
# literal, which proves nothing by itself (`ProxyManager('https://localhost:1')`
# in a test fixture matched a coarser regex in the 2026-09-13 scan) and is
# recorded for review but never asserted as network use. `pip show`,
# `pip --version`, `python -c` stay local and unflagged -- a broader list
# denied those and broke cells in the swebench_ab probes (see its history).
_NETWORK_DEFINITE = re.compile(
    r"(?<![\w/.-])(?:pip3?\s+(?:download|install)\b|uv\s+(?:pip\s+install|add|sync)\b"
    r"|npm\s+(?:install|i|ci)\b|curl\s|wget\s"
    r"|git\s+(?:clone|fetch|pull|ls-remote)\b)"
)
# `gh <pr|api|repo|issue>` is checked separately, at command position (see
# _invokes_command), not by this regex: the polyglot suite added cli/cli
# (GitHub's own CLI) as a benchmark repo, where "gh issue"/"gh pr" appear
# constantly as ordinary text -- in Prism query strings, code, commit
# messages -- with nothing executed. A text-anywhere regex false-positived
# on exactly that shape.
_GH_NETWORK_SUBCOMMANDS = {"pr", "api", "repo", "issue"}
# `pip install` of a LOCAL path (`-e .`, `.`, `./pkg`, `/abs`) is a build step,
# not a fetch: it only reaches the index if a dependency is missing, and the
# task prompt states dependencies are preinstalled. Recorded as suspect, not
# asserted as network use -- a pr3228 cell did `python -m pip install -e . -q`
# after writing a repro script, and calling that "network access" would be
# the same over-claim the two-tier design exists to avoid.
_PIP_LOCAL_INSTALL = re.compile(
    r"(?:uv\s+)?pip3?\s+install\s+(?:-{1,2}[\w-]+(?:[=\s]\S+)?\s+)*"
    r"(?:-e\s+|--editable\s+)?(?:\.(?=[\s/]|$)|/)"
)
_NETWORK_SUSPECT = re.compile(r"https?://")
# A heredoc body fed to `cat`/`tee` is text being WRITTEN to a file, not a
# command being RUN -- `cat > repro.py <<'EOF' ... pip install foo ... EOF`
# must not match. But a heredoc fed to an interpreter (`python - <<'PY'`,
# `bash <<EOF`, or `cat <<EOF | python`) IS executed. Python bodies need an
# AST check: a dictionary containing `{"command": "curl ..."}` is not a
# fetch. The opener and commands after the terminator remain in shell scope.
_HEREDOC = re.compile(
    r"((?:^|(?<=\n))[^\n]*<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n).*?\n[ \t]*\2[ \t]*(?:\n|$)", re.S
)


def _heredoc_sub(m: re.Match) -> str:
    opener = m.group(1)
    before, after = opener.split("<<", 1)
    writes_file = re.search(r"\b(?:cat|tee)\b", before) is not None and "|" not in after
    runs_python = re.search(r"\bpython(?:\d+(?:\.\d+)?)?\b", opener) is not None
    return opener if writes_file or runs_python else m.group(0)


def _without_heredoc_bodies(value: str) -> str:
    return _HEREDOC.sub(_heredoc_sub, value)


_PYTHON_C = re.compile(r"\bpython(?:\d+(?:\.\d+)?)?\s+-c\s+(['\"])(.*?)\1", re.S)


def _python_embedded_code(value: str) -> tuple[str, list[str]]:
    """Separate Python code from shell commands without declaring literals run."""
    bodies = []
    for match in _HEREDOC.finditer(value):
        if re.search(r"\bpython(?:\d+(?:\.\d+)?)?\b", match.group(1)):
            bodies.append("\n".join(match.group(0)[len(match.group(1)):].splitlines()[:-1]))
    shell = _without_heredoc_bodies(value)

    def take(match: re.Match) -> str:
        bodies.append(match.group(2))
        return "python -c"

    return _PYTHON_C.sub(take, shell), bodies


def _python_executes_fetch(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    executors = {"subprocess.run", "subprocess.call", "subprocess.check_call",
                 "subprocess.check_output", "os.system", "os.popen"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = ""
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            name = node.func.value.id + "." + node.func.attr
        if name not in executors:
            continue
        try:
            command = ast.literal_eval(node.args[0])
        except (ValueError, TypeError):
            continue
        if isinstance(command, (list, tuple)):
            command = " ".join(str(part) for part in command)
        if isinstance(command, str) and _NETWORK_DEFINITE.search(command) and not _PIP_LOCAL_INSTALL.search(command):
            return True
    return False


def classify_network(value: str) -> str | None:
    """'definite' for a command that fetches from the network; 'suspect' for a
    local-path `pip install` or a bare URL literal (recorded for review, never
    asserted); else None."""
    cmd, python_bodies = _python_embedded_code(value)
    if _invokes_command(cmd, "gh", _GH_NETWORK_SUBCOMMANDS):
        return "definite"
    hit = False
    for m in _NETWORK_DEFINITE.finditer(cmd):
        hit = True
        tail = cmd[m.start():]
        if re.match(r"(?:uv\s+)?pip3?\s+install\b", tail) and _PIP_LOCAL_INSTALL.match(tail):
            continue
        return "definite"
    if any(_python_executes_fetch(code) for code in python_bodies):
        return "definite"
    if hit or _NETWORK_SUSPECT.search(cmd) or any(
            _NETWORK_DEFINITE.search(code) or _NETWORK_SUSPECT.search(code)
            for code in python_bodies):
        return "suspect"
    return None


def active_tool(arm: str) -> str:
    """Which tool (if any) this arm's name says it uses: the `{prefix}_tool`
    suffix convention, generalized beyond prism/native."""
    if arm.endswith("prism"):
        return "prism"
    if arm.endswith("codegraph"):
        return "codegraph"
    return "native"


def _codex_mcp_lines(server: str, binary: Path, args: list[str]) -> list[str]:
    """Shared shape for a codex `-c mcp_servers.<server>.*` block."""
    return [
        f"mcp_servers.{server}.command=" + json.dumps(str(binary)),
        f"mcp_servers.{server}.args=" + json.dumps(args),
        f"mcp_servers.{server}.required=true",
    ]


@dataclass(frozen=True)
class ToolSpec:
    """One entry in the tool registry `TOOLS`. Every currently-Prism-specific
    branch in this module becomes a lookup into `TOOLS[active_tool(arm)]`,
    with the per-tool logic living only here."""

    name: str
    mcp_server_name: str
    init_args: Callable[[Path, Path], list[str]]
    mcp_stdio: Callable[[Path, Path], dict]
    codex_mcp_config: Callable[[Path, Path], list[str]]
    invokes_cli: Callable[[str], bool]
    sonnet_call_prefix: str
    # Extra codex `-c` lines that need cfg (e.g. Prism's per-tool approval
    # mode list) -- None when a tool needs nothing beyond codex_mcp_config.
    codex_extra_config: Callable[["AgentConfig"], list[str]] | None = None


TOOLS: dict[str, ToolSpec] = {
    "prism": ToolSpec(
        name="prism",
        mcp_server_name="prism",
        init_args=lambda binary, target: prism_init_args(binary, target),
        mcp_stdio=lambda binary, work: {
            "type": "stdio", "command": str(binary), "args": ["mcp", str(work)],
        },
        codex_mcp_config=lambda binary, work: _codex_mcp_lines(
            "prism", binary, ["mcp", str(work)]),
        invokes_cli=lambda value: _invokes_cli(value, "prism"),
        sonnet_call_prefix="mcp__prism__",
        codex_extra_config=lambda cfg: [
            f'mcp_servers.prism.tools.{name}.approval_mode="approve"'
            for name in dict.fromkeys(["prism", *cfg.prism_tools])
        ],
    ),
    "codegraph": ToolSpec(
        name="codegraph",
        mcp_server_name="codegraph",
        init_args=lambda binary, target: [str(binary), "init", str(target)],
        mcp_stdio=lambda binary, work: {
            "type": "stdio", "command": str(binary),
            "args": ["serve", "-p", str(work), "--mcp"],
        },
        codex_mcp_config=lambda binary, work: _codex_mcp_lines(
            "codegraph", binary, ["serve", "-p", str(work), "--mcp"]),
        invokes_cli=lambda value: _invokes_cli(value, "codegraph"),
        sonnet_call_prefix="mcp__codegraph__",
        codex_extra_config=None,
    ),
}


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
    call_outcomes: dict = {}
    permission_denials: list[str] = []
    thinking_blocks = thinking_chars = 0
    for event in events:
        # Not every event carries a dict `message`: a deny-list refusal is
        # `{"type":"system","subtype":"permission_denied","message":"<str>"}`.
        # That string once crashed a whole 6-cell run before scoring
        # (2026-09-13), losing the very evidence it should have recorded.
        if event.get("type") == "system" and event.get("subtype") == "permission_denied":
            permission_denials.append(str(event.get("message") or ""))
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                identity = block.get("id")
                call_names[identity] = block.get("name", "")
                if identity not in seen:
                    seen.add(identity)
                    calls.append(block)
            elif block.get("type") == "tool_result":
                identity = block.get("tool_use_id")
                tool_result_bytes[identity] = result_bytes(block.get("content"))
                call_outcomes[identity] = not block.get("is_error")
                if block.get("is_error"):
                    tool_errors.append({"tool": call_names.get(identity, ""),
                                        "content": block.get("content")})
            elif block.get("type") == "thinking" and event.get("type") == "assistant":
                thinking_blocks += 1
                thinking_chars += len(block.get("thinking") or "")
    rec["tool_errors"] = tool_errors
    # Per-call success, keyed by tool_use id, so the audit can tell an
    # executed network fetch (violation) from one the deny list refused
    # (recorded attempt). Denial messages are kept verbatim: they show what
    # the model tried, which is evidence in its own right.
    rec["call_outcomes"] = call_outcomes
    rec["permission_denials"] = permission_denials
    # Reasoning-capture check (see AgentConfig.thinking_display): blocks
    # present but zero chars means the API returned signature-only thinking
    # -- the flag was dropped or unsupported, and "why did the agent do X"
    # is not answerable from this transcript.
    rec["thinking_blocks"] = thinking_blocks
    rec["thinking_chars"] = thinking_chars
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


def _violation_message(own_tool: str, other_tool: str) -> str:
    label = TOOL_LABEL.get(other_tool, other_tool)
    if own_tool == "native":
        return f"native arm used {label}"
    return f"{own_tool} arm used {label} (not its own tool)"


def audit_calls(rec: dict, calls: list[dict], arm: str) -> None:
    """Protocol-violation audit: mutual exclusion across every tool in
    `TOOLS`, plus delegated/networked tools and duplicate own-tool call
    signatures.

    A violation is any call to a tool OTHER than `active_tool(arm)` -- for a
    native arm that means any tool call at all; for a prism arm, a codegraph
    call is also a violation, and vice versa.

    `prism_calls`/`prism_cli_commands`/`prism_actions`/`duplicate_prism_calls`
    are kept, for measurement.json backward compatibility, as the count of
    calls to THIS ARM'S OWN tool -- so on a `sonnet_codegraph` arm,
    `prism_calls` is actually its CodeGraph call names (a misleading legacy
    name we're stuck with). `own_tool_calls`/`own_tool_cli_commands`/
    `cross_tool_violations` are the tool-agnostic equivalents; prefer those
    in new code.
    """
    own_tool = active_tool(arm)
    own_calls: list[str] = []
    other_tool_hits: dict[str, int] = {}
    native_commands: list[str] = []
    native_ok: list[bool] = []  # parallel to native_commands: did the shell call succeed?
    outcomes = rec.get("call_outcomes") or {}
    signatures: list[str] = []
    violations: list[str] = []
    if arm.startswith("sonnet"):
        for call in calls:
            name = call.get("name", "")
            value = call.get("input") or {}
            matched = next((tname for tname, spec in TOOLS.items()
                            if name.startswith(spec.sonnet_call_prefix)), None)
            if matched is not None:
                if matched == own_tool:
                    own_calls.append(name)
                    signatures.append(name + ":" + json.dumps(value, sort_keys=True))
                else:
                    other_tool_hits[matched] = other_tool_hits.get(matched, 0) + 1
            elif name == "Bash":
                native_commands.append(value.get("command", ""))
                native_ok.append(bool(outcomes.get(call.get("id"), True)))
            elif name in ("Agent", "Task", "WebFetch", "WebSearch"):
                violations.append("delegation or network tool used")
    else:
        for call in calls:
            kind = call.get("type")
            if kind == "mcp_tool_call":
                server = call.get("server")
                if server in TOOLS:
                    tool_name = call.get("tool", "")
                    if server == own_tool:
                        own_calls.append(tool_name)
                        signatures.append(tool_name + ":" +
                                          json.dumps(call.get("arguments") or {}, sort_keys=True))
                    else:
                        other_tool_hits[server] = other_tool_hits.get(server, 0) + 1
            elif kind == "command_execution":
                native_commands.append(call.get("command", ""))
                native_ok.append(call.get("status") == "completed" and call.get("exit_code") == 0)
            elif kind in ("collab_tool_call", "web_search"):
                violations.append("delegation or network tool used")
            elif kind == "file_change" and not rec.get("allow_source_edits"):
                violations.append("edit used in read-only cell")
    # A definite fetch that EXECUTED is a violation. One the deny list or the
    # Codex sandbox refused is recorded as an attempt: nothing reached the
    # network, so the cell is not contaminated, and the turns it cost are a
    # fair charge for the model's own behavior (the same in every arm).
    definite = [(v, ok) for v, ok in zip(native_commands, native_ok)
                if classify_network(v) == "definite"]
    network_commands = [v for v, ok in definite if ok]
    network_attempts_blocked = [v for v, ok in definite if not ok]
    network_suspects = [v for v in native_commands if classify_network(v) == "suspect"]
    if network_commands:
        violations.append("network access via shell")
    own_spec = TOOLS.get(own_tool)
    own_cli_commands = [value for value in native_commands
                        if own_spec is not None and own_spec.invokes_cli(value)]
    cross_tool_violations: list[str] = []
    for tname, count in sorted(other_tool_hits.items()):
        message = _violation_message(own_tool, tname)
        violations.append(message)
        cross_tool_violations.append(f"{message} ({count} MCP call(s))")
    for tname, spec in sorted(TOOLS.items()):
        if tname == own_tool:
            continue
        cli_hits = [value for value in native_commands if spec.invokes_cli(value)]
        if cli_hits:
            message = _violation_message(own_tool, tname)
            violations.append(message)
            cross_tool_violations.append(f"{message} ({len(cli_hits)} CLI command(s))")
    rec.update(
        calls=calls,
        tool_calls=len(calls),
        prism_calls=own_calls,
        prism_cli_commands=own_cli_commands,
        prism_actions=len(own_calls) + len(own_cli_commands),
        duplicate_prism_calls=len(signatures) - len(set(signatures)),
        native_commands=native_commands,
        violations=violations,
        own_tool=own_tool,
        own_tool_calls=own_calls,
        own_tool_cli_commands=own_cli_commands,
        cross_tool_violations=cross_tool_violations,
        network_commands=network_commands,
        network_attempts_blocked=network_attempts_blocked,
        network_suspects=network_suspects,
    )


def successful_own_tool_actions(events: list[dict], calls: list[dict], arm: str) -> int:
    """Count completed own-tool calls, excluding denied MCP attempts."""
    own_tool = active_tool(arm)
    spec = TOOLS.get(own_tool)
    if spec is None:
        return 0
    if arm.startswith("sonnet"):
        results = {}
        for event in events:
            message = event.get("message")
            if not isinstance(message, dict):
                continue
            for block in message.get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = not block.get("is_error")
        return sum(
            bool(results.get(call.get("id"))) and (
                str(call.get("name", "")).startswith(spec.sonnet_call_prefix) or
                (call.get("name") == "Bash" and
                 spec.invokes_cli((call.get("input") or {}).get("command", "")))
            )
            for call in calls
        )
    return sum(
        (call.get("type") == "mcp_tool_call" and
         call.get("server") == own_tool and call.get("status") == "completed" and
         not call.get("error")) or
        (call.get("type") == "command_execution" and
         spec.invokes_cli(call.get("command", "")) and
         call.get("status") == "completed" and call.get("exit_code") == 0)
        for call in calls
    )


# --- agent invocation config -------------------------------------------------

@dataclass
class AgentConfig:
    """Everything that used to be a hardcoded module constant in
    run_readonly.py / coding_suite.py / product_impact_suite.py."""

    sonnet_model: str = "claude-sonnet-5"
    gpt_model: str = "gpt-5.5"
    effort: str = "medium"
    # `--thinking-display summarized` asks the API for thinking summaries so the
    # model's reasoning lands in stdout.jsonl. Without it, `claude -p
    # --output-format stream-json` returns signature-only thinking blocks
    # (`thinking: ""`): the tokens are billed but the text is absent, because
    # the CLI only consults `showThinkingSummaries` in interactive mode. The
    # flag is hidden from `claude --help` (v2.1.270) and rides a beta header the
    # CLI silently drops if the server rejects it -- so check `thinking_chars`
    # in measurement.json rather than assume capture worked. None omits the
    # flag. This is display-only: it does not change whether or how much the
    # model thinks, so it does not affect agent behavior or comparability.
    thinking_display: str | None = "summarized"
    timeout_s: int = 300
    max_budget_usd: str = "1.50"
    # "skip" -> --dangerously-skip-permissions (coding/product suites, which
    # must edit files); "restricted" -> --restricted --permission-mode dontAsk
    # --permission-prompts none (readonly/impact suites, which must not edit).
    permission_mode: str = "skip"
    tools: str = "Read,Grep,Glob,Bash,Edit,Write"
    # mcp__prism/mcp__codegraph are harmless to allow on arms that don't
    # register that MCP server (mcp.json has no entry for it there, so the
    # allowance is inert) -- this lets one allowedTools string serve every
    # arm regardless of which tool (if any) it uses.
    allowed_tools: str = "Read,Grep,Glob,Bash,Edit,Write,mcp__prism,mcp__codegraph"
    # Network block for Claude arms, via --disallowedTools. Probed 2026-09-13
    # with the harness's own flags: deny rules hold under
    # --dangerously-skip-permissions and Claude Code evaluates each segment
    # of a compound command, so `cd /tmp && curl ...` is refused too. Narrow
    # on purpose -- `pip show`, `pip --version`, `python -c` stay allowed
    # (a broad `Bash(pip:*)` broke legitimate cells in the swebench_ab
    # probes). Blocking is belt; the audit's `network_commands` record is
    # braces for anything a pattern misses. Codex arms are covered by the
    # workspace-write sandbox instead (curl exit 6 in the same probe).
    disallowed_tools: str = (
        "Bash(pip download:*),Bash(pip install:*),Bash(pip3 download:*),Bash(pip3 install:*),"
        "Bash(curl:*),Bash(wget:*),Bash(gh:*),Bash(git clone:*),Bash(git fetch:*),Bash(git pull:*),"
        "WebFetch,WebSearch"
    )
    project_doc_max_bytes: int = 32768
    output_schema: bool = False  # codex --output-schema <root>/answer-schema.json
    prism_tools: list[str] = field(default_factory=lambda: list(PRISM_TOOLS))
    concurrency: int = 4


def build_command(cfg: AgentConfig, root: Path, out: Path, work: Path, arm: str,
                  prompt: str, tool_binary: Path) -> list[str]:
    """`tool_binary` is the binary for this arm's own tool (per
    `active_tool(arm)`) -- unused for a native arm."""
    tool = active_tool(arm)
    if arm.startswith("sonnet"):
        settings = {"autoMemoryEnabled": False, "disableAllHooks": True, "enabledPlugins": {}}
        cmd = [
            shutil.which("claude"), "-p", prompt, "--model", cfg.sonnet_model,
            "--effort", cfg.effort, "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", cfg.max_budget_usd,
        ]
        if cfg.thinking_display:
            cmd += ["--thinking-display", cfg.thinking_display]
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
        if cfg.disallowed_tools:
            cmd += ["--disallowedTools", cfg.disallowed_tools]
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
        # Pin the workspace-write sandbox's network policy rather than rely on
        # its default. Probed 2026-09-13 under these flags: the default already
        # blocks (curl exit 6, host unresolvable), so correctness does not
        # rest on this line -- it makes the policy explicit in command.json.
        "sandbox_workspace_write.network_access=false",
    ]
    spec = TOOLS.get(tool)
    if spec is not None:
        fcfg += spec.codex_mcp_config(tool_binary, work)
        if spec.codex_extra_config:
            fcfg += spec.codex_extra_config(cfg)
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
        if any(part in (".git", ".grove", ".prism", ".codegraph") for part in rel.parts):
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
    task.

    Two Prism steps are required, in this order (matching
    `product_impact_suite.py`): `prism index` builds the Grove graph the MCP
    server actually serves, then `prism init` (`prism_init_args`) layers the
    product integration (steering files, harness config) on top. Running
    `init` alone leaves the graph empty (`filesIndexed`/`symbolCount`/
    `edgeCount` == 0) -- confirmed directly against a fresh pallets/click
    checkout -- so `index` must run first or the Prism arm is silently
    starting every agent session against an empty index.
    """
    prism = root / "templates" / key / "prism"
    shutil.copytree(base, prism)
    t0 = time.monotonic()
    indexed = subprocess.run([str(binary), "index", str(prism)], cwd=prism,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    initialized = subprocess.run(prism_init_args(binary, prism), cwd=prism,
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    status = subprocess.run([str(binary), "status", str(prism)], cwd=prism,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    try:
        status_json = json.loads(status.stdout) if status.returncode == 0 else None
    except json.JSONDecodeError:
        status_json = None
    dump(root / "templates" / key / "index.json",
         {"wall_s": time.monotonic() - t0,
          "index_exit_code": indexed.returncode, "index_stdout": indexed.stdout, "index_stderr": indexed.stderr,
          "init_exit_code": initialized.returncode, "init_stdout": initialized.stdout, "init_stderr": initialized.stderr,
          "status": status_json})
    if indexed.returncode or initialized.returncode:
        raise RuntimeError(f"{key}: prism index/init failed")
    if not status_json or not status_json.get("symbolCount"):
        raise RuntimeError(f"{key}: prism template has an empty graph after index+init: {status_json}")
    base_content = template_content(base)
    prism_content = template_content(prism)
    mismatched = sorted(path for path, digest in base_content.items()
                        if prism_content.get(path) != digest)
    if mismatched:
        raise RuntimeError(f"{key}: native/Prism template mismatch: {mismatched[:10]}")
    return prism, template_setup_files(prism)


def make_codegraph_template(root: Path, binary: Path, key: str, base: Path) -> tuple[Path, list[str]]:
    """CodeGraph counterpart to `make_prism_template`. `codegraph init`
    builds `.codegraph/codegraph.db` in one non-interactive step (no
    separate index command, unlike Prism), so there is no ordering concern
    here -- just the same copy + init + byte-identical-except-`.codegraph`
    check."""
    codegraph = root / "templates" / key / "codegraph"
    shutil.copytree(base, codegraph)
    t0 = time.monotonic()
    initialized = subprocess.run(TOOLS["codegraph"].init_args(binary, codegraph), cwd=codegraph,
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    dump(root / "templates" / key / "index.codegraph.json",
         {"wall_s": time.monotonic() - t0, "exit_code": initialized.returncode,
          "stdout": initialized.stdout, "stderr": initialized.stderr})
    if initialized.returncode:
        raise RuntimeError(f"{key}: codegraph init failed")
    base_content = template_content(base)
    codegraph_content = template_content(codegraph)
    mismatched = sorted(path for path, digest in base_content.items()
                        if codegraph_content.get(path) != digest)
    if mismatched:
        raise RuntimeError(f"{key}: native/CodeGraph template mismatch: {mismatched[:10]}")
    return codegraph, template_setup_files(codegraph)


def prefetch_dependencies(root: Path, key: str, base: Path, language: str) -> None:
    """Non-Python languages: fetch dependencies once, before any timed cell,
    so no agent cell needs network to build or test. Go/Rust caches are
    global on the host (GOPATH/pkg/mod, CARGO_HOME/registry) -- fetching
    once here warms them for every later cell on this host, no per-cell
    copy needed. npm has no such global cache; `npm ci` runs directly in
    `base` so node_modules is materialized in the template and carried into
    each cell by prepare_cell's plain `shutil.copytree(template, work)`."""
    cmds = {"go": ["go", "mod", "download"], "rust": ["cargo", "fetch"],
            "ts": ["npm", "ci", "--no-audit", "--no-fund"], "js": ["npm", "ci", "--no-audit", "--no-fund"]}
    cmd = cmds.get(language)
    if cmd is None:
        return
    t0 = time.monotonic()
    prefetch_env = os.environ.copy()
    prefetch_env["GOWORK"] = "off"  # see run_cell's GOWORK note
    # This harness process's own PATH may predate a toolchain install (e.g.
    # rustup's ~/.cargo/bin) -- same gap agent_path() documents for cells.
    prefetch_env["PATH"] = os.pathsep.join(
        [str(Path.home() / ".cargo" / "bin"), "/usr/local/go/bin", prefetch_env.get("PATH", "")])
    result = subprocess.run(cmd, cwd=base, capture_output=True, text=True, timeout=1800, env=prefetch_env)
    dump(root / "environments" / key / "setup.json", {
        "language": language, "wall_s": round(time.monotonic() - t0, 3),
        "cmd": cmd, "exit_code": result.returncode,
        "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:],
    })
    if result.returncode != 0:
        raise RuntimeError(f"{key}: {' '.join(cmd)} failed: {result.stderr[-500:]}")


def prepare_environment(root: Path, key: str, base: Path, language: str = "python") -> Path | None:
    """Install dependencies before the timed cells and archive exact versions.
    Python only -- other languages use `prefetch_dependencies` and need no
    venv (their toolchain is on PATH directly, see `agent_path`)."""
    if language != "python":
        prefetch_dependencies(root, key, base, language)
        return None
    env_dir = root / "environments" / key
    python = shutil.which("python3.12") or shutil.which("python3")
    if not python:
        raise RuntimeError("Python is unavailable")
    t0 = time.monotonic()
    logs = []
    subprocess.run([python, "-m", "venv", str(env_dir)], check=True)
    env_python = env_dir / "bin/python"
    uv = shutil.which("uv")
    packaged = any((base / name).exists() for name in ("pyproject.toml", "setup.py", "setup.cfg"))
    installed = not packaged
    if not packaged:
        logs.append({"target": "source-only repository (no package metadata)", "exit_code": 0})
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


def agent_path(env_dir: Path | None, tool_cli_dir: Path | None, rg: str | None) -> str:
    """Return an isolated PATH, exposing an arm's own tool CLI only to that
    arm (a native, or wrong-tool, arm cannot exec it via Bash).

    Cells run as host subprocesses, not containers, so a language's own
    toolchain must already be on this list or the agent cannot invoke it at
    all -- caught adding Go/Rust/TS tasks 2026-09-13: /usr/local/go/bin (go)
    and ~/.cargo/bin (cargo/rustc) were both missing, which would have made
    every non-Python cell unable to self-test regardless of env_dir/venv."""
    parts = [str(env_dir / "bin")] if env_dir is not None else []
    if tool_cli_dir is not None:
        parts.append(str(tool_cli_dir))
    if rg:
        parts.append(str(Path(rg).parent))
    parts.extend(["/opt/homebrew/bin", "/usr/local/bin", "/usr/local/go/bin",
                  str(Path.home() / ".cargo" / "bin"), "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    return os.pathsep.join(dict.fromkeys(parts))


SOURCE_SUFFIXES_BY_LANGUAGE = {
    "python": (".py", ".pyi"),
    "go": (".go",),
    "rust": (".rs",),
    "ts": (".ts", ".tsx"),
    "js": (".js", ".jsx", ".mjs", ".cjs"),
}


def is_source_path(path: str, extra_suffixes: tuple[str, ...] = (".py", ".pyi")) -> bool:
    """Keep implementation files while rejecting tests and run artifacts.

    `extra_suffixes` defaults to Python only -- a non-Python task MUST pass
    its own language's suffixes (see SOURCE_SUFFIXES_BY_LANGUAGE) or every
    edit is silently classified as non-source and the captured diff comes
    back empty regardless of what the agent actually did. Caught 2026-09-13
    after a full 66-cell polyglot run scored 0/66 resolved on BOTH arms:
    every cell's `agent.diff` was empty ("empty_diff": true) despite real,
    uncommitted .go/.rs/.ts edits sitting in the work tree the whole time --
    `finalize_coding` never threaded the task's language through. The bug
    silently invalidated every "not resolved" verdict for every non-Python
    cell run this session, not just this one call site.
    """
    value = Path(path)
    parts = set(value.parts)
    is_test_name = value.name.startswith("test_") or value.name.endswith("_test.py")
    if value.suffix in (".go",):
        is_test_name = is_test_name or value.name.endswith("_test.go")
    elif value.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        stem = value.name
        is_test_name = is_test_name or any(
            stem.endswith(suffix) for suffix in (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                                                 ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx",
                                                 ".tests.ts", ".tests.js"))
    return (
        value.suffix in extra_suffixes
        and not parts.intersection({"test", "tests", ".grove", ".prism", ".shale", ".codegraph"})
        and not is_test_name
    )


def source_diff(work: Path, baseline: str, setup_files: list[str],
                extra_suffixes: tuple[str, ...] = (".py", ".pyi")) -> tuple[str, list[str], list[str]]:
    command(["git", "add", "-A"], work, check=False)
    all_changed = command(
        ["git", "diff", "--cached", "--name-only", baseline], work, check=False
    ).decode().splitlines()
    setup = set(setup_files)
    candidate_files = [path for path in all_changed if path not in setup]
    source_files = [path for path in candidate_files if is_source_path(path, extra_suffixes)]
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
    tool_cli_dir: Path | None = None
    extra: dict = field(default_factory=dict)


def prepare_cell(root: Path, key: str, arm: str, template: Path | None, cfg: AgentConfig,
                 tool_binary: Path, prompt: str,
                 env_dir: Path | None = None, tool_cli_dir: Path | None = None,
                 extra: dict | None = None) -> Cell:
    """Assemble one cell's evidence dir, work copy, mcp.json, and command.

    `template` is copied into the cell's `work` dir; pass `None` when the
    caller has already materialized `work` itself (e.g. it needed to run
    `prism index`/`prism init` directly inside it before assembly).
    `tool_binary` is this arm's own tool's binary (per `active_tool(arm)`);
    unused for a native arm.
    """
    out = root / "evidence" / key
    work = root / "work" / key
    out.mkdir(parents=True)
    if template is not None:
        shutil.copytree(template, work)
    spec = TOOLS.get(active_tool(arm))
    mcp = {"mcpServers": {}}
    if spec is not None:
        mcp["mcpServers"][spec.mcp_server_name] = spec.mcp_stdio(tool_binary, work)
    dump(out / "mcp.json", mcp)
    (out / "prompt.txt").write_text(prompt)
    cmd = build_command(cfg, root, out, work, arm, prompt, tool_binary)
    dump(out / "command.json", cmd)
    return Cell(key=key, out=out, work=work, cmd=cmd, arm=arm,
               invocation_id=str(uuid.uuid4()), env_dir=env_dir,
               tool_cli_dir=(tool_cli_dir if spec is not None else None),
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
    # Close git's network path without denying git: fetch/clone/pull to any
    # non-file remote fail, local operations are untouched. Independent of
    # tool-permission rules, so it holds even where a deny pattern misses a
    # compound command. Same mechanism swebench_ab.py settled on.
    env["GIT_ALLOW_PROTOCOL"] = "file"
    # An unrelated host go.work (this machine has one at /private/tmp) is
    # auto-discovered upward from any cwd under /tmp and silently pulls a Go
    # cell's `go build`/`go test` into the WRONG module set. Caught 2026-09-13:
    # a cli/cli cell burned several turns discovering and disabling this
    # itself. Harmless to set for every cell, not only Go ones.
    env["GOWORK"] = "off"
    rg = shutil.which("rg")
    env["PATH"] = agent_path(cell.env_dir, cell.tool_cli_dir, rg)
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
    rec["allow_source_edits"] = bool(cell.extra.get("allow_source_edits"))
    audit_calls(rec, calls, arm)
    rec["successful_own_tool_actions"] = successful_own_tool_actions(events, calls, arm)
    if active_tool(arm) != "native" and not rec["successful_own_tool_actions"]:
        rec["violations"].append("own tool had no successful calls")
    if any("requires approval" in str(err.get("error") or err.get("content") or "")
           for err in rec.get("tool_errors", [])):
        rec["violations"].append("tool call blocked by approval policy")
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
