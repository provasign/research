"""Aggregate jackson runs: recall AND token/cost, per task x model x arm.

The graph's surviving value in the Go study was cost-at-fixed-quality, so for the
stronger (expensive) models we report tokens + USD alongside recall. Also prints
the running bill (sum of total_cost_usd over all jackson runs) and the T-vs-G
cost ratio at matched recall.

Run rescore_java.py first so graph-arm line-number answers score fairly.
"""
from __future__ import annotations

import glob
import json
import statistics
from pathlib import Path

TASKS = [  # ordered by GT size
    ("jackson-jsonnode-get", 8), ("jackson-settable-set", 22),
    ("jackson-writetypeprefix", 38), ("jackson-serializewithtype", 58),
    ("jackson-deserialize", 104), ("jackson-serialize", 108),
]
RUNS = Path(__file__).resolve().parent / "runs"
# Known Claude tiers print first, in order; any other model dir (e.g. a GPT model
# run via run_codex.py) is auto-discovered and appended.
KNOWN_ORDER = ["haiku", "sonnet", "opus"]


def discover_models() -> list[str]:
    found: set[str] = set()
    for task, _ in TASKS:
        d = RUNS / task
        if d.is_dir():
            for sub in d.iterdir():
                if sub.is_dir() and any(sub.glob("[TGV].t*.json")):
                    found.add(sub.name)
    ordered = [m for m in KNOWN_ORDER if m in found]
    ordered += sorted(m for m in found if m not in KNOWN_ORDER)
    return ordered


def cell(task: str, model: str, arm: str):
    rec, out_tok, cost, wall = [], [], [], []
    base = RUNS / task / model   # jackson uses a per-model subdir for every model
    for f in sorted(glob.glob(str(base / f"{arm}.t*.json"))):
        d = json.load(open(f))
        if d.get("status") != "ok" or d.get("violation"):
            continue
        rec.append(d["recall"])
        c = d.get("cost") or {}
        u = c.get("usage") or {}
        out_tok.append(u.get("output_tokens", 0))
        if c.get("total_cost_usd") is not None:
            cost.append(c["total_cost_usd"])
        if c.get("wall_s"):
            wall.append(c["wall_s"])
    return rec, out_tok, cost, wall


def main() -> None:
    grand_cost = 0.0
    grand_n = 0
    for model in discover_models():
        rows = []
        for task, size in TASKS:
            t = cell(task, model, "T")
            g = cell(task, model, "G")
            gs = cell(task, model, "Gstar")
            if not t[0] and not g[0] and not gs[0]:
                continue
            rows.append((task, size, t, g, gs))
        if not rows:
            continue
        has_gstar = any(r[4][0] for r in rows)
        print(f"\n================ {model.upper()} ================")
        hdr = (f"{'task':<26}{'sz':>4}  {'Trec':>6}{'Grec':>6}"
               + ("{'G*rec':>6}" if has_gstar else "")
               + "{'ΔG-T':>6}  {'Tcost$':>7}{'Gcost$':>7}{'G/T':>5}"
               + ("{'G*cost$':>8}" if has_gstar else "")
               + "{'nT':>4}{'nG':>4}" + ("{'nG*':>4}" if has_gstar else ""))
        print(f"{'task':<26}{'sz':>4}  {'Trec':>6}{'Grec':>6}"
              + (f"{'G*rec':>6}" if has_gstar else "")
              + f"{'ΔG-T':>6}  {'Tcost$':>7}{'Gcost$':>7}{'G/T':>5}"
              + (f"{'G*cost$':>8}" if has_gstar else "")
              + f"  {'nT':>3}{'nG':>3}" + (f"{'nG*':>4}" if has_gstar else ""))
        for task, size, t, g, gs in rows:
            tr = statistics.mean(t[0]) if t[0] else float("nan")
            gr = statistics.mean(g[0]) if g[0] else float("nan")
            gsr = statistics.mean(gs[0]) if gs[0] else float("nan")
            tc = statistics.mean(t[2]) if t[2] else float("nan")
            gc = statistics.mean(g[2]) if g[2] else float("nan")
            gsc = statistics.mean(gs[2]) if gs[2] else float("nan")
            ratio = (gc / tc) if (t[2] and g[2] and tc) else float("nan")
            grand_cost += sum(t[2]) + sum(g[2]) + sum(gs[2])
            grand_n += len(t[2]) + len(g[2]) + len(gs[2])
            row = (f"{task:<26}{size:>4}  {tr:>6.2f}{gr:>6.2f}"
                   + (f"{gsr:>6.2f}" if has_gstar else "")
                   + f"{gr-tr:>+6.2f}  {tc:>7.4f}{gc:>7.4f}{ratio:>5.2f}"
                   + (f"{gsc:>8.4f}" if has_gstar else "")
                   + f"  {len(t[0]):>3}{len(g[0]):>3}"
                   + (f"{len(gs[0]):>4}" if has_gstar else ""))
            print(row)
    print(f"\n--- running bill: ${grand_cost:.2f} over {grand_n} scored jackson runs ---")


if __name__ == "__main__":
    main()
