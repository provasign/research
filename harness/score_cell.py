#!/usr/bin/env python3
"""Score ONE agent cell for correctness, and report what the agent did.

Efficiency at unknown resolve-rate is uninterpretable -- one arm may simply
have done less. Every benchmark number this project produced before
2026-08-16 was efficiency-only for want of this step, which is why they were
deleted. This closes the loop: per cell, resolve-rate FIRST, then tokens and
turns, then the tool trace.

    python3 score_cell.py <run_dir> <instance_id>          # one cell pair
    python3 score_cell.py <run_dir> --all                  # every complete pair
    python3 score_cell.py <run_dir> --watch                # score as they land

Scoring runs docker_eval.score() in an ephemeral container over a throwaway
worktree, so neither the host repo nor the agent's edits are mutated.

FIELD MAPPING. The bed stores FAIL_TO_PASS / PASS_TO_PASS (uppercase, from
the mining pipeline) and no test_modules; docker_eval wants lowercase plus
test_modules. Modules are derived from the FAIL_TO_PASS node ids, and
PASS_TO_PASS is RESTRICTED to those same modules -- the beds carry up to 495
P2P node ids spanning the whole suite, and score() treats "not in the run
results" as a regression, so an unrestricted list would fail every cell for
tests that were never executed.
"""
from __future__ import annotations

import collections
import difflib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docker_eval  # noqa: E402

# The agent harness caches repos here; docker_eval defaults to the older
# gvg-corpus root and would report "worktree add" failures for every task.
docker_eval.CLONE_ROOT = Path.home() / ".cache" / "prism-research" / "swebench-repos"

CATEGORIES = [
    ("test-run", r"\b(pytest|tox|unittest|nose2?)\b"),
    ("env-setup", r"\b(pip|venv|virtualenv|conda|poetry|uv)\b|which -a|command -v"
                  r"|PYTHONPATH=|site-packages|-c [\"']import "),
    ("search", r"(?:^|[\s;&|(])(?:grep|rg|ag|ack|find)\b"),
    ("read-file", r"(?:^|[\s;&|(])(?:cat|sed|head|tail|less|wc|nl)\b"),
    ("git", r"(?:^|[\s;&|(])git\b"),
    ("repro", r"python3?\s+-c\b|<<[\"']?EOF"),
]


def categorize(cmd: str) -> str:
    for name, pat in CATEGORIES:
        if re.search(pat, cmd):
            return name
    return "other"


def modules_for(task: dict) -> list[str]:
    return sorted({n.split("::")[0] for n in task.get("FAIL_TO_PASS", []) if "::" in n})


def scoreable(task: dict) -> dict:
    """Adapt a bed task to what docker_eval.score expects."""
    mods = modules_for(task)
    inmods = lambda n: n.split("::")[0] in mods  # noqa: E731
    return {**task,
            "test_modules": mods,
            "fail_to_pass": task.get("FAIL_TO_PASS", []),
            "pass_to_pass": [n for n in task.get("PASS_TO_PASS", []) if inmods(n)]}


def retry_loops(cmds: list[str]) -> tuple[int, int]:
    runs = red = 0
    i = 0
    while i < len(cmds) - 1:
        j = i
        while j + 1 < len(cmds) and difflib.SequenceMatcher(None, cmds[j], cmds[j + 1]).ratio() >= 0.8:
            j += 1
        if j > i:
            runs += 1
            red += j - i
            i = j + 1
        else:
            i += 1
    return runs, red


def behaviour(rec: dict) -> dict:
    calls = rec.get("tool_calls") or []
    bash = [str(c["input"].get("command", "")) for c in calls if c["name"] == "Bash"]
    cats = collections.Counter(categorize(c) for c in bash)
    prism = [c for c in calls if c["name"].startswith("mcp__prism")]
    runs, red = retry_loops(bash)
    return {
        "tools": collections.Counter(c["name"] for c in calls),
        "bash": len(bash), "bash_cats": dict(cats.most_common()),
        "prism_calls": [(c["name"].replace("mcp__prism__prism_", ""), c["input"]) for c in prism],
        "retry_runs": runs, "retry_redundant": red,
        "denials": len(rec.get("permission_denials") or []),
    }


