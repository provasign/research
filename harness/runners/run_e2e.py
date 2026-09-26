"""End-to-end benchmark runner: 4 arms x 3 models over validated 2026 tasks.

One cell = (task, arm, model). Each cell runs the agent in a throwaway worktree
at base_commit, captures its NON-test diff, and scores it with docker_eval
(apply test_patch + agent diff -> FAIL_TO_PASS pass & no PASS_TO_PASS regress).
The model is the only thing that varies across model rows; the arm is the only
thing that varies across arm columns (tool exposure from ab_endtoend_arms).

Backends (no ANTHROPIC_API_KEY here):
  - sonnet/haiku : `claude -p` (subscription) with the arm's --allowedTools +
    --mcp-config -- the proven ab_agentic_mcp pattern, now end-to-end.
  - local        : run_local_agent.py over ollama (no rate limit).

Resumable + auto-pause: every finished cell writes a result JSON and is skipped
on restart. On an Anthropic usage/rate-limit the cloud path writes a pause
marker (results/e2e/PAUSED.json) and the process exits 42; the caller re-invokes
after the reset (ScheduleWakeup). Run local first (free, always completes), then
cloud.
"""
from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)


import argparse
import os
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOKS_SRC = Path(__file__).resolve().parent.parent / "hooks"

import docker_eval
import fanout_eval
import seeded_refactor
import java_eval
import go_eval
import js_eval
import c_eval
import run_local_agent
import usage_account
from ab_endtoend_arms import ARMS, PRISM_BIN_FOR_ARM


def _prism_bin(arm: str) -> str:
    """The prism binary to invoke for `prism init`/`prism index` for this
    arm -- PATH-resolved "prism" normally, or a specific build's absolute
    path for an arm listed in PRISM_BIN_FOR_ARM (A/B'ing the engine itself
    without touching the real installed prism)."""
    return PRISM_BIN_FOR_ARM.get(arm, "prism")

OUT = Path("results/e2e")
OUT.mkdir(parents=True, exist_ok=True)

_LANG_EVAL = {"java": java_eval, "go": go_eval, "js": js_eval, "c": c_eval}


def _is_java(task) -> bool:
    return task.get("lang") == "java"


def _repo_for(task) -> Path:
    """lang-tagged tasks (java/go/js/c) live in that module's REPO_DIR
    (e.g. ~/gvg-corpus/<repo>); untagged Python tasks use docker_eval's
    e2e-2026 clone convention."""
    lang = task.get("lang")
    if lang in _LANG_EVAL:
        return _LANG_EVAL[lang].REPO_DIR[task["repo"]]
    return docker_eval._repo_dir(task)


def _score(task, diff: str) -> dict:
    """Kind- and language-aware scoring: fanout tasks are scored on
    green + gold-file coverage (fanout_eval); the rest on fail->pass."""
    if not diff.strip():
        return {"resolved": False, "empty_diff": True}
    if task.get("kind") == "fanout":
        return fanout_eval.score(task, diff)
    if task.get("kind") == "seeded_refactor":
        return seeded_refactor.score(_repo_for(task), task, diff)
    lang = task.get("lang")
    if lang == "go":
        return go_eval.score(go_eval.REPO_DIR[task["repo"]], task, diff)
    if lang in ("js", "c"):
        mod = _LANG_EVAL[lang]
        return mod.score(mod.REPO_DIR[task["repo"]], task["repo"], task, diff)
    if _is_java(task):
        return java_eval.score(java_eval.REPO_DIR[task["repo"]], task, diff)
    return docker_eval.score(task, diff)
RATE_HINTS = ("rate limit", "usage limit", "429", "too many requests",
              "overloaded", "please try again later")


# The agent's session died because the API was unreachable, not because of
# anything the agent did. Clamshell sleep on battery (2026-09-25 22:57 ->
# 02:22) cut the network mid-run; claude -p ended with "API Error: Can't
# reach the API server (ENOTFOUND)" and the cell was scored as a loss.
NETWORK_HINTS = ("enotfound", "can't reach the api server", "econnrefused",
                 "econnreset", "etimedout", "network is down", "connection error")


