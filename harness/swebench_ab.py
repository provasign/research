#!/usr/bin/env python3
"""SWE-bench A/B: does prism make an agent fix real issues cheaper/faster at
EQUAL correctness? Real GitHub issues, the fixing PR's tests as the oracle.

Two arms per task, identical except for prism availability:
  no-prism : Read/Edit/Write + shell (grep/find/git). Plain agent baseline.
  prism    : the same, PLUS the prism CLI (pre-indexed) and its steering block.

Correctness is judged by the SWE-bench test oracle (FAIL_TO_PASS must flip to
pass, PASS_TO_PASS must stay pass) — so "equivalent fix" means "clears the same
objective bar", not "textually identical". Only tasks BOTH arms resolve (or the
resolve-rate itself) are the correctness comparison; turns/tokens/cost are the
efficiency comparison, fair because both cleared the same oracle.

This runner produces predictions.jsonl per arm + a metrics record per task. The
CORRECTNESS eval is the standard SWE-bench harness and needs Docker:

  python -m swebench.harness.run_evaluation \
      --predictions_path runs/swebench/<arm>.predictions.jsonl \
      --run_id prism-ab-<arm> --dataset_name princeton-nlp/SWE-bench_Verified

Usage:
  python swebench_ab.py --tasks /tmp/swebench_slice.json --limit 20 \
      --arms no-prism prism --out runs/swebench --prism ~/bin/prism
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
# NOT /tmp: macOS's periodic cleaner deletes /tmp files untouched for 3+
# days while KEEPING directories — observed 2026-08-15 00:00: all 32 cached
# clones lost .git/HEAD+config simultaneously, leaving repos that LOOK
# present but where checkout silently fails and the working tree stays at
# clone-time state. A smoke ran on the wrong code for 64 turns before a
# human noticed. Cache lives in $HOME now; integrity is CHECKED, not assumed.
REPO_CACHE = Path.home() / ".cache" / "prism-research" / "swebench-repos"
WT_ROOT = Path("/tmp/swebench-wt")
RUN_TIMEOUT_S = 1800

# The prism CLI steering block, kept in sync with prism's own `init` output —
# the agent sees the same guidance a real prism user gets.
# Matched-arm design (per RESULTS.md §8.2.1 finding #4: arm comparisons need
# MATCHED steering or the tool effect is unmeasurable). BOTH arms receive
# INVESTIGATION_GUIDANCE verbatim; the prism arm additionally receives
# PRISM_STEERING, which is a purely DESCRIPTIVE tool reference — no workflow
# doctrine, no request-pricing mandate. The arms differ in tool availability
# and tool documentation only.
INVESTIGATION_GUIDANCE = """
Investigation discipline (applies regardless of which tools you use):
- Where an error is raised is where the bug SURFACES, not necessarily where it
  lives. Before deciding where to edit, read the WHOLE file that defines the
  failing behavior, not just the lines a search hit.
- Before finishing, run the tests for the module the issue is about, not only
  the tests nearest the code you edited.
- Make the smallest change that resolves the issue; do not restructure
  neighboring code the issue does not require.
