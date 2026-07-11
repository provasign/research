"""A/B: Claude Code CLI (Sonnet, subscription) vs mason (ollama:qwen3-coder:30b, $0).

Same natural-language prompts, fresh gin scratch tree per (task, arm), objective
oracles run by THIS script after the agent exits (never trusting agent claims).
Idempotent: per-run JSON results; completed runs are skipped on re-invocation.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
GIN_SRC = HOME / "gvg-corpus" / "gin"
WORK = Path("/tmp/ab-mason-claude")
RESULTS = WORK / "results"
TIMEOUT_S = 15 * 60

TASKS = {
    "rename": (
        "Rename the Status method of the ResponseWriter interface to StatusCode. "
        "Update every implementation and caller so the project still builds. "
        "Verify with 'go build ./...'."
    ),
    "feature": (
        "Add a new method IsSuccess() bool to the ResponseWriter interface in "
        "response_writer.go that reports whether the HTTP status code is in "
        "[200, 300). Implement it on the concrete writer type and add a unit "
        "test for it in response_writer_test.go. Verify your work by running "
        "the response writer tests."
    ),
    "comprehend": (
        "Which types in this repository implement the ResponseWriter interface "
        "declared in response_writer.go? List each type and where it is defined."
    ),
}


def sh(*args, cwd=None, timeout=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def fresh_tree(name: str) -> Path:
    d = WORK / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(GIN_SRC, d)
    shutil.rmtree(d / ".grove", ignore_errors=True)
    # a clean git baseline so oracles can diff what the agent did
    sh("git", "-C", str(d), "add", "-A")
    sh("git", "-C", str(d), "commit", "-qm", "ab-baseline", "--no-verify")
    return d


# ---------------------------------------------------------------------------
# Oracles — run by the harness, after the agent exits.
# ---------------------------------------------------------------------------

def oracle_rename(d: Path) -> tuple[bool, str]:
    rw = (d / "response_writer.go").read_text()
    if not re.search(r"\bStatusCode\(\) int", rw):
        return False, "interface/impl not renamed to StatusCode"
    if re.search(r"^\s*Status\(\) int", rw, re.M):
        return False, "old Status() still declared"
    b = sh("go", "build", "./...", cwd=d, timeout=300)
    if b.returncode != 0:
        return False, "go build failed: " + b.stderr.strip().splitlines()[-1][:120]
    return True, "renamed + builds"


def oracle_feature(d: Path) -> tuple[bool, str]:
    rw = (d / "response_writer.go").read_text()
    if "IsSuccess() bool" not in rw:
        return False, "IsSuccess not declared in response_writer.go"
    tests = (d / "response_writer_test.go").read_text()
    if "IsSuccess" not in tests:
        return False, "no test references IsSuccess"
    b = sh("go", "build", "./...", cwd=d, timeout=300)
    if b.returncode != 0:
        return False, "go build failed"
    t = sh("go", "test", "-run", "ResponseWriter|IsSuccess", ".", cwd=d, timeout=600)
    if t.returncode != 0:
        return False, "targeted tests failed: " + (t.stdout + t.stderr)[-120:]
    return True, "declared + implemented + tested"


def oracle_comprehend(_: Path, answer: str = "") -> tuple[bool, str]:
    # Engine truth (grove, closed set): the one project implementor is the
    # unexported responseWriter in response_writer.go.
    if "responseWriter" in answer and "response_writer.go" in answer:
        return True, "found responseWriter @ response_writer.go"
    return False, "missed the concrete implementor responseWriter"


ORACLES = {"rename": oracle_rename, "feature": oracle_feature, "comprehend": oracle_comprehend}


# ---------------------------------------------------------------------------
# Arms
# ---------------------------------------------------------------------------

def run_claude(prompt: str, d: Path) -> dict:
    cmd = ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json",
           "--strict-mcp-config", "--dangerously-skip-permissions"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(d), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=TIMEOUT_S)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        out, err = proc.communicate()
        timed_out = True
    wall = round(time.time() - t0, 1)
    cost = None
    answer = ""
    turns = None
    try:
        j = json.loads(out)
        cost = j.get("total_cost_usd")
        answer = j.get("result") or ""
        turns = j.get("num_turns")
    except (json.JSONDecodeError, TypeError):
        answer = out[-2000:]
    return {"arm": "claude-sonnet", "wall_s": wall, "cost_usd": cost,
            "turns": turns, "timed_out": timed_out, "answer": answer,
            "stderr_tail": err[-300:]}


def run_mason(prompt: str, d: Path) -> dict:
    cmd = [str(HOME / "bin" / "mason"), "--dir", str(d), "--yes",
           "--model", "ollama:qwen3-coder:30b", prompt]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=TIMEOUT_S)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        out, _ = proc.communicate()
        timed_out = True
    wall = round(time.time() - t0, 1)
    m = re.search(r"usage: (\d+) in / (\d+) out", out)
    tok_in, tok_out = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return {"arm": "mason-30b", "wall_s": wall, "cost_usd": 0.0,
            "tokens_in": tok_in, "tokens_out": tok_out, "timed_out": timed_out,
            "answer": out[-2500:]}


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for tname, prompt in TASKS.items():
        for arm, runner in (("claude-sonnet", run_claude), ("mason-30b", run_mason)):
            if only and only not in (tname, arm, f"{tname}:{arm}"):
                continue
            rfile = RESULTS / f"{tname}.{arm}.json"
            if rfile.exists():
                print(f"skip {tname}/{arm} (done)")
                continue
            print(f"== {tname} / {arm} ==", flush=True)
            d = fresh_tree(f"{tname}__{arm.replace(':','-')}")
            rec = runner(prompt, d)
            if tname == "comprehend":
                ok, why = ORACLES[tname](d, rec.get("answer", ""))
            else:
                ok, why = ORACLES[tname](d)
            rec.update({"task": tname, "oracle_pass": ok, "oracle_note": why})
            rfile.write_text(json.dumps(rec, indent=2))
            print(f"   pass={ok} ({why})  wall={rec['wall_s']}s  cost={rec.get('cost_usd')}",
                  flush=True)
    print("all done ->", RESULTS)


if __name__ == "__main__":
    main()