def _network_down(returncode: int, blob: str) -> bool:
    """The session ended on an unreachable API. A blip claude recovered from
    internally never reaches the final output, so it doesn't count."""
    if not any(h in blob for h in NETWORK_HINTS):
        return False
    return returncode != 0 or '"is_error":true' in blob.replace(" ", "") or "api error" in blob


class RateLimited(Exception):
    pass


class NetworkDown(RateLimited):
    """Retry the same cell once the network is back; never score it."""


def _worktree(task):
    """Per-cell LOCAL CLONE at base_commit with every ref stripped -- NOT a
    `git worktree`. A worktree shares the corpus clone's refs, and the corpus
    was cloned after each task's fixing PR merged, so `git log --all` finds the
    gold fix. Measured 2026-09-24 over 366 cells with transcripts: 32 cells
    opened a post-base commit touching the gold source files (`git log --all
    --grep=<issue>` then `git show <sha>`), 27 of them scored resolved
    (mostly jackson-databind: pr6105, 6019, 6042, 6012, 6061, ...). Same
    leak and same fix as swebench_ab.run_arm (2026-08-15), never ported here.
    After the refs and remote are deleted, `git log --all` shows only the base
    commit's ancestry."""
    repo = _repo_for(task)
    wt = Path(tempfile.mkdtemp(prefix="e2e-run-"))
    sh = docker_eval._sh
    sh("git", "clone", "--local", "--no-checkout", "--quiet", str(repo), str(wt), timeout=600)
    # A blobless (promisor) corpus clone can't serve lazy fetches through a
    # file-path origin: point origin at the real remote for the one checkout
    # (setup time, before any agent runs), then strip it.
    if sh("git", "-C", str(repo), "config", "remote.origin.promisor",
          check=False).strip() == "true":
        upstream = sh("git", "-C", str(repo), "remote", "get-url", "origin").strip()
        sh("git", "-C", str(wt), "remote", "set-url", "origin", upstream)
        sh("git", "-C", str(wt), "config", "remote.origin.promisor", "true")
        sh("git", "-C", str(wt), "config", "remote.origin.partialclonefilter", "blob:none")
    sh("git", "-C", str(wt), "checkout", "--detach", "-f", "-q", task["base_commit"], timeout=600)
    for ref in sh("git", "-C", str(wt), "for-each-ref", "--format=%(refname)").split():
        sh("git", "-C", str(wt), "update-ref", "-d", ref)
    sh("git", "-C", str(wt), "remote", "remove", "origin", check=False)
    head = sh("git", "-C", str(wt), "rev-parse", "HEAD").strip()
    if head != task["base_commit"]:
        raise RuntimeError(f"checkout for {task['instance_id']} is at {head!r}, expected "
                           f"{task['base_commit']!r} -- refusing to run on the wrong code")
    return repo, wt


def _remove_worktree(wt: Path):
    shutil.rmtree(wt, ignore_errors=True)


# Index/tool artifacts the context tools drop into the worktree. They MUST be
# excluded from the agent diff: git apply is atomic, so a single binary stub
# (e.g. .grove/grove.db) makes the whole patch unappliable and silently zeroes
# the score (this invalidated every prism-arm cell before 2026-07-14).
TOOL_ARTIFACTS = (".grove", ".engine-b", ".prism", "prism.yaml", ".p.diff",
                  ".shale",  # mason's evidence trail
                  # prism_init writes these into the worktree (real product
                  # setup path); left unexcluded, they leaked into every
                  # prism_init scored diff and hard-failed the build on
                  # RAT-license-audited Apache projects (commons-lang: 0/11
                  # resolved, confirmed independent of code correctness --
                  # see overnight-run/INVESTIGATION.md, 2026-09-21).
                  ".claude", ".mcp.json", "CLAUDE.md",
                  # the read-guard hook's own state file (harness/hooks/
                  # prism_read_tracker.py) -- same leak class as the three
                  # above, self-inflicted this time (found 2026-09-21 in
                  # psf/requests pr7315's scored diff).
                  ".prism-read-tracker.json")


def _agent_diff(wt: Path, task) -> str:  # noqa: D401
    """The agent's change to NON-test files (test_patch is the harness's job)."""
    docker_eval._sh("git", "-C", str(wt), "add", "-A", check=False)
    excludes = [f":(exclude){m}" for m in task["test_modules"]]
    excludes += [f":(exclude){a}" for a in TOOL_ARTIFACTS]
    return docker_eval._sh("git", "-C", str(wt), "diff", "--cached", "--", ".",
                           *excludes, check=False)