def report(task: dict, run_dir: Path, arms=("no-prism", "prism")) -> dict | None:
    tid = task["instance_id"]
    recs = {}
    for a in arms:
        p = run_dir / f"{tid}.{a}.json"
        if not p.exists():
            return None
        recs[a] = json.load(open(p))

    out = {"instance_id": tid, "arms": {}}
    print("\n" + "=" * 78)
    print(f"CELL  {tid}")
    print("=" * 78)

    st = scoreable(task)
    print(f"  scoring {len(st['fail_to_pass'])} FAIL_TO_PASS + "
          f"{len(st['pass_to_pass'])} PASS_TO_PASS in {st['test_modules']}")
    for a in arms:
        r = recs[a]
        t0 = time.time()
        try:
            sc = docker_eval.score(st, r["model_patch"]) if r["model_patch"].strip() \
                else {"resolved": False, "note": "empty patch"}
        except Exception as e:                                  # noqa: BLE001
            sc = {"resolved": None, "error": str(e)[:200]}
        sc["score_wall_s"] = round(time.time() - t0, 1)
        b = behaviour(r)
        out["arms"][a] = {"resolved": sc.get("resolved"), "score": sc,
                          "turns": r["turns"], "cost": r["cost_usd"],
                          "fresh": r["fresh_input_tokens"], "cache": r["cache_read_tokens"],
                          "out_tokens": r["output_tokens"], "prism_used": r["prism_used"],
                          "behaviour": {k: v for k, v in b.items() if k != "tools"}}

    # --- resolve-rate FIRST, then efficiency, then behaviour ---
    print("\n  CORRECTNESS")
    for a in arms:
        s = out["arms"][a]["score"]
        v = {True: "RESOLVED", False: "not resolved", None: "SCORING ERROR"}[s.get("resolved")]
        extra = s.get("error") or s.get("note") or f"f2p={s.get('f2p_ok')} p2p={s.get('p2p_ok')} n_run={s.get('n_run')}"
        print(f"    {a:9} {v:14} ({extra})  [{s['score_wall_s']}s]")
    rs = {a: out["arms"][a]["score"].get("resolved") for a in arms}
    if len(set(rs.values())) == 1 and None not in rs.values():
        print("    -> equal correctness: the efficiency numbers below are comparable")
    else:
        print("    -> UNEQUAL or unscored: efficiency below is NOT comparable")

    print("\n  EFFICIENCY")
    print(f"    {'arm':9} {'turns':>6} {'cost':>8} {'fresh':>8} {'out':>7} {'denials':>8}")
    for a in arms:
        x = out["arms"][a]
        print(f"    {a:9} {x['turns']:6} {x['cost']:8.3f} {x['fresh']:8} {x['out_tokens']:7} "
              f"{x['behaviour']['denials']:8}")

    print("\n  WHAT THE AGENT DID")
    for a in arms:
        x = out["arms"][a]; b = x["behaviour"]
        print(f"    {a:9} bash={b['bash']:3} {b['bash_cats']}")
        print(f"    {'':9} retry_loops={b['retry_runs']} ({b['retry_redundant']} redundant) "
              f"prism_used={x['prism_used']}")
        for name, args in b["prism_calls"]:
            print(f"    {'':9}   prism_{name}: {json.dumps(args)[:110]}")
    return out


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    run_dir = Path(sys.argv[1])
    # Prefer the gold-validated subset: a task whose GOLD patch does not score
    # resolved cannot have its cells judged, and including it reproduces the
    # efficiency-only numbers this whole loop exists to prevent.
    slice_path = next((run_dir.parent / n for n in
                       ("slice-scoreable.json", "slice-ab38.json")
                       if (run_dir.parent / n).exists()))
    tasks = {t["instance_id"]: t for t in json.load(open(slice_path))}
    print(f"scoring against {slice_path.name} ({len(tasks)} tasks)")
    done, results = set(), []

    def sweep():
        for tid, task in tasks.items():
            if tid in done:
                continue
            r = report(task, run_dir)
            if r:
                done.add(tid)
                results.append(r)
                json.dump(results, open(run_dir / "scored.json", "w"), indent=1)

    if sys.argv[2] == "--watch":
        # Score pairs as the run produces them; exit when the run is gone and
        # nothing new has appeared.
        import subprocess
        idle = 0
        while True:
            before = len(done)
            sweep()
            alive = subprocess.run(["pgrep", "-f", "swebench_ab.py"],
                                   capture_output=True).returncode == 0
            if len(done) == before:
                idle += 1
            else:
                idle = 0
            if not alive and idle >= 2:
                break
            time.sleep(30)
    elif sys.argv[2] == "--all":
        sweep()
    else:
        r = report(tasks[sys.argv[2]], run_dir)
        if r is None:
            print("incomplete pair")
            sys.exit(1)

    if results:
        ok = collections.Counter()
        for r in results:
            for a, x in r["arms"].items():
                ok[a] += bool(x["resolved"])
        print("\n" + "=" * 78)
        print(f"RESOLVE RATE over {len(results)} scored cells: " +
              "  ".join(f"{a} {ok[a]}/{len(results)}" for a in sorted(ok)))


if __name__ == "__main__":
    main()
