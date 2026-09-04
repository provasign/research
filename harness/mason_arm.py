#!/usr/bin/env python3
"""Mason arm for the Python bed: run `mason --json` one-shot per cell.

Reuses swebench_ab's isolation primitives (ensure_repo, sanitize_worktree,
sh) and mirrors its clone-strip-verify sequence exactly — gold must be
unreachable-by-discovery in the mason arm too. Records the same cell shape
(instance_id, arm="mason", turns, cost_usd, model_patch) so score_java/
score_cell tooling reads it unchanged.

Usage: python3 mason_arm.py --ids /tmp/bed36-scoreable-ids.json \
         --tasks runs/swebench-live/slice-bed36.json \
         --out runs/swebench-live/bed36-mason --mason ~/bin/mason-0321
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import swebench_ab as ab

def run_cell(task, mason_bin, out_dir, model):
    tid = task["instance_id"]
    rec_path = out_dir / f"{tid}.mason.json"
    if rec_path.exists():
        return "cached"
    repo_dir = ab.ensure_repo(task["repo"])
    wt = ab.WT_ROOT / f"{tid}.mason"
    if wt.exists():
        shutil.rmtree(wt)
    wt.parent.mkdir(parents=True, exist_ok=True)
    # — isolation, mirrored from run_arm (clone-strip-verify) —
    ab.sh("git", "clone", "--local", "--no-checkout", "--quiet", str(repo_dir), str(wt))
    upstream = ab.sh("git", "-C", str(repo_dir), "remote", "get-url", "origin").stdout.strip()
    ab.sh("git", "-C", str(wt), "remote", "set-url", "origin", upstream)
    ab.sh("git", "-C", str(wt), "config", "remote.origin.promisor", "true")
    ab.sh("git", "-C", str(wt), "config", "remote.origin.partialclonefilter", "blob:none")
    ab.sh("git", "-C", str(wt), "checkout", "--detach", "-f", "-q", task["base_commit"])
    for ref in ab.sh("git", "-C", str(wt), "for-each-ref", "--format=%(refname)").stdout.split():
        ab.sh("git", "-C", str(wt), "update-ref", "-d", ref)
    ab.sh("git", "-C", str(wt), "remote", "remove", "origin")
    head = ab.sh("git", "-C", str(wt), "rev-parse", "HEAD").stdout.strip()
    if head != task["base_commit"]:
        raise RuntimeError(f"{tid}: worktree at {head}, expected {task['base_commit']}")
    ab.sanitize_worktree(wt, "mason")
    prompt = ab.BASE_PROMPT.format(repo=task["repo"], problem=task["problem_statement"],
                                   steer="\n" + ab.INVESTIGATION_GUIDANCE)
    env = dict(os.environ)
    env.pop("MASON_STEERING", None)
    try:
        r = subprocess.run([mason_bin, "--json", "--yes", "--no-tui",
                            "--model", model, "--dir", str(wt),
                            "--max-cost", "2.50", "--max-turns", "28", prompt],
                           capture_output=True, text=True, timeout=3900, env=env)
        line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "{}"
        meta = json.loads(line)
    except Exception as e:
        meta = {"error": type(e).__name__ + ": " + str(e)[:150], "timed_out": "Timeout" in type(e).__name__}
    diff = ab.sh("git", "-C", str(wt), "diff").stdout
    usage = meta.get("usage") or {}
    rec = {"instance_id": tid, "arm": "mason", "model": model,
           "turns": -1,  # mason --json does not expose a turn count
           "duration_s": round((meta.get("durationMs") or 0) / 1000),
           "cost_usd": usage.get("costUSD", 0.0) or 0.0,
           "fresh_input_tokens": usage.get("inputTokens", 0),
           "cache_read_tokens": 0,
           "output_tokens": usage.get("outputTokens", 0),
           "tool_calls": [], "prism_used": True,
           "mason_meta": {k: v for k, v in meta.items() if k not in ("result", "text")},
           "model_patch": diff, "empty_patch": not diff.strip()}
    out_dir.mkdir(parents=True, exist_ok=True)
    json.dump(rec, open(rec_path, "w"), indent=1)
    shutil.rmtree(wt, ignore_errors=True)
    return f"t={rec['turns']} ${rec['cost_usd']:.2f} empty={rec['empty_patch']}"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", required=True)
    p.add_argument("--ids", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--mason", default=os.path.expanduser("~/bin/mason-0321"))
    p.add_argument("--model", default="sonnet")
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()
    tasks = json.load(open(a.tasks))
    if a.ids:
        keep = set(json.load(open(a.ids)))
        tasks = [t for t in tasks if t["instance_id"] in keep]
    if a.limit:
        tasks = tasks[:a.limit]
    out_dir = Path(a.out)
    for i, t in enumerate(tasks):
        print(f"[{i+1}/{len(tasks)}] {t['instance_id']} :: mason", flush=True)
        try:
            print("   ", run_cell(t, a.mason, out_dir, a.model), flush=True)
        except Exception as e:
            print(f"    FAILED: {e}", flush=True)

if __name__ == "__main__":
    main()
