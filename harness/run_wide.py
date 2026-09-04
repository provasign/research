#!/usr/bin/env python3
"""Run the mandated-wide bed: completeness-scored, sonnet-only, prism_plus
vs baseline.

REBUILT 2026-08-31 after the first version was invalidated: shared-history
worktrees let agents `git log --all` / `cherry-pick` the gold commit, and
WebFetch/curl reached the real GitHub PR. Both holes are closed here using
the pattern already proven in swebench_ab.py (sanitize_worktree,
--local --no-checkout clone + full ref-strip + HEAD verification), plus
GIT_ALLOW_PROTOCOL=file and no WebFetch/WebSearch/curl/wget/gh in either
arm's allowlist. tool_trace is recorded per cell so "did this arm actually
use its tool" is visible in the result, not something you have to dig a
transcript to find.

One cell = (task, arm). The agent starts at the commit's PARENT and is told
what changed upstream, in the words the commit itself used. Scoring:

  file_recall    fraction of the real commit's MODIFIED/DELETED source
                 files also touched (additions are unscored — you cannot
                 retrieve a file that does not exist yet)
  symbol_recall  fraction of relocated/removed symbols the diff mentions
  extra_files    files touched that the real commit did not (noise)
  build          compile check where cheaply available (go build)
  tool_trace     per-tool call counts, so arm compliance is auditable
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import ab_endtoend_arms as arms

# ab_endtoend_arms.py points the prism MCP config at ~/bin/prism, which was
# found 2026-08-31 to be a stale v0.55.10 build — missing every fix shipped
# this session (context cap, prism_lookup routing, prism_query residency).
# "The same steering/preload/schema as if prism was installed" means the
# actual released binary: /opt/homebrew/bin/prism (brew, kept current all
# session via `brew upgrade`).
_REAL_PRISM = "/opt/homebrew/bin/prism"
arms.CFG_DIR.mkdir(exist_ok=True)
(arms.CFG_DIR / "prism.json").write_text(json.dumps({"mcpServers": {"prism": {
    "type": "stdio", "command": _REAL_PRISM, "args": ["mcp"]}}}))

OUT = Path("runs/wide")
OUT.mkdir(parents=True, exist_ok=True)

TAIL = (
    "\n\nUpdate EVERY affected file in this repository so the project builds "
    "again. The change is deliberately wide — do not stop at the first file. "
    "Test files are in scope: if a moved or renamed API is referenced in a "
    "test, that reference must be updated too. Do not change behaviour, only "
    "the sites the upstream change forces. Then stop.\n\n"
    "You have no network access and no git history beyond this commit — "
    "the answer is not reachable by searching git log, GitHub, or any URL. "
    "Find it by reading and searching the code in front of you."
)

# No WebFetch/WebSearch, no gh/curl/wget in EITHER arm — the actual PR
# fixing this exact change is one API call away otherwise, and today's
# audit found both arms had reached it.
_NETWORK_TOOLS = {"WebFetch", "WebSearch"}
_NETWORK_BASH = ("curl", "wget", "gh ")


def _strip_network(allowed: list[str]) -> list[str]:
    return [a for a in allowed if a not in _NETWORK_TOOLS
            and not any(a.startswith(f"Bash({b}") for b in _NETWORK_BASH)]


def _real_shipped_steering() -> str:
    """The literal steeringInstructions block from prism's own source —
    extracted programmatically, not hand-transcribed. A copy risks silent
    drift (measured 2026-08-31: a first hand-written attempt injected
    framing, changed the bullet numbering, and dropped a sentence, none
    of it caught until asked to verify). "The same steering as if prism
    was installed" means literally this string, byte for byte, re-read
    from source every run so it can never go stale relative to what
    `prism init` actually writes.
    """
    src = Path.home() / "Projects/provasign/prism/internal/cli/commands.go"
    text = src.read_text()
    i = text.index("const steeringInstructions")
    j = text.index("<!-- prism:end -->", i)
    rhs = text[i:j].split("=", 1)[1].strip()
    # Go concatenation of `literal` + "escaped" + `literal` + ... segments,
    # decoded and reassembled in source order — mechanical de-escaping,
    # not rewording. First attempt split on the 2nd backtick and silently
    # dropped the opening sentence; this walks every segment instead.
    parts = re.findall(r"`([^`]*)`|\"((?:[^\"\\]|\\.)*)\"", rhs)
    block = "".join(raw if raw else esc.encode().decode("unicode_escape")
                    for raw, esc in parts)
    # Stop before the CLI-only usage examples — not relevant to an
    # MCP-tool-using agent, and the source's own closing marker sits past
    # a stray quote that this decoder would otherwise run past.
    return block.split("Bash-only")[0].strip()


arms.ARMS["prism_plus"] = {
    "guidance": (
        "CONTEXT TOOL: the Prism MCP server, alongside your normal tools "
        "(grep/find/ls remain available for anything below does not cover).\n\n"
        + _real_shipped_steering()),
    "allowed": _strip_network(arms.ARMS["baseline"]["allowed"]) + ["mcp__prism"],
    "mcp": arms.ARMS["prism_native"]["mcp"],
}
arms.ARMS["baseline"] = {
    **arms.ARMS["baseline"],
    "allowed": _strip_network(arms.ARMS["baseline"]["allowed"]),
}


def sh(*a, cwd=None, check=False) -> str:
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(a)}: {r.stderr[-300:]}")
    return r.stdout


def isolated_worktree(task: dict) -> tuple[str, Path]:
    """git archive the tree at base_commit, then `git init` fresh — zero
    historical objects ever exist in the result, by construction.

    Ref-stripping a --local clone was tried first and FAILED: refs no
    longer point at the gold commit, but the object is still physically
    in the packfile, and a completely ordinary command --
    `git cat-file --batch-all-objects --batch-check` -- enumerates all
    ~15k objects with no SHA needed in advance (measured 2026-08-31).
    gc-based pruning has grace periods and reflog edge cases; not
    reachable at all is the only guarantee that holds regardless.
    """
    repo = task["repo_path"]
    wt = Path(tempfile.mkdtemp(prefix="wide-"))
    archive = wt.with_suffix(".tar")
    sh("git", "-C", repo, "archive", "--format=tar", "-o", str(archive),
       task["base_commit"], check=True)
    wt.mkdir(exist_ok=True)
    sh("tar", "-xf", str(archive), "-C", str(wt), check=True)
    archive.unlink()
    sh("git", "-C", str(wt), "init", "--quiet", check=True)
    sh("git", "-C", str(wt), "-c", "user.email=w@w", "-c", "user.name=w",
       "add", "-A", check=True)
    sh("git", "-C", str(wt), "-c", "user.email=w@w", "-c", "user.name=w",
       "commit", "--quiet", "-m", "base", check=True)
    # The real sanity check: not "few objects" (a real tree legitimately has
    # one blob/tree per file/dir) but that the SPECIFIC gold commit is
    # absent, and there is exactly one commit object (this fresh one).
    objs = sh("git", "-C", str(wt), "cat-file", "--batch-all-objects",
              "--batch-check").splitlines()
    gold_short = task["gold_commit"][:10]
    if any(gold_short in o for o in objs):
        shutil.rmtree(wt, ignore_errors=True)
        raise RuntimeError(f"isolation FAILED: gold commit {gold_short} present in object store")
    n_commits = sum(1 for o in objs if " commit " in o)
    if n_commits != 1:
        shutil.rmtree(wt, ignore_errors=True)
        raise RuntimeError(f"isolation sanity check failed: {n_commits} commit objects, want 1")
    return repo, wt


def agent_diff_files(wt: Path) -> list[str]:
    """MODIFIED or DELETED files only — never created ones (see scoring
    docstring: ground truth excludes additions, so this side of the ratio
    must exclude them too, or one arm gets credit for authoring, not
    finding)."""
    files = []
    for line in sh("git", "-C", str(wt), "status", "--porcelain").splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        if code.strip() in {"??", "A"}:
            continue
        if path:
            files.append(path)
    return files


def score(task: dict, wt: Path) -> dict:
    touched = set(agent_diff_files(wt))
    gt = set(task["gt_files"])
    hit = gt & touched
    diff_text = sh("git", "-C", str(wt), "diff")
    syms = task.get("gt_symbols") or []
    sym_hit = [s for s in syms if s in diff_text]
    return {
        "file_recall": round(len(hit) / len(gt), 3) if gt else None,
        "files_found": len(hit),
        "files_expected": len(gt),
        "missed_files": sorted(gt - touched),
        "extra_files": len(touched - gt),
        "symbol_recall": round(len(sym_hit) / len(syms), 3) if syms else None,
        "symbols_missed": [s for s in syms if s not in sym_hit],
    }


def build_check(task: dict, wt: Path) -> str:
    if task["project"] in ("grove", "prism"):
        r = subprocess.run(["go", "build", "./..."], cwd=wt,
                           capture_output=True, text=True, timeout=600)
        return "pass" if r.returncode == 0 else "fail"
    return "skipped"


def tool_trace(wt: Path) -> dict:
    """Per-tool call counts for this cell, mined from the CLI's own
    session transcript. Without this the previous run's headline result
    (prism_plus arm, zero prism calls, discovered only by hand-reading a
    raw transcript) would have shipped unnoticed again."""
    base = wt.name.replace("_", "-")
    candidates = [str(wt), str(wt.resolve()), "/private" + str(wt)]
    home_projects = Path.home() / ".claude" / "projects"
    hits = sorted(home_projects.glob(f"*{base}"), key=lambda d: d.stat().st_mtime,
                  reverse=True)
    pdir = hits[0] if hits else None
    if pdir is None:
        for _ in range(10):
            for c in candidates:
                d = home_projects / c.replace("/", "-")
                if d.exists() and any(d.glob("*.jsonl")):
                    pdir = d
                    break
            if pdir:
                break
            time.sleep(1)
    if pdir is None:
        return {"_trace_unavailable": 1}
    counts: dict = {}
    for f in pdir.glob("*.jsonl"):
        for line in f.open(errors="ignore"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("type") != "assistant":
                continue
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    counts[c["name"]] = counts.get(c["name"], 0) + 1
    return counts


# --allowedTools does NOT restrict in headless -p mode (verified directly
# 2026-08-30: a tool absent from --allowedTools still ran, no denial, no
# error). --disallowedTools is the flag that actually removes a tool from
# the agent's list. Network tools go here, on BOTH arms, as real
# enforcement rather than the decorative allowlist. Agent/Task is here too:
# measured 2026-08-31 — a probe cell spawned two subagents whose internal
# tool calls carry NO parent_tool_use_id in this project's transcript, so
# they are invisible to tool_trace and to any leak audit. Not "probably
# fine" — genuinely unauditable, and turns/cost accounting undercounts
# whatever they did. No legitimate reason a completeness cell needs one.
_DISALLOW_NETWORK = ["WebFetch", "WebSearch", "Bash(curl:*)", "Bash(wget:*)",
                     "Bash(gh:*)", "Agent", "Task"]


def run_cell(task: dict, arm: str, model: str, tag: str) -> dict:
    spec = arms.ARMS[arm]
    prompt = (spec["guidance"] + "\n\nUPSTREAM CHANGE:\n" +
              task["subject"] + "\n" + (task.get("body") or "") + TAIL)
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--strict-mcp-config",
           "--allowedTools", *spec["allowed"],
           "--disallowedTools", *_DISALLOW_NETWORK]
    if spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"]]

    repo, wt = isolated_worktree(task)
    rec: dict = {"task": task["instance_id"], "arm": arm, "model": model,
                 "project": task["project"]}
    try:
        if arm.startswith("prism"):
            # Explicit path, not the bare "prism" command: PATH resolved
            # that to ~/bin/prism (a stale v0.55.10 build) on this machine,
            # which would have indexed with a different engine than the
            # one actually serving the agent's MCP calls.
            subprocess.run([_REAL_PRISM, "index", str(wt)], capture_output=True,
                           text=True, timeout=600)
        env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file"}
        t0 = time.monotonic()
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True,
                           timeout=2400, env=env)
        rec["wall_s"] = round(time.monotonic() - t0, 1)
        try:
            j = json.loads(r.stdout)
            rec["turns"] = j.get("num_turns")
            rec["cost_usd"] = j.get("total_cost_usd")
        except Exception:
            rec["agent_error"] = (r.stderr or r.stdout)[-250:]
        rec["tool_trace"] = tool_trace(wt)
        rec.update(score(task, wt))
        rec["build"] = build_check(task, wt)
        rec["diff"] = sh("git", "-C", str(wt), "diff")[:20000]
    finally:
        shutil.rmtree(wt, ignore_errors=True)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="tasks-wide")
    ap.add_argument("--arms", default="baseline,prism_plus")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--tag", default="w2")
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    files = sorted(Path(args.tasks).glob("*.json"))
    if args.only:
        files = [f for f in files if args.only in f.name]
    if args.limit:
        files = files[: args.limit]

    for tf in files:
        task = json.loads(tf.read_text())
        for arm in args.arms.split(","):
            out = OUT / f"{task['instance_id']}.{args.model}.{arm}.{args.tag}.json"
            if out.exists():
                rec = json.loads(out.read_text())
                tt = rec.get("tool_trace") or {}
                prism_calls = sum(v for k, v in tt.items() if "prism" in k.lower())
                print(f"(cached) {rec['task']:26} {arm:12} "
                      f"recall={rec.get('file_recall')} prism_calls={prism_calls}")
                continue
            try:
                rec = run_cell(task, arm, args.model, args.tag)
            except Exception as e:
                print(f"{task['instance_id']:26} {arm:12} ERROR {str(e)[:150]}")
                continue
            out.write_text(json.dumps(rec, indent=1))
            tt = rec.get("tool_trace") or {}
            prism_calls = sum(v for k, v in tt.items() if "prism" in k.lower())
            print(f"{rec['task']:26} {arm:12} recall={rec.get('file_recall')} "
                  f"({rec.get('files_found')}/{rec.get('files_expected')}) "
                  f"sym={rec.get('symbol_recall')} extra={rec.get('extra_files')} "
                  f"build={rec.get('build')} turns={rec.get('turns')} "
                  f"cost=${rec.get('cost_usd')} prism_calls={prism_calls}", flush=True)


if __name__ == "__main__":
    main()
