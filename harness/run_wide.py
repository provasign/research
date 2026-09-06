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
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import ab_endtoend_arms as arms
import usage_account
import wide_score

# ab_endtoend_arms.py points the prism MCP config at ~/bin/prism, which was
# found 2026-08-31 to be a stale v0.55.10 build — missing every fix shipped
# this session (context cap, prism_lookup routing, prism_query residency).
# "The same steering/preload/schema as if prism was installed" means the
# actual released binary: /opt/homebrew/bin/prism (brew, kept current all
# session via `brew upgrade`).
#
# 2026-09-05: brew tap has not refreshed past v0.69.2 yet (self-refreshes
# daily), but v0.70.0 is tagged+pushed. Built straight from the pushed tag
# (clean clone, not this session's working tree) so the arm exercises
# exactly what was released, not uncommitted state.
#
# Moved out of /tmp 2026-09-05 (macOS purges it; the binary's sha is in each
# cell's provenance so identity does not depend on the path).
_REAL_PRISM = str(Path.home() / ".cache/prism-research/bin/prism-v0.70.0")


def _use_prism(binary: str) -> None:
    """Point the prism_plus arm at one specific binary (--prism). The cell's
    provenance records its sha, so a candidate run and the shipped-tag run
    are told apart by the record, not by the tag string alone.

    The config file is named by the binary's sha, NOT the shared
    /tmp/ab-endtoend/prism.json: every runner on this machine used to write
    that one path at import time, so two concurrent runs silently pointed
    each other's later cells at the wrong binary (2026-09-05: a v0.70.0
    probe and another session's v0.71 bed overlapped for ~15 minutes)."""
    global _REAL_PRISM
    _REAL_PRISM = str(Path(binary).expanduser().resolve())
    arms.CFG_DIR.mkdir(exist_ok=True)
    sha = hashlib.sha1(Path(_REAL_PRISM).read_bytes()).hexdigest()[:10]
    cfg = arms.CFG_DIR / f"prism-{sha}.json"
    cfg.write_text(json.dumps({"mcpServers": {"prism": {
        "type": "stdio", "command": _REAL_PRISM, "args": ["mcp"]}}}))
    if "prism_plus" in arms.ARMS:
        arms.ARMS["prism_plus"]["mcp"] = str(cfg)

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
    "mcp": None,  # set by _use_prism
}
arms.ARMS["baseline"] = {
    **arms.ARMS["baseline"],
    "allowed": _strip_network(arms.ARMS["baseline"]["allowed"]),
}
_use_prism(_REAL_PRISM)


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


def score(task: dict, wt: Path, diff_text: str) -> dict:
    """Legacy file-touched metrics (kept for continuity with earlier tags)
    PLUS the strict site-identity metrics from wide_score — `site_recall`
    is the headline from 2026-09-05 on. The legacy `file_recall` credits a
    file the agent touched anywhere; `symbol_recall` credits a name that
    appears anywhere in the diff text, context lines included."""
    touched = set(agent_diff_files(wt))
    gt = set(task["gt_files"])
    hit = gt & touched
    syms = task.get("gt_symbols") or []
    sym_hit = [s for s in syms if s in diff_text]
    out = {
        "file_recall": round(len(hit) / len(gt), 3) if gt else None,
        "files_found": len(hit),
        "files_expected": len(gt),
        "missed_files": sorted(gt - touched),
        "extra_files": len(touched - gt),
        "symbol_recall": round(len(sym_hit) / len(syms), 3) if syms else None,
        "symbols_missed": [s for s in syms if s not in sym_hit],
    }
    out.update(wide_score.score_diff(task, diff_text))
    return out


def _sha(path_or_text) -> str:
    data = (Path(path_or_text).read_bytes() if isinstance(path_or_text, Path)
            else path_or_text.encode())
    return hashlib.sha1(data).hexdigest()[:10]