"""

# FAITHFUL DEPLOYMENT ARM -- what "faithful" means has changed twice, so the
# history matters:
#
#   through v0.49.x : `prism init --deny-builtin-search` wrote
#                     permissions.deny [Grep, Bash(grep:*), Bash(rg:*)];
#                     the harness simulated it via --disallowedTools.
#   v0.50.0-v0.51.x : a PreToolUse hook became the primary mechanism, so the
#                     harness switched to running the real init in-worktree.
#   v0.52.0 onward  : THE WHOLE DENIAL ARC WAS REVERTED. There is no hook,
#                     and the shipped `prism init` writes NO deny rules.
#
# The harness kept calling `prism init --deny-builtin-search` after that
# revert, so every prism-arm cell ran with grep/rg blocked -- a configuration
# no prism user gets. Caught 2026-08-15 in the v054-smoke traces: 4 denied
# grep calls in the prism arm, 0 in baseline, with the agent burning turns
# retrying before falling back to prism_search. Numbers from runs before this
# fix measure prism-plus-a-denial, not prism.
#
# Faithful now means: plain `prism init`, no flag. The agent gets .mcp.json,
# the steering block, and a free choice between grep and prism -- which is
# the actual question ("do agents reach for it when they don't have to?").
#
# SEARCH_TOOLS survives only as the historical marker of what used to be
# stripped from --allowedTools. Nothing strips it now.
SEARCH_TOOLS = {"Grep", "Bash(grep:*)", "Bash(rg:*)"}

# Everything `prism init` can create or append to inside a worktree. Excluded
# from the prediction diff so the treatment arm's patch is the agent's work
# and nothing else. Keep in sync with writeSteeringInstructions +
# initRegisterMCPTools in prism's internal/cli/commands.go.
PRISM_FOOTPRINT = [
    ".grove", "prism.yaml", ".mcp.json",
    "CLAUDE.md", "GEMINI.md", "Gemini.md", "AGENTS.md",
    ".cursorrules", ".windsurfrules", ".clinerules",
    ".cursor", ".windsurf", ".vscode", ".kiro", ".devin",
    ".github/copilot-instructions.md", ".claude",
]


def prism_provenance(prism: str) -> dict:
    """Identify the binary under test, and refuse to run without one.

    A run's conclusions are about a specific prism build; recording only the
    PATH is not enough, because ~/bin/prism is routinely rebuilt. Capture the
    version string, the mtime, and the tool surface the MCP server actually
    advertises -- the last of these is what a tool-surface experiment is
    changing, so a run that does not record it cannot be interpreted later.
    """
    exe = Path(prism).expanduser()
    if not exe.exists():
        raise RuntimeError(f"--prism {prism} does not exist; nothing to test")
    ver = sh(str(exe), "version", timeout=30).stdout.strip() or "(no version output)"
    # A local `go build` reports "prism dev", which identifies nothing — and
    # ~/bin/prism is rebuilt constantly. Hash the bytes so a results directory
    # names an exact build, not a moving path.
    import hashlib
    h = hashlib.sha256()
    with open(exe, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    tools = []
    try:
        req = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n'
        out = subprocess.run([str(exe), "mcp", "."], input=req, capture_output=True,
                             text=True, timeout=60).stdout.splitlines()
        for line in out:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "result" in d and "tools" in d["result"]:
                tools = sorted(t["name"] for t in d["result"]["tools"])
                break
    except Exception:
        pass
    return {"path": str(exe), "version": ver, "sha256": h.hexdigest(),
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(exe.stat().st_mtime)),
            "mcp_tools": tools, "mcp_tool_count": len(tools)}


def mark_trusted(path) -> None:
    """Headless `claude -p` ignores permissions.allow (and therefore
    mcp__prism) in a workspace it has never seen accept the trust dialog --
    verified live 2026-08-14 (prism_search calls failed with "you haven't
    granted it yet" despite a correct permissions.allow entry). Each
    worktree is a fresh, never-before-seen path, so this must run before
    every prism-arm agent invocation."""
    import json as _json
    cfg = Path.home() / ".claude.json"
    doc = _json.loads(cfg.read_text()) if cfg.exists() else {}
    doc.setdefault("projects", {})[str(path)] = {
        **doc.get("projects", {}).get(str(path), {}), "hasTrustDialogAccepted": True}
    cfg.write_text(_json.dumps(doc, indent=2))


def unmark_trusted(path) -> None:
    """Undo mark_trusted after a worktree is torn down -- unbounded growth
    of ~/.claude.json's projects map across a 38+ instance run otherwise."""
    import json as _json
    cfg = Path.home() / ".claude.json"
    if not cfg.exists():
        return
    doc = _json.loads(cfg.read_text())
    doc.get("projects", {}).pop(str(path), None)
    cfg.write_text(_json.dumps(doc, indent=2))


# CLI ARM STEERING (2026-08-15). The shipped product has no CLI-only mode:
# `prism init --mode` is accepted and IGNORED since v0.38.0, and the one
# steering block it writes is MCP-first -- its opening instruction is to
# ToolSearch for prism_* tools, which in a CLI deployment sends the agent
# hunting for tools that do not exist. So the CLI arm cannot reuse the shipped
# block with the MCP part deleted; it needs the inverse, and the harness owns
# it until a measurement justifies adding the mode back to the product.
#
# Deliberately parallel in CONTENT to real_prism_steering(): same routes, same
# relay rule, same batching advice. Only the surface differs. An arm
# comparison where the two texts teach different things measures the prose,
# not the surface.
CLI_PRISM_STEERING = """
## Prism — code intelligence (a command, already indexed)

`prism` is on your PATH and this repo is indexed. It answers structural
questions a text search cannot, and costs nothing until you call it.

    prism search <term> [more terms...] --scope text --format text
        where is X? --scope text is a plain grep. Pass SEVERAL terms to
        search them in one call (up to 10), grouped by term.
    prism lookup <pkg.Func> --format text        read one function
    prism read <file> --format text              read one file
    prism query "<label>" --terms X --format text
        edit-ready context for X: source windows plus callers. Keys on
        --terms; the label wording changes nothing.
    prism change-impact 'Type.method' --format text
        who breaks if I change X: declarations, every override and
        implementation, all resolved callers, in one call. Relay that set
        as-is -- re-checking it with grep measurably drops real sites.
    prism verify --base <ref>                    is my diff complete?

Keep `--format text`: without it you get JSON, which is ~2x the tokens for
the same hits. Keep `--scope text` on a plain search: without it the CLI
returns full symbol bodies for a text question.
"""

# UNWIRED as of 2026-08-15 and STALE: nothing passes steering_variant="short"
# (it defaults to "full"), and this text describes the v0.50-era surface —
# tools resident rather than deferred, no prism_verify, no multi-term search.
# The live path is real_prism_steering(), which reads the block prism's own
# `init` writes, so the arm always sees what a user sees. Left for the
# short-steering probe; rewrite from AGENTS.md before reusing it.
SHORT_PRISM_STEERING = """
## Prism — code intelligence (already in your tool list)

prism_search/query/read/lookup/change_impact are loaded now; call them
directly, no lookup step. Locate a string/symbol -> prism_search(scope="text")
(a real ripgrep pass, same cost as grep). Bug/task with an anchor ->
prism_query(task=..., terms=[...]) -- terms is required, guess one keyword.
Signature change, rename, or "who breaks if I change X" ->
prism_change_impact -- returns the complete site set in one call; do not
re-verify it with grep, that measurably drops real sites. A repeat
prism_read of an unchanged file returns a short cached-pointer line, not
the body -- that is not an error.
"""


def real_prism_steering() -> str:
    src = Path.home() / "Projects/provasign/prism/AGENTS.md"
    text = src.read_text()
    end = text.find("<!-- prism:end -->")
    return text[:end].strip() if end >= 0 else text.strip()

BASE_PROMPT = """You are fixing a real bug in the {repo} repository, checked out at the
commit where the bug exists. Read the issue, find the cause in the code, and EDIT
the source files to fix it. Do not write a new test; the project's own test suite
will judge your fix. Make the smallest change that resolves the issue.

ISSUE:
{problem}

When done, stop — your edits to the working tree are the submission.{steer}"""

# TOOLS_BASE was an ENUMERATION of binaries, and it did not match how Python
# projects are actually built. Measured over 380 denials in the 38-task run
# (2026-08-15): `uv` 93, `pip`, `pytest`, `PYTHONPATH=... python3` 46, `env`
# 15, absolute venv paths. None of those are dangerous; they were simply
# absent. The cost was not noise but SIGN: corr(delta-denials, delta-turns)
# = +0.89, and every large cost swing in that run was a cell where one arm
# hit the allowlist harder than the other. The four denial-confounded cells
# had median delta-cost -1.07; the other 26 had +0.035.
#
# An env-var prefix cannot be expressed as a binary pattern at all -- there
# is no allowlist entry that makes `PYTHONPATH=src python3 ...` match
# Bash(python3:*), because the leading token is the assignment.
#
# So: allow Bash broadly and DENY the boundary explicitly. Verified live
# 2026-08-15 with two probes ($0.36 total):
#
#   allowedTools Bash + disallowedTools gh/curl/wget/WebFetch/WebSearch
#     PYTHONPATH=. python3 -c ...   RAN      (denied under the old list)
#     uv --version                  RAN      (denied under the old list)
#     pip --version                 RAN      (denied under the old list)
#     gh --version                  DENIED   <- contamination boundary holds
#     curl https://example.com      DENIED   <- contamination boundary holds
#
# NOTE the harness's own 2026-08-11 comment claimed omission from
# --allowedTools does not deny in headless mode. That was true then and is
# NOT true now: --allowedTools alone produced all 380 denials, with
# disallowed= never passed. Probe before trusting either mechanism again.
TOOLS_BASE = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]

