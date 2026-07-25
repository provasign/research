"""Greenfield benchmark, CLOUD arm: does Prism help SONNET build a new app,
not just Mason+local? Same two-phase task, same scoring, as greenfield_bench.py
— the only thing that changes is the executor: `claude -p` (subscription,
not the blocked Anthropic API key) instead of the mason CLI.

Two arms, same model (sonnet):
  prism   — Read/Write/Edit/Grep/Bash + the prism MCP server (unified `prism`
            tool: prepare with obligations before editing, verify after).
  noprism — Read/Write/Edit/Grep/Bash only, no MCP server at all.

Session continuation between phase 1 (scaffold) and phase 2 (self-refactor)
uses `claude -p ... --continue`, exactly like mason's `--continue`.

Usage: python greenfield_bench_cloud.py --model sonnet --trials 2 --arms prism,noprism --tiers small,medium
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile, time
from pathlib import Path

# Reuse the scaffold/refactor prompts and the independent scorer verbatim —
# only the executor differs from the local-model harness.
from greenfield_bench import TIERS, TIER_MANDATED_FILES, REFACTOR_TMPL, \
    pick_target_preferred, score_phase2, sh

OUT = Path(__file__).parent / "runs" / "greenfield"
OUT.mkdir(parents=True, exist_ok=True)
CFG_DIR = Path("/tmp/greenfield-cloud-mcp")
CFG_DIR.mkdir(exist_ok=True)
(CFG_DIR / "prism.json").write_text(json.dumps({"mcpServers": {
    "prism": {"type": "stdio", "command": str(Path.home() / "bin" / "prism"), "args": ["mcp"]}}}))

WRITE_TOOLS = ["Read", "Write", "Edit", "Grep", "Glob", "Bash(python:*)", "Bash(python3:*)",
               "Bash(pytest:*)", "Bash(mkdir:*)"]

ARMS = {
    "prism": {
        "guidance": ("TOOLS: file read/write/edit/grep, plus the Prism MCP server's unified `prism` "
                     "tool. Before writing any new code, and before any refactor, call "
                     "prism(task=\"<what you're building or changing>\") — it returns edit-ready "
                     "context and, once code exists, the type-resolved CHANGE OBLIGATIONS for any "
                     "function you're about to modify (every site that must be updated). After "
                     "editing, call prism(task=..., changed_files=[...]) to verify nothing was missed "
                     "before you finish. Resolve everything it reports."),
        "allowed": WRITE_TOOLS + ["mcp__prism"], "mcp": str(CFG_DIR / "prism.json"),
    },
    "noprism": {
        "guidance": "TOOLS: file read/write/edit/grep only. No other tools are available.",
        "allowed": WRITE_TOOLS, "mcp": None,
    },
}


def run_claude(workdir: Path, prompt: str, model: str, arm: str, cont: bool, timeout=1800):
    spec = ARMS[arm]
    full_prompt = spec["guidance"] + "\n\n" + prompt
    cmd = ["claude", "-p", full_prompt, "--model", model, "--output-format", "json",
           "--dangerously-skip-permissions", "--allowedTools", *spec["allowed"]]
    if spec["mcp"]:
        cmd += ["--mcp-config", spec["mcp"], "--strict-mcp-config"]
    if cont:
        cmd.append("--continue")
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # A single stuck trial must not crash the whole sweep.
        return {"ok": False, "error": f"timed out after {timeout}s",
                "wall_s": round(time.monotonic() - t0, 1), "tokens_in": 0, "tokens_out": 0,
                "cost_usd": None, "turns": None}
    wall = round(time.monotonic() - t0, 1)
    try:
        j = json.loads(r.stdout)
    except Exception:
        j = {"ok": False, "error": (r.stdout + r.stderr)[-500:]}
    tokens_in = tokens_out = 0
    if "usage" in j:
        u = j["usage"] or {}
        tokens_in = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
        tokens_out = u.get("output_tokens") or 0
    return {"ok": not j.get("is_error", False) and "error" not in j, "wall_s": wall,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": j.get("total_cost_usd"), "turns": j.get("num_turns"),
            "error": j.get("error")}


def run_trial(model: str, arm: str, tier: str, trial: int, max_turns_note: int):
    tag = f"{model}.{tier}.{arm}.t{trial}"
    outfile = OUT / f"cloud.{tag}.json"
    if outfile.exists():
        print(f"cached {outfile.name}", flush=True); return json.loads(outfile.read_text())

    workdir = Path(tempfile.mkdtemp(prefix=f"greenfield-cloud-{tag.replace('/','_')}-"))
    sh("git", "init", "-q", cwd=workdir)
    sh("git", "-C", str(workdir), "config", "user.email", "t@t")
    sh("git", "-C", str(workdir), "config", "user.name", "t")

    rec = {"model": model, "arm": arm, "tier": tier, "trial": trial, "workdir": str(workdir)}
    p1 = run_claude(workdir, TIERS[tier], model, arm, cont=False)
    rec["phase1"] = {k: p1[k] for k in ("ok", "wall_s", "tokens_in", "tokens_out", "cost_usd", "turns")}
    # Failure branches deliberately do NOT cache — a harness/agent failure is
    # not a completed trial, and not caching it means the next sweep launch
    # retries this cell instead of treating it as permanently done.
    if not p1.get("ok"):
        print(f"{tag}: PHASE1 FAILED {str(p1.get('error'))[:300]}", flush=True)
        return None

    target = pick_target_preferred(workdir)
    if target is None:
        print(f"{tag}: NO TARGET — no usable function with >=2 caller files", flush=True)
        return None
    name, defn_file, before_callers, n_sites = target
    rec["target"] = {"fn": name, "definedIn": defn_file, "callerFiles": list(before_callers.keys()), "totalSites": n_sites}

    prompt2 = REFACTOR_TMPL.format(fn=name, defn_file=defn_file)
    p2 = run_claude(workdir, prompt2, model, arm, cont=True)
    rec["phase2"] = {k: p2[k] for k in ("ok", "wall_s", "tokens_in", "tokens_out", "cost_usd", "turns")}
    if not p2.get("ok"):
        print(f"{tag}: PHASE2 FAILED {str(p2.get('error'))[:300]}", flush=True)
        return None

    fixed, forgotten = score_phase2(workdir, name, before_callers)
    rec["fixedFiles"] = fixed
    rec["forgottenFiles"] = forgotten
    rec["completeness"] = round(len(fixed) / max(1, len(fixed) + len(forgotten)), 3)
    rec["totalTokens"] = (rec["phase1"]["tokens_in"] or 0) + (rec["phase1"]["tokens_out"] or 0) + \
                          (rec["phase2"]["tokens_in"] or 0) + (rec["phase2"]["tokens_out"] or 0)
    rec["totalWallS"] = round((rec["phase1"]["wall_s"] or 0) + (rec["phase2"]["wall_s"] or 0), 1)
    rec["totalCostUSD"] = round((rec["phase1"]["cost_usd"] or 0) + (rec["phase2"]["cost_usd"] or 0), 4)

    py_files = [f for f in workdir.rglob("*.py") if ".git" not in f.parts]
    rec["codebaseFiles"] = len(py_files)
    rec["codebaseLOC"] = sum(len(f.read_text(errors="replace").splitlines()) for f in py_files)

    outfile.write_text(json.dumps(rec, indent=1))
    print(f"{tag}: target={name} sites={n_sites} completeness={rec['completeness']} "
          f"forgotten={forgotten} tokens={rec['totalTokens']} wall={rec['totalWallS']}s "
          f"cost=${rec['totalCostUSD']}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--arms", default="prism,noprism")
    ap.add_argument("--tiers", default="small,medium")
    a = ap.parse_args()
    for tier in a.tiers.split(","):
        for arm in a.arms.split(","):
            for t in range(1, a.trials + 1):
                try:
                    run_trial(a.model, arm, tier, t, 0)
                except Exception as e:
                    print(f"{a.model}.{tier}.{arm}.t{t}: UNCAUGHT ERROR {type(e).__name__}: {e}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