def provenance(task: dict, arm: str, model: str) -> dict:
    """Everything a later reader needs to know what was measured: binary,
    steering, corpus commit, CLI version, model — pinned together."""
    p = {"model": model, "claude_version": usage_account.claude_version(),
         "corpus_commit": task["base_commit"], "gold_commit": task["gold_commit"]}
    if arm.startswith("prism"):
        if not Path(_REAL_PRISM).exists():
            raise RuntimeError(f"prism binary missing: {_REAL_PRISM}")
        p["prism_binary"] = _REAL_PRISM
        p["prism_sha"] = _sha(Path(_REAL_PRISM))
        p["steering_sha"] = _sha(_real_shipped_steering())
    return p


def build_check(task: dict, wt: Path) -> str:
    if task["project"] in ("grove", "prism"):
        r = subprocess.run(["go", "build", "./..."], cwd=wt,
                           capture_output=True, text=True, timeout=600)
        return "pass" if r.returncode == 0 else "fail"
    return "skipped"


def tool_trace(wt: Path, session_id: str | None = None) -> dict:
    """Per-tool call counts for this cell, mined from the CLI's own
    session transcript. Without this the previous run's headline result
    (prism_plus arm, zero prism calls, discovered only by hand-reading a
    raw transcript) would have shipped unnoticed again.

    With a session_id (recorded since 2026-09-05) the transcript is found
    exactly; the mtime-glob below is the fallback for older cells."""
    if session_id:
        t = usage_account.transcript_usage(session_id)
        if "tool_calls" in t:
            return t["tool_calls"]
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
                 "project": task["project"], "tag": tag,
                 "provenance": provenance(task, arm, model)}
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
            rec["is_error"] = bool(j.get("is_error"))
            rec["result_tail"] = str(j.get("result") or "")[-300:]
            rec["usage"] = usage_account.cli_usage(j)
        except Exception:
            rec["agent_error"] = (r.stderr or r.stdout)[-250:]
        if rec.get("is_error") or rec.get("agent_error") or not rec.get("cost_usd"):
            # v070sample 2026-09-05: 10 cells came back in ~1s with
            # num_turns=1 cost=0 (a transient API-side error result) and
            # were cached as recall=0. A cell the agent never ran is not
            # a measurement — raise so main() prints ERROR and caches
            # nothing, and the next run retries it.
            raise RuntimeError("agent did not run: " + (rec.get("agent_error")
                               or rec.get("result_tail") or "cost=0"))
        sid = (rec.get("usage") or {}).get("session_id")
        rec["tool_trace"] = tool_trace(wt, sid)
        rec["transcript_usage"] = usage_account.transcript_usage(sid)
        # Full diff, never truncated: the 20k cap (dropped 2026-09-05) cut
        # 10/16 v070sample cells mid-file and made a strict rescore
        # impossible. main() moves it to a .diff sidecar next to the record.
        diff_text = sh("git", "-C", str(wt), "diff")
        rec.update(score(task, wt, diff_text))
        rec["build"] = build_check(task, wt)
        rec["diff"] = diff_text
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
    ap.add_argument("--prism", default=_REAL_PRISM,
                    help="prism binary for the prism_plus arm (sha recorded in provenance)")
    args = ap.parse_args()
    _use_prism(args.prism)

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
            out.with_suffix(".diff").write_text(rec.pop("diff"))
            out.write_text(json.dumps(rec, indent=1))
            tt = rec.get("tool_trace") or {}
            prism_calls = sum(v for k, v in tt.items() if "prism" in k.lower())
            print(f"{rec['task']:26} {arm:12} site={rec.get('site_recall')} "
                  f"({rec.get('sites_found')}/{rec.get('sites_expected')}) "
                  f"file={rec.get('file_recall')} "
                  f"sym={rec.get('symbol_recall_strict')} extra={rec.get('extra_files')} "
                  f"build={rec.get('build')} turns={rec.get('turns')} "
                  f"cost=${rec.get('cost_usd')} prism_calls={prism_calls}", flush=True)


if __name__ == "__main__":
    main()
