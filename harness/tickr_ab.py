#!/usr/bin/env python3
"""tickr A/B: does Prism help an agent BUILD a project, end to end?

One cell = (arm, trial). A cell is a single CONTINUOUS Sonnet session that walks
the 9 turns of tickr_harness/tasks.py in a fresh git repo — scaffold, two features, two
refactors with real blast radius, a test-authoring turn, a behavioural bug fix,
a feature on top of the refactored code, and a cleanup pass. That is the point:
the token and time story of a code graph is a story about a LONG session, where
context accumulates and the agent has to re-find code it wrote hours ago.

The arms differ only in how the agent finds code (arms.py). Prompts, spec, model,
tool surface, and grading are identical. Grading is done by graders.py — a hidden
conformance suite plus a stdlib `ast` completeness check — so no number in this
benchmark is produced by the tool under test.

Resumable: each finished turn writes a JSON record and is skipped on restart.
On an Anthropic usage/rate limit the runner writes PAUSED.json and exits 42.

  python3 tickr_ab.py --trials 3
  python3 tickr_ab.py --report
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tickr_harness import graders                      # noqa: E402
from tickr_harness import seed as seedmod              # noqa: E402
from tickr_harness.arms import ARMS                    # noqa: E402
from tickr_harness.tasks import TURNS, TAIL            # noqa: E402

# Two conditions, same 9 turns:
#   small — the app the agent builds and nothing else (~350 LOC).
#   large — identical for turns 1-3, then the platform team's 60-module consumer
#           package lands in the repo just before the blast-radius refactor.
# The pilot showed `small` saturates: the baseline misses nothing, so the scorer
# cannot separate the arms. `large` exists to find where (if anywhere) it can.
CONDITION = "small"
ROOT = Path.home() / "tickr-ab"
REPOS = SNAPS = OUT = None  # set by set_condition()


def set_condition(cond: str) -> None:
    global CONDITION, REPOS, SNAPS, OUT
    CONDITION = cond
    sfx = "" if cond == "small" else f"-{cond}"
    REPOS = ROOT / f"repos{sfx}"
    SNAPS = ROOT / f"snapshots{sfx}"
    OUT = ROOT / f"results{sfx}"
    for d in (REPOS, SNAPS, OUT):
        d.mkdir(parents=True, exist_ok=True)


set_condition("small")

# Turn 9 tells the agent to delete unreachable code. In the large condition the
# desk package is reachable only from outside the repo, so without this it
# is a legitimate-looking 60-file deletion target — that would measure our
# framing, not the agent.
PLATFORM_KEEP = ("\n\nNote: the `desk/` package ships to customers and is "
                 "called from outside this repository. It is not dead code.")

SPEC_SRC = Path(__file__).parent / "tickr_harness" / "SPEC.md"
PRISM = str(Path.home() / "bin" / "prism")
MODEL = "sonnet"
TURN_TIMEOUT = 2400

RATE_HINTS = ("rate limit", "usage limit", "429", "too many requests",
              "overloaded", "please try again later", "quota")


class RateLimited(Exception):
    pass


def _cell(arm: str, trial: int) -> str:
    return f"{arm}-t{trial}"


def _rec_path(arm: str, trial: int, turn_id: str) -> Path:
    return OUT / f"{_cell(arm, trial)}--{turn_id}.json"


# ------------------------------------------------------------------ workspace
GITIGNORE = "__pycache__/\n*.pyc\n.pytest_cache/\n.grove/\n.prism/\nprism.yaml\n"


def fresh_repo(arm: str, trial: int) -> Path:
    repo = REPOS / _cell(arm, trial)
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(GITIGNORE)
    (repo / "SPEC.md").write_text(SPEC_SRC.read_text())
    (repo / "CLAUDE.md").write_text(ARMS[arm]["claude_md"])
    return repo


def snapshot(repo: Path, arm: str, trial: int, turn_id: str) -> Path:
    dst = SNAPS / f"{_cell(arm, trial)}--{turn_id}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(repo, dst, ignore=shutil.ignore_patterns(
        *graders.TOOL_ARTIFACTS))
    return dst


# ------------------------------------------------------------------ the agent
def _tool_counts(sid: str) -> dict:
    """Tool-use histogram for one session, read off the CLI's own transcript."""
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
        for blk in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                counts[blk.get("name", "?")] = counts.get(blk.get("name", "?"), 0) + 1
    return counts


