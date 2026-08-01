#!/usr/bin/env python3
"""Aggregate the day-to-day coding e2e run into a per-arm comparison.

The question: on ordinary bug-fix work (fail->pass scored by the repo's own
tests), does a code graph help the agent, and does Prism's richer one-call
context cut agent turns vs CodeGraph's leaner explore?

Headline = resolve rate (correctness). Secondary = turns / tokens / cost,
which is where the "Prism returns a bit more -> fewer round-trips" hypothesis
is tested. Averaged over trials; only resolved cells count toward the
turns-on-success mean (a failed cell's turn count is not comparable).
"""
import json, glob, collections, statistics as st
from pathlib import Path

E2E = Path(__file__).parent / "runs" / "e2e"
ARMS = ["baseline", "codegraph", "prism_source"]
MODEL = "haiku"


def cells(arm):
    out = []
    for f in glob.glob(str(E2E / f"pallets__click__pr*.{MODEL}.{arm}.json")) + \
             glob.glob(str(E2E / f"pallets__click__pr*.{MODEL}.{arm}.t*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("arm") == arm and d.get("model") == MODEL and "error" not in d:
            out.append(d)
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else float("nan")


print(f"\nDay-to-day coding — e2e (pallets/click, {MODEL}, fail->pass scored in Docker)\n")
print(f"{'arm':14} {'cells':>5} {'resolve':>8} {'turns*':>7} {'tok_in*':>8} {'cost*':>7} {'wall*':>6}")
print("-" * 60)
rows = {}
for arm in ARMS:
    cs = cells(arm)
    if not cs:
        print(f"{arm:14} {'--- no cells ---':>40}")
        continue
    n = len(cs)
    resolved = [c for c in cs if c.get("resolved")]
    rate = len(resolved) / n
    # per-task resolve (any trial) for a task-level view
    by_task = collections.defaultdict(list)
    for c in cs:
        by_task[c["task"]].append(bool(c.get("resolved")))
    turns = mean([c.get("turns") for c in resolved])
    tok = mean([c.get("tokens_in") for c in resolved])
    cost = mean([c.get("cost_usd") for c in resolved])
    wall = mean([c.get("wall_s") for c in resolved])
    rows[arm] = dict(n=n, rate=rate, turns=turns, tok=tok, cost=cost, wall=wall,
                     tasks=len(by_task), tasks_ever=sum(1 for v in by_task.values() if any(v)))
    print(f"{arm:14} {n:>5} {rate*100:>7.0f}% {turns:>7.1f} "
          f"{(tok or 0)/1000:>7.0f}k {cost:>6.3f} {wall:>5.0f}s")

print("\n* turns/tokens/cost/wall averaged over RESOLVED cells only (comparable-work basis).")
print("resolve = resolved cells / total cells across all trials.\n")

if "prism_source" in rows and "codegraph" in rows:
    p, c = rows["prism_source"], rows["codegraph"]
    print("Head-to-head (prism_source vs codegraph):")
    print(f"  resolve rate : {p['rate']*100:.0f}% vs {c['rate']*100:.0f}%")
    if p["turns"] == p["turns"] and c["turns"] == c["turns"]:
        dt = (c["turns"] - p["turns"]) / c["turns"] * 100
        print(f"  turns/success: {p['turns']:.1f} vs {c['turns']:.1f}  "
              f"({dt:+.0f}% prism vs codegraph)")