# The contamination + destruction boundary, enforced by --disallowedTools.
# gh and curl are the routes to the gold fix an agent actually tried: the
# beets-5890 cell ran `gh pr view 5890 --json title,body,files` twice and
# WebFetch'd github.com/beetbox/beets/pull/5890/files, all denied. The
# instance_id leaks the PR number, so this is not hypothetical.
# git's network path is closed separately by GIT_ALLOW_PROTOCOL=file.
#
# `rm` is deliberately NOT here. It was denied 27 times in the 38-task run,
# all of it legitimate scratch-file cleanup, and blocking it produced retry
# loops. Agents work inside a throwaway worktree the harness deletes anyway.
# The residual risk is an agent removing something outside that worktree;
# accepted knowingly, because a benchmark that cannot clean up after itself
# measures the allowlist instead of the agent.
DENIED_TOOLS = ["Bash(gh:*)", "Bash(curl:*)", "Bash(wget:*)",
                "Bash(ssh:*)", "Bash(scp:*)", "Bash(nc:*)", "Bash(sudo:*)",
                "WebFetch", "WebSearch"]


def sh(*args, cwd=None, timeout=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def ensure_repo(repo: str) -> Path:
    """Clone `owner/name` once (blobless) into the cache; re-clone if the
    cached copy fails an integrity check (a present-looking but gutted .git
    is exactly what the /tmp cleaner left behind)."""
    dest = REPO_CACHE / repo.replace("/", "__")
    if dest.exists():
        ok = sh("git", "-C", str(dest), "rev-parse", "--git-dir")
        if ok.returncode != 0:
            print(f"!! cache integrity failure for {repo} — re-cloning", flush=True)
            import shutil
            shutil.rmtree(dest, ignore_errors=True)
    if not dest.exists():
        REPO_CACHE.mkdir(parents=True, exist_ok=True)
        sh("git", "clone", "--filter=blob:none", "--quiet",
           f"https://github.com/{repo}.git", str(dest))
    return dest


def _clip(v, n=300):
    """Truncate one tool-argument value for the metrics file.

    Lists are kept as lists (the whole point is seeing that query=["a","b"]
    was a batch of two), just with each element clipped.
    """
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + f"...[+{len(v)-n} chars]"
    if isinstance(v, list):
        return [_clip(x, 80) for x in v[:20]]
    if isinstance(v, dict):
        return {k: _clip(x, 80) for k, x in list(v.items())[:20]}
    return v


def parse_stream(stdout: str) -> dict:
    env = {"result": ""}
    trace = []
    calls = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "system" and obj.get("subtype") == "init":
            # The init event lists the tools ACTUALLY loaded at turn one —
            # the ground truth for whether MCP schemas were deferred.
            env["init_tools"] = obj.get("tools", [])
        elif obj.get("type") == "assistant":
            for b in obj.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    inp = b.get("input", {})
                    if name == "Bash":
                        trace.append(inp.get("command", "")[:120])
                    elif name == "ToolSearch":
                        trace.append(f"ToolSearch({inp.get('query','')})"[:120])
                    else:
                        trace.append(name)
                    # tool_trace keeps its historical string shape (every
                    # existing analysis parses it), but for MCP tools it kept
                    # the NAME ONLY and dropped the arguments -- so a run
                    # could not answer "did the agent batch its search terms?"
                    # or "what scope did it ask for?", which is exactly what
                    # a tool-surface change needs to be judged on. Record the
                    # arguments alongside, truncated so a big task string or
                    # file body cannot bloat the metrics file.
                    calls.append({
                        "name": name,
                        "input": {k: _clip(v) for k, v in inp.items()},
                    })
        elif obj.get("type") == "result":
            env.update(obj)
    env["tool_trace"] = trace
    env["tool_calls"] = calls
    # prism use = MCP tool call OR the CLI binary run as a command (path
    # segments containing "prism" don't count). The pre-2026-08-11 version
    # missed MCP calls entirely and under-reported adoption.
    env["prism_used"] = any(
        t.startswith("mcp__prism")
        or re.search(r"(?:^|[\s;&|(])(?:[^\s;&|(]*/)?prism\s", t)
        for t in trace)
    return env


def run_agent(prompt: str, tools: list[str], workdir: Path, model: str = "",
              mcp: str = "", disallowed: list[str] | None = None) -> dict:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--allowedTools", ",".join(tools)]
    if disallowed:
        # BOTH mechanisms enforce, as of 2026-08-15. The 2026-08-11 note here
        # said omission from --allowedTools does not deny -- that has since
        # changed: --allowedTools alone produced all 380 denials in the
        # 38-task run, with this parameter never supplied. --disallowedTools
        # still enforces too (probe: gh and curl refused under a broad Bash
        # allow). We now rely on BOTH: Bash broadly allowed, boundary denied.
        # Re-probe before trusting either; this behaviour has moved once.
        cmd += ["--disallowedTools", ",".join(disallowed)]
    if mcp:
        cmd += ["--mcp-config", mcp]
    if model:
        cmd += ["--model", model]
    t0 = time.time()
    # GIT_ALLOW_PROTOCOL=file: git stays fully usable locally but cannot fetch
    # over the network. Audit of trials 1-2 caught agents running
    # `git fetch origin refs/pull/<N>/head` to pull the GOLD fix (the instance
    # id leaks the PR number); gh/curl were already blocked by the allowlist,
    # git was the remaining hole. Applies identically to both arms.
    env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file"}
    proc = subprocess.Popen(cmd, cwd=str(workdir), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True,
                            env=env)
    try:
        out, err = proc.communicate(timeout=RUN_TIMEOUT_S)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        out, err = proc.communicate()
        timed_out = True
    env = parse_stream(out)
    env["_wall_s"] = round(time.time() - t0, 1)
    env["_timed_out"] = timed_out
    return env


# Files through which a corpus checkout could smuggle steering into a cell.
# ARM ISOLATION RULE: the baseline arm must carry ZERO prism steering or
# config; the prism arm's deployment comes exclusively from the harness
# (prompt-injected generated steering + --mcp-config + tool list), never
# from files in the checkout — otherwise a prism-configured corpus repo
# double-steers one arm and contaminates the other.
STEERING_FILES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules",
                  ".windsurfrules", ".clinerules", ".mcp.json",
                  ".github/copilot-instructions.md"]