def _install_read_guard_hook(wt: Path) -> None:
    """Deny a native Read that substantially overlaps a range prism already
    delivered this session (prism_read_tracker.py/prism_read_guard.py under
    harness/hooks/). Measured 2026-09-21: the single largest fixable driver
    of prism-arm token blowup was re-reading content already delivered by
    prism; advisory steering alone didn't hold up over multi-turn sessions.
    TOOL_ARTIFACTS already excludes .claude/ from the scored diff, so these
    files never leak into agent_diff."""
    hooks_dir = wt / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HOOKS_SRC / "prism_read_tracker.py", hooks_dir / "prism_read_tracker.py")
    shutil.copy(HOOKS_SRC / "prism_read_guard.py", hooks_dir / "prism_read_guard.py")

    settings_path = wt / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    hooks = settings.setdefault("hooks", {})
    hooks.setdefault("PostToolUse", []).append({
        "matcher": "mcp__prism__prism",
        "hooks": [{"type": "command",
                  "command": f"python3 {hooks_dir / 'prism_read_tracker.py'}"}],
    })
    hooks.setdefault("PreToolUse", []).append({
        "matcher": "Read",
        "hooks": [{"type": "command",
                  "command": f"python3 {hooks_dir / 'prism_read_guard.py'}"}],
    })
    settings_path.write_text(json.dumps(settings, indent=2))


PRISM_INIT_ARMS = ("prism_init", "prism_init_deferred", "prism_init_no_guard",
                    "prism_body_baseline", "prism_body_exp")


def _index_graph(wt: Path, arm: str):
    if arm in PRISM_INIT_ARMS:
        # The real product setup path -- writes .mcp.json with the actual
        # resolved binary + --compact, and a CLAUDE.md with prism's own
        # current, correct steering (right tool name, explicit ToolSearch
        # instruction). Hand-rolled MCP configs and guidance strings rot the
        # moment prism's interface changes (measured 2026-09-20: a stale
        # ~/bin/prism path AND stale legacy tool names in ab_endtoend_arms.py,
        # both silently broken for an unknown time). `prism init` is
        # maintained by prism itself, so it can't drift out of sync this way.
        r = subprocess.run([_prism_bin(arm), "init", "--harness", "claude", "--yes", str(wt)],
                           capture_output=True, text=True, timeout=300)
        if not (wt / ".mcp.json").exists():
            raise RuntimeError(
                f"prism init did not create .mcp.json in {wt} "
                f"(rc={r.returncode}): {r.stdout[-300:]} {r.stderr[-300:]}")
        if arm in ("prism_init", "prism_init_no_guard", "prism_body_baseline", "prism_body_exp"):
            # Make the ONE compact tool resident (alwaysLoad) instead of
            # deferred behind a ToolSearch hop. Deferred-by-default was
            # chosen on a 9-task haiku A/B (2026-08-29); on this harness's
            # own Sonnet cells 4/8 prism_source sessions never took the
            # ToolSearch hop at all -- silent, zero-cost-looking
            # non-adoption. alwaysLoad previously measured 90%+ adoption
            # (full38, 2026-08-17+) before being dropped. Under --compact
            # there is exactly one tool to make resident.
            # prism_init_deferred is the otherwise-identical control arm:
            # same real setup, same steering, alwaysLoad withheld -- isolates
            # residency's own effect instead of conflating it with "the MCP
            # server finally worked" (2026-09-22, requested by Topo).
            mcp_path = wt / ".mcp.json"
            mcp_cfg = json.loads(mcp_path.read_text())
            if "prism" in mcp_cfg.get("mcpServers", {}):
                mcp_cfg["mcpServers"]["prism"]["alwaysLoad"] = True
                mcp_path.write_text(json.dumps(mcp_cfg, indent=2))
        # init's own docs say indexing happens automatically on first use, but
        # build it explicitly up front anyway so the agent's first real call
        # never eats first-index latency or a cold-cache miss.
        r2 = subprocess.run([_prism_bin(arm), "index", str(wt)], capture_output=True,
                            text=True, timeout=300)
        if r2.returncode != 0:
            print(f"  [index] WARN prism index rc={r2.returncode}: {r2.stderr[-200:]}")
        if arm != "prism_init_no_guard":
            _install_read_guard_hook(wt)
    elif arm.startswith("prism"):
        r = subprocess.run(["prism", "index", str(wt)], capture_output=True,
                            text=True, timeout=300)
        if r.returncode != 0:
            print(f"  [index] WARN prism index rc={r.returncode}: {r.stderr[-200:]}")
    if arm.startswith("engine-b") or arm.startswith("codegraph"):
        # engine-b requires `init` to CREATE the index; `index` only rebuilds an
        # already-initialized one and errors out on a fresh worktree ("Run
        # engine-b init first"). With capture_output that failure is silent and
        # the arm degrades to grep-only — a crippled strawman. Use init, and fail
        # loudly if the .engine-b index did not materialize so a broken cell is
        # never scored as a real engine-b result.
        r = subprocess.run(["codegraph", "init", str(wt)], capture_output=True,
                           text=True, timeout=600)
        if not (wt / ".codegraph").exists():
            raise RuntimeError(
                f"codegraph init did not create .codegraph in {wt} "
                f"(rc={r.returncode}): {r.stdout[-300:]} {r.stderr[-300:]}")


