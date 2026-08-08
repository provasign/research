#!/usr/bin/env python3
"""ledger A/B: does a code graph help an agent build a MID-SIZE typed service?

One cell = one continuous Sonnet session walking 13 work items in a fresh repo,
building a ~35-class TypeScript billing service and then changing it five times.

Why this exists, and what it fixes about the previous (tickr) study:

  tickr tied because the baseline never failed — the scorer saturated and the
  only measurable quantity left was overhead. In a TYPED language the trap is
  worse: on a signature change the compiler already computes the impact set for
  free, so both arms converge on correct no matter how they found the sites.

  So the turns split deliberately. On the COMPILER-CAUGHT turns (t06/t09/t10)
  tsc flags every miss, and what is measurable is the cost of getting there —
  which is where TypeScript's method-name collisions bite (`apply` on
  PricingRule AND LedgerPolicy, `validate` on three interfaces). On the SILENT
  turns (t07/t08) the change compiles clean and the existing tests still pass,
  so a missed site is invisible; completeness can only be established by
  analysis. That is the one regime where a graph can show a CORRECTNESS effect.

Grading (ledger_harness/graders.py) is a 341-test hidden suite parameterized PER
IMPLEMENTATION, so the failure count in a turn's family IS the missed-site
count, plus tsc as an independent compiler oracle. Nothing runs through Prism.

  python3 ledger_ab.py --trials 2
  python3 ledger_ab.py --report
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ledger_harness import graders                    # noqa: E402
from ledger_harness.arms import ARMS                  # noqa: E402
from ledger_harness.tasks import TURNS, TAIL          # noqa: E402

ROOT = Path.home() / "ledger-ab"
TEMPLATE = ROOT / "template"
REPOS = ROOT / "repos"
SNAPS = ROOT / "snapshots"
OUT = ROOT / "results"
for d in (REPOS, SNAPS, OUT):
    d.mkdir(parents=True, exist_ok=True)

SPEC_SRC = Path(__file__).parent / "ledger_harness" / "SPEC.md"
PRISM = str(Path.home() / "bin" / "prism")
MODEL = "sonnet"
TURN_TIMEOUT = 3600

RATE_HINTS = ("rate limit", "usage limit", "429", "too many requests",
              "overloaded", "please try again later", "quota")


class RateLimited(Exception):
    pass


def _cell(arm: str, trial: int) -> str:
    return f"{arm}-t{trial}"


def _rec_path(arm: str, trial: int, turn_id: str) -> Path:
    return OUT / f"{_cell(arm, trial)}--{turn_id}.json"


GITIGNORE = "node_modules/\n.grove/\n.prism/\nprism.yaml\n.conformance/\n"


def fresh_repo(arm: str, trial: int) -> Path:
    repo = REPOS / _cell(arm, trial)
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for f in ("package.json", "tsconfig.json"):
        shutil.copy2(TEMPLATE / f, repo / f)
    # symlinks=True is REQUIRED: node_modules/.bin/tsc is a symlink, and a
    # dereferencing copy produces a tsc that cannot find its own lib and exits
    # non-zero — which would be scored as a type error that never happened.
    shutil.copytree(TEMPLATE / "node_modules", repo / "node_modules",
                    symlinks=True)
    (repo / ".gitignore").write_text(GITIGNORE)
    (repo / "SPEC.md").write_text(SPEC_SRC.read_text())
    (repo / "CLAUDE.md").write_text(ARMS[arm]["claude_md"])
    return repo


def snapshot(repo: Path, arm: str, trial: int, turn_id: str) -> Path:
    dst = SNAPS / f"{_cell(arm, trial)}--{turn_id}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(repo, dst,
                    ignore=shutil.ignore_patterns(*graders.TOOL_ARTIFACTS))
    return dst


def _tool_counts(sid: str) -> dict:
    hits = list((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl"))
    if not hits:
        return {}
    counts: dict[str, int] = {}
    for line in hits[0].read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        msg = ev.get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "tool_use":
                    n = blk.get("name", "?")
                    counts[n] = counts.get(n, 0) + 1
    return counts


def run_turn(arm: str, repo: Path, sid: str, first: bool, prompt: str) -> dict:
    spec = ARMS[arm]
    cmd = ["claude", "-p", prompt, "--model", MODEL, "--effort", "medium",
           "--output-format", "json", "--permission-mode", "acceptEdits",
           "--setting-sources", "project",
           "--strict-mcp-config", "--mcp-config", spec["mcp"],
           "--allowedTools", *spec["allowed"],
           # No subagents: a Task subagent gets its own context and may not
           # inherit the arm's MCP tools, which would silently degrade the
           # prism arm only — an asymmetry invisible in the results.
           "--disallowedTools", "Task", "Agent", "ScheduleWakeup"]
    cmd += ["--session-id", sid] if first else ["--resume", sid]
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                       timeout=TURN_TIMEOUT)
    wall = round(time.monotonic() - t0, 1)
    blob = (r.stdout + r.stderr).lower()
    if r.returncode != 0 and any(h in blob for h in RATE_HINTS):
        raise RateLimited(blob[-300:])
    rec: dict = {"wall_s": wall, "rc": r.returncode}
    try:
        j = json.loads(r.stdout)
    except Exception:
        if any(h in blob for h in RATE_HINTS):
            raise RateLimited(blob[-300:])
        rec["agent_error"] = (r.stderr or r.stdout)[-400:]
        return rec
    u = j.get("usage") or {}
    rec.update(
        num_turns=j.get("num_turns"), cost_usd=j.get("total_cost_usd"),
        is_error=j.get("is_error"), stop_reason=j.get("stop_reason"),
        permission_denials=j.get("permission_denials") or [],
        input_tokens=u.get("input_tokens", 0),
        output_tokens=u.get("output_tokens", 0),
        cache_creation_tokens=u.get("cache_creation_input_tokens", 0),
        cache_read_tokens=u.get("cache_read_input_tokens", 0),
        final_message=(j.get("result") or "")[-1200:],
    )
    return rec


def index_prism(repo: Path) -> float:
    t0 = time.monotonic()
    subprocess.run([PRISM, "index", str(repo)], capture_output=True, text=True,
                   timeout=900)
    return round(time.monotonic() - t0, 2)


def run_cell(arm: str, trial: int, resume: bool = True) -> None:
    done = [t for t in TURNS if _rec_path(arm, trial, t["id"]).exists()]
    if resume and len(done) == len(TURNS):
        print(f"[skip] {_cell(arm, trial)} complete")
        return
    repo = REPOS / _cell(arm, trial)
    sid_file = OUT / f"{_cell(arm, trial)}.sid"
    if not resume or not done or not repo.exists():
        for t in TURNS:
            _rec_path(arm, trial, t["id"]).unlink(missing_ok=True)
        done = []
        repo = fresh_repo(arm, trial)
        sid = str(uuid.uuid4())
        sid_file.write_text(sid)
    else:
        sid = sid_file.read_text().strip()

    print(f"\n=== {_cell(arm, trial)} (session {sid[:8]}, from turn "
          f"{len(done)+1}/{len(TURNS)}) ===", flush=True)

    for i, turn in enumerate(TURNS, start=1):
        rp = _rec_path(arm, trial, turn["id"])
        if rp.exists():
            continue
        idx_s = index_prism(repo) if ARMS[arm]["index"] else 0.0
        print(f"  [{_cell(arm, trial)}] {i}/{len(TURNS)} {turn['id']} ...",
              end="", flush=True)
        rec = run_turn(arm, repo, sid, first=(i == 1),
                       prompt=turn["prompt"] + TAIL)
        rec.update(arm=arm, trial=trial, turn=i, turn_id=turn["id"],
                   kind=turn["kind"], index_s=idx_s, session_id=sid)
        snap = snapshot(repo, arm, trial, turn["id"])
        t0 = time.monotonic()
        rec["grade"] = graders.grade(repo, snap, i)   # typecheck on LIVE repo
        rec["grade_s"] = round(time.monotonic() - t0, 1)
        rec["tools"] = _tool_counts(sid)
        rp.write_text(json.dumps(rec, indent=2))
        g = rec["grade"]
        tcs = "clean" if g["typecheck"].get("clean") else \
              ("N/A" if not g["typecheck"].get("ran") else
               f"{g['typecheck']['error_count']}err")
        print(f" {rec['wall_s']}s ${rec.get('cost_usd', 0):.2f} "
              f"conf {g['conformance']['score']:.3f} "
              f"silent {g['silent_misses']} tsc {tcs} "
              f"own {'green' if g['own_tests'].get('green') else 'RED'}",
              flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--arms", default="base,prism")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        import ledger_harness.report as rep
        rep.main(OUT)
        return 0
    paused = ROOT / "PAUSED.json"
    paused.unlink(missing_ok=True)
    for trial in range(1, a.trials + 1):
        for arm in a.arms.split(","):
            try:
                run_cell(arm, trial, resume=not a.fresh)
            except RateLimited as e:
                paused.write_text(json.dumps(
                    {"at": time.time(), "cell": _cell(arm, trial),
                     "detail": str(e)[:400]}, indent=2))
                print(f"\n[PAUSED] rate limited on {_cell(arm, trial)}")
                return 42
    print("\nAll cells complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