STEERING_DIRS = [".claude", ".cursor", ".windsurf", ".grove", ".kiro",
                 ".devin", ".vscode"]


def sanitize_worktree(wt: Path, arm: str) -> list[str]:
    """Strip anything prism-related the checkout brought with it, BOTH arms.
    Returns what was removed so the cell record can prove isolation."""
    import shutil
    removed = []
    for rel in STEERING_FILES:
        p = wt / rel
        if p.exists() and "prism" in p.read_text(errors="ignore").lower():
            p.unlink()
            removed.append(rel)
    for rel in STEERING_DIRS:
        p = wt / rel
        if p.is_dir():
            probe = " ".join(str(f) for f in p.rglob("*"))
            if "prism" in probe.lower() or rel in (".claude", ".grove"):
                shutil.rmtree(p, ignore_errors=True)
                removed.append(rel + "/")
    return removed


def run_arm(task: dict, arm: str, prism: str, model: str = "",
            steering_variant: str = "full") -> dict:
    """Check out the task's repo at base_commit, run the agent, capture the
    patch (git diff of its edits) + efficiency metrics."""
    repo_dir = ensure_repo(task["repo"])
    wt = WT_ROOT / f"{task['instance_id']}__{arm}"
    WT_ROOT.mkdir(parents=True, exist_ok=True)
    # Per-cell LOCAL CLONE with every ref stripped — NOT a worktree. A
    # worktree shares the cache's refs, and the cache (cloned after every
    # task's fixing PR merged) carries the GOLD FIX on origin/main. Agents
    # provably mined it: 2026-08-15 audit found 21/228 cells running
    # `git log --all` + `git show <sha>`; sonnet38 baseline dbbackup-623
    # showed 1c40705 — the literal fix commit for its own task ("...
    # auto-enabling --if-exists (#623)") — then edited and scored
    # resolved=True. GIT_ALLOW_PROTOCOL=file blocked FETCHING the fix but
    # the clone already contained it. --local hardlinks objects (cheap);
    # checkout runs while origin still points at the cache (so a blobless
    # cache can lazy-fetch), THEN all refs and the remote are deleted:
    # future history becomes unreachable-by-discovery — `git log --all`
    # shows only the detached base commit's ancestry.
    sh("git", "clone", "--local", "--no-checkout", "--quiet",
       str(repo_dir), str(wt))
    # The cache is blobless; a --local clone's origin is a file path, which
    # cannot serve promisor lazy-fetches. Re-point origin at the real remote
    # (with promisor config) for the one checkout that materializes the
    # tree — network at SETUP time, before any agent runs — then strip.
    upstream = sh("git", "-C", str(repo_dir), "remote", "get-url", "origin").stdout.strip()
    sh("git", "-C", str(wt), "remote", "set-url", "origin", upstream)
    sh("git", "-C", str(wt), "config", "remote.origin.promisor", "true")
    sh("git", "-C", str(wt), "config", "remote.origin.partialclonefilter", "blob:none")
    sh("git", "-C", str(wt), "checkout", "--detach", "-f", "-q", task["base_commit"])
    for ref in sh("git", "-C", str(wt), "for-each-ref",
                  "--format=%(refname)").stdout.split():
        sh("git", "-C", str(wt), "update-ref", "-d", ref)
    sh("git", "-C", str(wt), "remote", "remove", "origin")
    # A checkout that silently failed (corrupted cache, missing blobs) leaves
    # the agent editing the WRONG CODE while every downstream number still
    # gets recorded. Verify, don't assume.
    head = sh("git", "-C", str(wt), "rev-parse", "HEAD").stdout.strip()
    if head != task["base_commit"]:
        raise RuntimeError(
            f"worktree for {task['instance_id']} is at {head!r}, expected "
            f"{task['base_commit']!r} — refusing to run an agent on the wrong code")
    isolation_removed = sanitize_worktree(wt, arm)
    try:
        steer = "\n" + INVESTIGATION_GUIDANCE
        tools = list(TOOLS_BASE)
        mcp_cfg = ""
        if arm == "prism-cli":
            # CLI arm: prism as a SHELL COMMAND only -- no MCP server, no
            # .mcp.json, no tool schemas in context. This is what the t1/t2
            # beds ran (commit 119d8ff) before 2bec8bf replaced it with the
            # MCP deployment; those two beds are the ones where prism came out
            # cheaper in 76% of cells against 44% for the MCP beds, which is
            # the observation this arm exists to test properly.
            #
            # The difference that matters is FIXED COST: an MCP arm pays tool
            # schemas as fresh context every session whether or not anything
            # is called (measured 2026-08-15: +19k fresh tokens and +$0.20 on
            # a cell where prism was never invoked). A CLI arm pays nothing
            # until the agent types `prism`.
            sh(prism, "index", ".", cwd=str(wt), timeout=600)
            tools = list(TOOLS_BASE) + ["Bash(prism:*)", f"Bash({prism}:*)"]
            steer += "\n" + CLI_PRISM_STEERING
        elif arm.startswith("prism"):
            # Run the REAL `prism init` in THIS worktree -- no flags -- so the
            # agent gets exactly what a user gets: .mcp.json, the steering
            # block, and grep still available. stdin is DEVNULL: the
            # interactive "register global tools?" prompt must never block on
            # stdin in a headless run.
            subprocess.run([prism, "init"], cwd=str(wt),
                           capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=120)
            # Verify, don't assume (the lesson of the corrupted-cache bug):
            # a stray deny rule silently turns this into a different
            # experiment, and the symptom -- an agent "choosing" prism -- looks
            # like a POSITIVE result rather than a broken one.
            _sp = wt / ".claude" / "settings.json"
            if _sp.exists():
                _deny = (json.loads(_sp.read_text())
                         .get("permissions", {}).get("deny", []))
                if _deny:
                    raise RuntimeError(
                        f"{task['instance_id']}: prism init wrote deny rules {_deny} "
                        "into the prism arm. The shipped product denies nothing; "
                        "this would measure a configuration no user runs.")
            sh(prism, "index", ".", cwd=str(wt), timeout=600)
            mark_trusted(wt)
            mcp_cfg = str(wt / ".mcp.json")
            # Enrichment-smoke arm (2026-08-15, prototype branch
            # proto/posttooluse-enrichment): identical deployment PLUS the
            # PostToolUse Read-enrichment hook, injected into the worktree's
            # settings.json. Gated on an explicit env var so ordinary runs
            # are untouched.
            if arm == "prism-enrich":
                hook_cmd = os.environ.get("PRISM_POSTTOOLUSE_HOOK")
                if not hook_cmd:
                    raise RuntimeError("arm prism-enrich requires PRISM_POSTTOOLUSE_HOOK")
                sp = wt / ".claude" / "settings.json"
                doc = json.loads(sp.read_text()) if sp.exists() else {}
                doc.setdefault("hooks", {}).setdefault("PostToolUse", []).append(
                    {"matcher": "Read",
                     "hooks": [{"type": "command", "command": hook_cmd}]})
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_text(json.dumps(doc, indent=2))
            # --allowedTools is the harness's overall safety boundary (no
            # arbitrary network/destructive commands) -- it is NOT how grep
            # gets blocked anymore, so Grep/grep/rg stay in it unmodified,
            # same as a real user's config. mcp__prism must be in-scope for
            # MCP calls to be reachable at all.
            tools = list(TOOLS_BASE) + ["mcp__prism"]
            steer += "\n" + (SHORT_PRISM_STEERING if steering_variant == "short"
                               else real_prism_steering())
        prompt = BASE_PROMPT.format(repo=task["repo"], problem=task["problem_statement"],
                                    steer=steer)
        env = run_agent(prompt, tools, wt, model, mcp=mcp_cfg,
                        disallowed=DENIED_TOOLS)
        # The prediction patch = the agent's edits (exclude the .grove index).
        # The prediction is the agent's edits to the PROJECT -- not prism's
        # own footprint. `prism init` appends its steering block to whatever
        # agent-instruction files the repo already ships, so CLAUDE.md,
        # GEMINI.md and AGENTS.md turn up as modifications in the diff:
        # measured 2026-08-16, 6 of 19 prism-arm patches were polluted this
        # way against 0 baseline. It did not change a verdict in that run
        # (checked: stripping them scored identically), but a repo whose
        # CLAUDE.md conflicts would abort `git apply --3way` and score a
        # correct fix as failed -- silently, and only ever in the prism arm.
        patch = sh("git", "-C", str(wt), "diff", "--", ".",
                   *(f":(exclude){p}" for p in PRISM_FOOTPRINT)).stdout
        usage = env.get("usage") or {}
        denials = env.get("permission_denials") or []
        # Word-boundary match on the command's LEADING token only (grep as
        # the invoked binary, not a substring anywhere in the command line --
        # a naive "grep" in str(cmd) false-positived on this repo's own
        # worktree path /tmp/swebench-wt-grepwarn, which contains "grep").
        _search_re = re.compile(r"(?:^|[\s;&|(])(?:[^\s;&|(]*/)?(?:sudo\s+)?(?:rg|grep)\b")
        # Heuristic, same class of imprecision as prism_used's regex above: a
        # quoted string mentioning "grep" (e.g. echo "use grep") can
        # false-positive. Acceptable for a diagnostic count, not a security
        # boundary -- the worktree's own settings.json (hook + deny,
        # written by `prism init` above) is the actual enforcement now.
        denied_search_attempts = [
            d for d in denials
            if d.get("tool_name") == "Bash"
            and _search_re.search(str(d.get("tool_input", {}).get("command", "")))
        ] if arm.startswith("prism") else []
        return {
            "instance_id": task["instance_id"], "arm": arm,
            "isolation_removed": isolation_removed,
            "prism_tools_loaded_at_init": sorted(
                t for t in (env.get("init_tools") or []) if "prism" in t.lower()),
            # Proves denial actually fired, not just that a grep command
            # appears in tool_trace (an attempted-then-denied call and a
            # successful call look IDENTICAL in tool_trace alone -- that
            # ambiguity is exactly what hid the 2026-08-11 bug).
            "permission_denials": denials,
            "denied_search_attempts": len(denied_search_attempts),
            "model_patch": patch,
            "empty_patch": not patch.strip(),
            "turns": env.get("num_turns"),
            # Fresh (billed-at-full) input vs cheap cache reads, kept separate —
            # cache reads dominate and would distort a raw "input tokens" total;
            # cost_usd is the honest efficiency metric (it weights them correctly).
            "fresh_input_tokens": usage.get("input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": env.get("total_cost_usd"),
            "wall_s": env.get("_wall_s"),
            "timed_out": env.get("_timed_out"),
            "prism_used": env.get("prism_used"),
            "tool_trace": env.get("tool_trace", []),
            "tool_calls": env.get("tool_calls", []),
        }
    finally:
        if arm == "prism-cli":
            # CLI arm: prism as a SHELL COMMAND only -- no MCP server, no
            # .mcp.json, no tool schemas in context. This is what the t1/t2
            # beds ran (commit 119d8ff) before 2bec8bf replaced it with the
            # MCP deployment; those two beds are the ones where prism came out
            # cheaper in 76% of cells against 44% for the MCP beds, which is
            # the observation this arm exists to test properly.
            #
            # The difference that matters is FIXED COST: an MCP arm pays tool
            # schemas as fresh context every session whether or not anything
            # is called (measured 2026-08-15: +19k fresh tokens and +$0.20 on
            # a cell where prism was never invoked). A CLI arm pays nothing
            # until the agent types `prism`.
            sh(prism, "index", ".", cwd=str(wt), timeout=600)
            tools = list(TOOLS_BASE) + ["Bash(prism:*)", f"Bash({prism}:*)"]
            steer += "\n" + CLI_PRISM_STEERING
        elif arm.startswith("prism"):
            unmark_trusted(wt)
        import shutil
        shutil.rmtree(wt, ignore_errors=True)  # standalone clone now, not a worktree


def fetch_tasks(out: str, n: int) -> None:
    """Pull a repo-diverse slice of SWE-bench Verified via the HF
    datasets-server API (no `datasets` package needed)."""
    import urllib.request
    rows, offsets = [], list(range(0, 500, max(1, 500 // max(n // 8, 1))))
    for off in offsets:
        url = ("https://datasets-server.huggingface.co/rows?dataset="
               "princeton-nlp%2FSWE-bench_Verified&config=default&split=test"
               f"&offset={off}&length=10")
        try:
            d = json.load(urllib.request.urlopen(url, timeout=30))
            rows += [r["row"] for r in d.get("rows", [])]
        except Exception as e:
            print("skip", off, e)
        time.sleep(0.3)
    json.dump(rows, open(out, "w"))
    from collections import Counter
    print(f"fetched {len(rows)} tasks -> {out}")
    for repo, c in Counter(r["repo"] for r in rows).most_common():
        print(f"  {repo}: {c}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", type=int, metavar="N",
                    help="fetch N SWE-bench Verified tasks to --tasks and exit")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--limit", type=int, default=20)
    # "baseline" not "no-prism": the arm name becomes a worktree dir, and
    # "no-prism" contains the substring "prism" which fooled usage detection.
    ap.add_argument("--arms", nargs="+", default=["baseline", "prism"])
    ap.add_argument("--out", default="runs/swebench")
    ap.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    ap.add_argument("--model", default="opus")
    args = ap.parse_args()

    if args.fetch:
        fetch_tasks(args.tasks, args.fetch)
        return

    tasks = json.load(open(args.tasks))[:args.limit]
    outdir = HARNESS / args.out
    outdir.mkdir(parents=True, exist_ok=True)

    # Idempotent resume: per-task metric JSONs are the source of truth and
    # survive a kill. Skip any (task, arm) already recorded; a re-launch picks
    # up exactly where a turn-boundary kill left off, re-paying for nothing.
    prov = None
    if any(a.startswith("prism") for a in args.arms):
        prov = prism_provenance(args.prism)
        print(f"prism under test: {prov['version']}  ({prov['path']}, built {prov['mtime']})")
        print(f"  MCP surface: {prov['mcp_tool_count']} tools -> "
              f"{', '.join(t.replace('prism_', '') for t in prov['mcp_tools']) or '(none)'}")
        # Written next to the cells so a results directory is self-describing:
        # "which build produced these numbers" must not depend on shell history.
        json.dump(prov, open(outdir / "prism_provenance.json", "w"), indent=2)
        print()

    for i, task in enumerate(tasks):
        for arm in args.arms:
            recpath = outdir / f"{task['instance_id']}.{arm}.json"
            if recpath.exists():
                print(f"[{i+1}/{len(tasks)}] {task['instance_id']} :: {arm}  SKIP (done)", flush=True)
                continue
            print(f"[{i+1}/{len(tasks)}] {task['instance_id']} :: {arm}", flush=True)
            rec = run_arm(task, arm, args.prism, args.model)
            # A cell that produced no turns and no cost is a FAILED INVOCATION
            # -- rate limit, auth, a dead CLI -- not a result. Writing it would
            # be worse than losing it: the resume check above skips any cell
            # whose file exists, so a rate-limit burst would silently become 28
            # permanently-empty cells that later read as "the agent gave up".
            # Observed 2026-08-16: a five-hour limit hit mid-run and every
            # subsequent cell returned in ~1.2s with turns=1 and cost=0.
            if not rec.get("cost_usd") and (rec.get("turns") or 0) <= 1:
                print(f"      !! no work done (turns={rec.get('turns')}, "
                      f"cost={rec.get('cost_usd')}, wall={rec.get('wall_s')}s) — "
                      f"NOT recorded, so a resume retries it. Rate limit?", flush=True)
                continue
            if arm.startswith("prism"):
                rec["prism_provenance"] = prov
            json.dump(rec, open(recpath, "w"))
            print(f"      turns={rec['turns']} fresh_in={rec['fresh_input_tokens']} "
                  f"cache={rec['cache_read_tokens']} out={rec['output_tokens']} "
                  f"${rec['cost_usd']} empty={rec['empty_patch']} prism_used={rec['prism_used']}",
                  flush=True)

    # Rebuild predictions.jsonl from all present metric JSONs (kill-safe).
    metrics = {a: [] for a in args.arms}
    for arm in args.arms:
        with open(outdir / f"{arm}.predictions.jsonl", "w") as pf:
            for task in tasks:
                rp = outdir / f"{task['instance_id']}.{arm}.json"
                if not rp.exists():
                    continue
                rec = json.load(open(rp))
                metrics[arm].append(rec)
                pf.write(json.dumps({
                    "instance_id": rec["instance_id"],
                    "model_name_or_path": f"prism-ab-{arm}",
                    "model_patch": rec["model_patch"],
                }) + "\n")

    print("\n" + "=" * 74)
    print(f"{'arm':10} {'n':>3} {'nonempty':>9} {'mean_turns':>11} "
          f"{'mean_fresh':>11} {'mean_out':>9} {'mean_$':>8} {'prism%':>7}")
    for arm in args.arms:
        m = [r for r in metrics[arm] if not r["timed_out"]]
        if not m:
            continue
        ne = sum(1 for r in m if not r["empty_patch"])
        mt = sum(r["turns"] or 0 for r in m) / len(m)
        mf = sum(r["fresh_input_tokens"] for r in m) / len(m)
        mo = sum(r["output_tokens"] for r in m) / len(m)
        mc = sum(r["cost_usd"] or 0 for r in m) / len(m)
        pu = 100 * sum(1 for r in m if r["prism_used"]) / len(m)
        print(f"{arm:10} {len(m):>3} {ne:>9} {mt:>11.1f} {mf:>11.0f} {mo:>9.0f} {mc:>8.3f} {pu:>6.0f}%")
    print("\nNext: score correctness with the SWE-bench Docker harness on each")
    print("arm's predictions.jsonl (FAIL_TO_PASS/PASS_TO_PASS). Efficiency is only")
    print("comparable at EQUAL resolve-rate — report resolve-rate FIRST.")


if __name__ == "__main__":
    main()