TASK_TAIL = ("\n\nFix the SOURCE code in this repository so the issue is resolved "
             "and the project's tests pass. Edit source files only; do NOT modify "
             "any test files. Before declaring the fix verified, confirm your test "
             "run actually exercises the code you just edited in THIS checkout -- "
             "not a separately installed copy (e.g. a non-editable `pip install` "
             "into a fresh venv resolves the published package, not your edit; "
             "same risk for a cached node_modules or local Maven/Go module install "
             "that shadows this repo). If you set up an isolated environment to "
             "run tests, install this repo in editable/local mode. "
             "Make the smallest change that works, then stop.")


# A seeded refactor needs its own closing instruction: the generic tail
# ("make the SMALLEST change that works, then stop") tells an agent facing a
# deliberately wide change to do the minimum — measured, the first baseline
# cell stopped after 4 turns. It also promises a test run that never happens
# here; the oracle is `mvn compile` over main sources only.
SEEDED_TAIL = ("\n\nUpdate the source so the project COMPILES again. Every "
               "implementation of the changed method and every call site must be "
               "updated — the change is deliberately wide, so do not stop at the "
               "first few. Verify with `mvn -q compile`. Edit main sources only; "
               "do not modify test files.")


# Host toolchains matching each scorer image (docker_eval python:3.12,
# go_eval golang:1.25, js_eval node:20, c_eval ubuntu:24.04 gcc 13; Java's
# JDK is chosen per task below, the same way java_eval picks its image).
PYTHON_HOME = Path("/opt/homebrew/opt/python@3.12/libexec")
GO_HOME = Path("/opt/homebrew/opt/go@1.25")
NODE_HOME = Path("/opt/homebrew/opt/node@20")
GCC = Path("/opt/homebrew/bin/gcc-13")
GXX = Path("/opt/homebrew/bin/g++-13")


