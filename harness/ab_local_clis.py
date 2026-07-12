"""A/B: can a LOCAL model actually do agentic coding, and does the harness matter?

Same local model (ollama qwen3-coder:30b), same natural-language prompts,
fresh gin scratch tree per (task, arm), objective oracles run by THIS script
after the agent exits — agent claims are never trusted. Products under test,
each as-shipped in its stock non-interactive mode:

  mason-30b     mason --yes            (prism graph harness baked in)
  opencode-30b  opencode run           (stock; ollama via openai-compatible)
  continue-30b  cn --auto -p           (Continue CLI; ollama provider)

Tasks and oracles are imported from ab_mason_claude.py — identical to the
2026-07-11 Claude Code vs mason run, so results are directly comparable.

Idempotent: per-run JSONs under results/; completed runs are skipped.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from ab_mason_claude import GIN_SRC, ORACLES, TASKS, sh  # noqa: F401

HOME = Path.home()
WORK = Path("/tmp/ab-local-clis")
RESULTS = WORK / "results"
TIMEOUT_S = 15 * 60
MODEL_TAG = "qwen3-coder:30b"


def fresh_tree(name: str) -> Path:
    import shutil
    d = WORK / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(GIN_SRC, d)
    shutil.rmtree(d / ".grove", ignore_errors=True)
    sh("git", "-C", str(d), "add", "-A")
    sh("git", "-C", str(d), "commit", "-qm", "ab-baseline", "--no-verify")
    return d


def run_to_completion(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[str, float, bool]:
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            start_new_session=True, env=env,
                            stdin=subprocess.DEVNULL)
    try:
        out, _ = proc.communicate(timeout=TIMEOUT_S)
        timed_out = False
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        out, _ = proc.communicate()
        timed_out = True
    return out, round(time.time() - t0, 1), timed_out


def run_mason(prompt: str, d: Path) -> dict:
    out, wall, timed_out = run_to_completion(
        [str(HOME / "bin" / "mason"), "--dir", str(d), "--yes",
         "--model", f"ollama:{MODEL_TAG}", prompt], d)
    m = re.search(r"usage: (\d+) in / (\d+) out", out)
    tok_in, tok_out = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return {"arm": "mason-30b", "wall_s": wall, "cost_usd": 0.0,
            "tokens_in": tok_in, "tokens_out": tok_out,
            "timed_out": timed_out, "answer": out[-2500:]}


def run_opencode(prompt: str, d: Path) -> dict:
    out, wall, timed_out = run_to_completion(
        ["opencode", "run", "-m", f"ollama/{MODEL_TAG}", prompt], d)
    return {"arm": "opencode-30b", "wall_s": wall, "cost_usd": 0.0,
            "timed_out": timed_out, "answer": out[-2500:]}


def run_continue(prompt: str, d: Path) -> dict:
    out, wall, timed_out = run_to_completion(
        ["cn", "--config", str(HOME / ".continue" / "config.yaml"),
         "--auto", "-p", prompt], d)
    return {"arm": "continue-30b", "wall_s": wall, "cost_usd": 0.0,
            "timed_out": timed_out, "answer": out[-2500:]}


ARMS = {
    "mason-30b": run_mason,
    "opencode-30b": run_opencode,
    "continue-30b": run_continue,
}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default=None,
                    help="task, arm, or task:arm filter")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    for tname, prompt in TASKS.items():
        for arm, runner in ARMS.items():
            if args.only and args.only not in (tname, arm, f"{tname}:{arm}"):
                continue
            for trial in range(1, args.trials + 1):
                rfile = RESULTS / f"{tname}.{arm}.t{trial}.json"
                if rfile.exists():
                    print(f"skip {tname}/{arm}/t{trial} (done)")
                    continue
                print(f"== {tname} / {arm} / t{trial} ==", flush=True)
                d = fresh_tree(f"{tname}__{arm}__t{trial}")
                rec = runner(prompt, d)
                if tname == "comprehend":
                    ok, why = ORACLES[tname](d, rec.get("answer", ""))
                else:
                    ok, why = ORACLES[tname](d)
                rec.update({"task": tname, "trial": trial, "oracle_pass": ok,
                            "oracle_note": why, "model": MODEL_TAG})
                rfile.write_text(json.dumps(rec, indent=2))
                print(f"   pass={ok} ({why})  wall={rec['wall_s']}s", flush=True)
    print("all done ->", RESULTS)


if __name__ == "__main__":
    main()