def run_turn(arm: str, repo: Path, sid: str, first: bool, prompt: str) -> dict:
    spec = ARMS[arm]
    cmd = ["claude", "-p", prompt,
           "--model", MODEL,
           "--effort", "medium",
           "--output-format", "json",
           "--permission-mode", "acceptEdits",
           "--setting-sources", "project",
           "--strict-mcp-config", "--mcp-config", spec["mcp"],
           "--allowedTools", *spec["allowed"]]
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
    su = (j.get("modelUsage") or {})
    rec.update(
        num_turns=j.get("num_turns"),
        cost_usd=j.get("total_cost_usd"),
        duration_api_ms=j.get("duration_api_ms"),
        is_error=j.get("is_error"),
        stop_reason=j.get("stop_reason"),
        permission_denials=j.get("permission_denials") or [],
        input_tokens=u.get("input_tokens", 0),
        output_tokens=u.get("output_tokens", 0),
        cache_creation_tokens=u.get("cache_creation_input_tokens", 0),
        cache_read_tokens=u.get("cache_read_input_tokens", 0),
        model_usage={k: {kk: vv for kk, vv in v.items()
                         if kk.endswith("Tokens") or kk == "costUSD"}
                     for k, v in su.items()},
        final_message=(j.get("result") or "")[-1500:],
    )
    return rec


def index_prism(repo: Path) -> float:
    t0 = time.monotonic()
    subprocess.run([PRISM, "index", str(repo)], capture_output=True, text=True,
                   timeout=600)
    return round(time.monotonic() - t0, 2)


# ------------------------------------------------------------------ the cell
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

    print(f"\n=== {_cell(arm, trial)}  (session {sid[:8]}, resuming at turn "
          f"{len(done)+1}/{len(TURNS)}) ===")

    for i, turn in enumerate(TURNS, start=1):
        rp = _rec_path(arm, trial, turn["id"])
        if rp.exists():
            continue
        # The merge lands BEFORE the index runs, so the prism arm indexes the
        # repository as it actually is — no arm gets a stale or a privileged view.
        prompt = turn["prompt"]
        seeded = None
        if CONDITION == "large" and i == 4:
            seeded = seedmod.seed(repo)
            prompt += seedmod.MERGE_NOTE
        if CONDITION == "large" and i == 9:
            prompt += PLATFORM_KEEP
        idx_s = index_prism(repo) if ARMS[arm]["index"] else 0.0
        print(f"  [{_cell(arm, trial)}] turn {i}/{len(TURNS)} {turn['id']} ...",
              end="", flush=True)
        rec = run_turn(arm, repo, sid, first=(i == 1), prompt=prompt + TAIL)
        rec.update(arm=arm, trial=trial, turn=i, turn_id=turn["id"],
                   kind=turn["kind"], index_s=idx_s, session_id=sid,
                   condition=CONDITION, seeded=seeded)
        snap = snapshot(repo, arm, trial, turn["id"])
        t0 = time.monotonic()
        rec["grade"] = graders.grade(snap, i)
        rec["grade_s"] = round(time.monotonic() - t0, 1)
        rec["tools"] = _tool_counts(sid)
        rp.write_text(json.dumps(rec, indent=2))
        g = rec["grade"]
        print(f" {rec['wall_s']}s  ${rec.get('cost_usd', 0):.3f}  "
              f"conf {g['conformance']['score']:.2f}  broken {g['broken_sites']}"
              f"  own_tests {'green' if g['own_tests'].get('green') else 'RED'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--arms", default="base,prism")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore existing results and rerun everything")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--condition", default="small", choices=("small", "large"))
    a = ap.parse_args()
    set_condition(a.condition)

    if a.report:
        import tickr_harness.report as rep
        rep.main(OUT)
        return 0

    arms = a.arms.split(",")
    paused = ROOT / "PAUSED.json"
    paused.unlink(missing_ok=True)
    # Interleave arms within each trial so API-side drift hits both equally.
    for trial in range(1, a.trials + 1):
        for arm in arms:
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