def _agent_env(wt: Path, task) -> tuple[dict, dict]:
    """The agent's environment, identical for every arm of a task.

    Runtimes are pinned to what the scorer uses instead of whatever the host
    defaults to. Unpinned, the host's Java 27 broke Mockito, and each agent
    found its own way out -- native switched to JDK 17, prism excluded
    failing tests and stayed on 27 -- so paired arms ran on different
    runtimes (jackson pr6099, 2026-09-25). Fails loudly when the pinned
    runtime is missing rather than silently falling back to the host's.
    """
    env = dict(os.environ)
    # Apache RAT fails the agent's own mvn builds on any header-less file, and
    # prism_init arms carry .mcp.json + CLAUDE.md in the worktree (native arms
    # carry nothing) -- every commons-lang prism cell burned turns on
    # -Drat.skip / JAVA_HOME workarounds (2026-09-25 rerun audit). Skip RAT in
    # every arm via the environment so neither worktree gains a file. Scoring
    # is unaffected: tool artifacts are already excluded from the scored diff.
    env["MAVEN_ARGS"] = (env.get("MAVEN_ARGS", "") + " -Drat.skip=true").strip()
    jdk = 17
    if _is_java(task):
        # same era rule the scorer uses to pick its maven image
        jdk = int(java_eval.image_for(
            java_eval.commit_date(wt, task["base_commit"])).rsplit("-", 1)[1])
    java_home = Path(f"/opt/homebrew/opt/openjdk@{jdk}")
    for need in (java_home / "bin/java", PYTHON_HOME / "bin/python3",
                 GO_HOME / "bin/go", NODE_HOME / "bin/node", GCC, GXX):
        if not need.exists():
            raise RuntimeError(f"pinned runtime missing on host: {need}")
    env["JAVA_HOME"] = str(java_home)
    bins = ":".join(map(str, [java_home / "bin", PYTHON_HOME / "bin",
                              GO_HOME / "bin", NODE_HOME / "bin"]))
    env["PATH"] = bins + ":" + env.get("PATH", "")
    # Claude Code's Bash tool runs off a snapshot of a login shell, which
    # re-sorts PATH and puts /opt/homebrew/bin back in front. This ZDOTDIR
    # sources the user's real zsh files, then re-prepends E2E_PINNED_PATH.
    env["ZDOTDIR"] = str(Path(__file__).resolve().parent.parent / "hooks/pinned-zdotdir")
    env["E2E_PINNED_PATH"] = bins
    env["SHELL_SESSIONS_DISABLE"] = "1"  # macOS zsh would write .zsh_sessions/ into ZDOTDIR
    # golang:1.25 runs with GOTOOLCHAIN=local; without it the host go
    # silently downloads whatever toolchain a go.mod asks for.
    env["GOTOOLCHAIN"] = "local"
    env["CC"], env["CXX"] = str(GCC), str(GXX)
    return env, {"java": jdk, "python": "3.12", "go": "1.25", "node": "20", "cc": "gcc-13"}


def _run_cloud(model: str, arm: str, wt: Path, task) -> dict:
    spec = ARMS[arm]
    tail = SEEDED_TAIL if task.get("kind") == "seeded_refactor" else TASK_TAIL
    prompt = spec["guidance"] + "\n\nISSUE:\n" + task["problem_statement"] + tail
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--strict-mcp-config",
           "--allowedTools", *spec["allowed"]]
    if arm in PRISM_INIT_ARMS:
        cmd += ["--mcp-config", str(wt / ".mcp.json")]
    elif spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"]]
    env, runtimes = _agent_env(wt, task)
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=1800, env=env)
    blob = (r.stdout + r.stderr).lower()
    if r.returncode != 0 and any(h in blob for h in RATE_HINTS):
        raise RateLimited(blob[-300:])
    if _network_down(r.returncode, blob):
        raise NetworkDown(blob[-300:])
    rec = {"wall_s": round(time.monotonic() - t0, 1), "runtimes": runtimes}
    try:
        j = json.loads(r.stdout)
        rec.update(turns=j.get("num_turns"), cost_usd=j.get("total_cost_usd"))
        rec["usage"] = usage_account.cli_usage(j)
        rec["session_id"] = rec["usage"].get("session_id")
        rec["tokens_request"] = rec["usage"]["input_total"]
        u = rec["usage"]["tokens"]
        rec["tokens_out"] = u["output"]
        rec["tokens_cache_read"] = u["cache_read"]
        rec["tokens_cache_write"] = u["cache_creation"]
    except Exception:
        if any(h in blob for h in RATE_HINTS):
            raise RateLimited(blob[-300:])
        rec["agent_error"] = (r.stderr or r.stdout)[-200:]
    rec["tool_trace"] = _tool_trace_for(wt)
    return rec


def _tool_trace_for(wt: Path) -> dict:
    """Tool-call counts for the session that just ran in worktree wt, mined
    from the claude CLI's own transcript (~/.claude/projects/<cwd-slug>/).
    The -p JSON output carries no per-tool trace; without this the routing
    question ('did the agent grep or graph?') needs manual excavation —
    measured, it was the most useful column of the 2026-08-06 analysis.
    Best-effort: {} when the transcript is not found."""
    # macOS: mkdtemp returns /var/... but the claude CLI records the RESOLVED
    # cwd (/private/var/...) — try both slugs (measured: the unresolved slug
    # matched nothing and every cell's trace came back empty).
    # Match by the worktree's BASENAME, not a computed slug: the CLI rewrites
    # more than slashes (temp names containing "_" come back hyphenated), so
    # any slug we compute here can silently miss. Globbing the basename is
    # robust to whatever transformation it applies to the prefix.
    base = Path(wt).name.replace("_", "-")
    hits = sorted(Path.home().glob(f".claude/projects/*{base}"),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    if hits:
        pdir = hits[0]
        counts: dict = {}
        scope_text = 0
        for f in pdir.glob("*.jsonl"):
            for line in f.open():
                try:
                    j = json.loads(line)
                except Exception:
                    continue
                if j.get("type") != "assistant":
                    continue
                for c in ((j.get("message") or {}).get("content") or []):
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        counts[c["name"]] = counts.get(c["name"], 0) + 1
                        if c["name"].endswith("prism_search") and \
                                (c.get("input") or {}).get("scope") == "text":
                            scope_text += 1
        if scope_text:
            counts["_prism_search_scope_text"] = scope_text
        if counts:
            return counts
    candidates = [str(wt), str(Path(wt).resolve()), "/private" + str(wt)]
    # The CLI flushes its session transcript asynchronously, so a read the
    # instant the process exits can find nothing (measured: 2 cells came back
    # with an empty trace and were briefly misread as "the agent made no
    # searches"). Retry briefly before giving up.
    pdir = None
    for _ in range(10):
        for c in candidates:
            d = Path.home() / ".claude" / "projects" / c.replace("/", "-")
            if d.exists() and any(d.glob("*.jsonl")):
                pdir = d
                break
        if pdir:
            break
        time.sleep(1)
    if pdir is None:
        return {"_trace_unavailable": 1}
    counts: dict = {}
    scope_text = 0
    for f in pdir.glob("*.jsonl"):
        for line in f.open():
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("type") != "assistant":
                continue
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    counts[c["name"]] = counts.get(c["name"], 0) + 1
                    if c["name"].endswith("prism_search") and \
                            (c.get("input") or {}).get("scope") == "text":
                        scope_text += 1
    if scope_text:
        counts["_prism_search_scope_text"] = scope_text
    return counts


def _run_mason(wt: Path, task, arm: str = "mason") -> dict:
    """The competent-local-harness arm: mason (Prism baked in, self-indexes).
    Output is teed to a visible per-cell log; capped at 30 min — the SAME
    budget the cloud arms get (subprocess timeout 1800). The old 600s cap
    killed 11/15 mason v0.28 cells mid-flight: the completeness gate and
    prepare obligations do strictly more engine work per task, and a slow
    local model pays for it in wall-clock, not correctness.

    Two arms share this driver so the ONLY variable is context delivery:
      - "mason":       default (code_context whole-neighborhood dump)
      - "mason_walk":  MASON_WALK=1 (graph_focus part-by-part walk)
    MASON_BIN selects the binary (default "mason") so an experimental build can
    be A/B'd against the released one."""
    import os as _os
    prompt = task["problem_statement"] + TASK_TAIL
    log = OUT / f"{task['instance_id']}.{arm}.transcript.txt"
    binary = _os.environ.get("MASON_BIN", "mason")
    env = dict(_os.environ)
    if arm == "mason_walk":
        env["MASON_WALK"] = "1"
    else:
        env.pop("MASON_WALK", None)
    t0 = time.monotonic()
    timed_out = False
    with open(log, "w") as fh:
        p = subprocess.Popen([binary, "--yes", "--model", "ollama:qwen3-coder:30b",
                              prompt], cwd=wt, stdout=fh, stderr=subprocess.STDOUT,
                             text=True, env=env)
        try:
            p.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(); timed_out = True
    return {"wall_s": round(time.monotonic() - t0, 1), "timed_out": timed_out,
            "transcript": str(log)}


def _save_diff(task, model: str, arm: str, tag: str, diff: str):
    """Persist the agent diff next to the cell JSON so failed fixes can be
    inspected after the worktree is gone."""
    (OUT / f"{task['instance_id']}.{model}.{arm}{tag}.diff").write_text(diff)


def run_cell(task: dict, arm: str, model: str, tag: str = "") -> dict:
    repo, wt = _worktree(task)
    try:
        if arm in ("mason", "mason_walk"):
            meta = _run_mason(wt, task, arm)
            diff = _agent_diff(wt, task)
            _save_diff(task, model, arm, tag, diff)
            _remove_worktree(wt)
            sc = _score(task, diff)
            return {"task": task["instance_id"], "arm": arm, "model": model,
                    "kind": task.get("kind"), "resolved": sc.get("resolved"),
                    "diff_lines": diff.count("\n"), **meta, "score": sc}
        if task.get("kind") == "seeded_refactor":
            # The agent starts from the broken build, not from base.
            seeded_refactor.apply_mutation(wt, task["mutation"])
        _index_graph(wt, arm)
        if model == "local":
            prompt = task["problem_statement"] + TASK_TAIL
            res = run_local_agent.run(
                os.environ.get("LOCAL_MODEL", "qwen3-coder-ctx16k"),
                arm, str(wt), prompt)
            meta = {"turns": res.get("turns"), "wall_s": res.get("wall_s"),
                    "trace": res.get("trace"), "agent_error": res.get("error")}
        else:
            meta = _run_cloud(model, arm, wt, task)
        diff = _agent_diff(wt, task)
        _save_diff(task, model, arm, tag, diff)
    finally:
        _remove_worktree(wt)
    sc = _score(task, diff)
    return {"task": task["instance_id"], "arm": arm, "model": model,
            "kind": task.get("kind"), "resolved": sc.get("resolved"),
            "diff_lines": diff.count("\n"), **meta, "score": sc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--models", default="local,haiku,sonnet")
    ap.add_argument("--arms", default="baseline,prism_g,prism_gstar,engine-b")
    ap.add_argument("--trials", type=int, default=1,
                    help="trials per cell; trial 1 keeps the unsuffixed cell name "
                         "(cache-compatible), trials 2..N write .t<n>.json")
    a = ap.parse_args()
    tasks = [json.loads((Path("tasks/e2e") / f"{i}.json").read_text())
             for i in json.loads(Path(a.manifest).read_text())]
    print(f"# {len(tasks)} tasks x {a.arms} x {a.models}", flush=True)
    import os
    wait_on_limit = os.environ.get("E2E_WAIT_ON_LIMIT") == "1"
    sleep_s = int(os.environ.get("E2E_LIMIT_SLEEP", "1200"))
    for model in a.models.split(","):
        for task in tasks:
            for arm in a.arms.split(","):
                for trial in range(1, a.trials + 1):
                    tag = "" if trial == 1 else f".t{trial}"
                    f = OUT / f"{task['instance_id']}.{model}.{arm}{tag}.json"
                    if f.exists():
                        print(f"  (cached) {f.name}", flush=True); continue
                    while True:  # retry the SAME cell across a rate-limit window
                        try:
                            rec = run_cell(task, arm, model, tag)
                            break
                        except RateLimited as e:
                            (OUT / "PAUSED.json").write_text(json.dumps(
                                {"at": f.name, "reason": str(e)[:200], "ts": int(time.time())}))
                            if not wait_on_limit:
                                print(f"  PAUSED at {f.name}: rate-limited", flush=True)
                                sys.exit(42)
                            print(f"  RATE-LIMITED at {f.name}; sleeping {sleep_s}s then retrying",
                                  flush=True)
                            time.sleep(sleep_s)
                        except Exception as e:  # noqa: BLE001
                            # Fault-isolate a single bad cell (engine-b index failure,
                            # maven timeout, apply reject) so a 30h unattended run does
                            # not die on one task. Record the error and move on.
                            import traceback
                            rec = {"task": task["instance_id"], "arm": arm, "model": model,
                                   "resolved": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                            print(f"  ERROR {f.name}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                            traceback.print_exc()
                            break
                    (OUT / "PAUSED.json").unlink(missing_ok=True)
                    rec["trial"] = trial
                    f.write_text(json.dumps(rec, indent=2))
                    print(f"  {model:7} {arm:12} {task['instance_id'][-24:]:24} "
                          f"t{trial} resolved={rec['resolved']} turns={rec.get('turns')} "
                          f"wall={rec.get('wall_s')}s", flush=True)
    print("# done", flush=True)


if __name__ == "__main__":
    main()
