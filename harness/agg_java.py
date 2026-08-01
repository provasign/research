#!/usr/bin/env python3
"""Aggregate the Java day-to-day e2e run — the cut that matters is task_kind
(localized vs multi_site) x arm x model. Resolve rate is the headline; turns on
resolved cells secondary. Localized is the honest-majority regime; multi_site is
the (few, underpowered) tasks where completeness could pay off — reported
separately and never blended into a single headline.
"""
import json, glob, collections, statistics as st
from pathlib import Path

E2E = Path(__file__).parent / "runs" / "e2e"
ARMS = ["baseline", "codegraph", "prism_source"]
MODELS = ["haiku", "sonnet"]
TASKS = Path(__file__).parent / "tasks-e2e"

# task_kind lookup from the task files
kind = {}
for f in glob.glob(str(TASKS / "*__pr*.json")):
    try:
        d = json.load(open(f))
        if d.get("lang") == "java":
            kind[d["instance_id"]] = d.get("task_kind", "localized")
    except Exception:
        pass


def cells(arm, model):
    out = []
    for f in glob.glob(str(E2E / f"*jackson*.{model}.{arm}.json")) + \
             glob.glob(str(E2E / f"*jackson*.{model}.{arm}.t*.json")) + \
             glob.glob(str(E2E / f"*commons-lang*.{model}.{arm}.json")) + \
             glob.glob(str(E2E / f"*commons-lang*.{model}.{arm}.t*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("arm") == arm and d.get("model") == model and "error" not in d:
            d["_kind"] = kind.get(d["task"], "localized")
            out.append(d)
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else float("nan")


for model in MODELS:
    print(f"\n{'='*64}\nMODEL: {model}\n{'='*64}")
    for kfilter in ("localized", "multi_site", "ALL"):
        print(f"\n--- {kfilter} tasks ---")
        print(f"{'arm':14} {'cells':>5} {'resolve':>8} {'turns*':>7} {'cost*':>7}")
        for arm in ARMS:
            cs = [c for c in cells(arm, model) if kfilter == "ALL" or c["_kind"] == kfilter]
            if not cs:
                print(f"{arm:14} {'--':>5}"); continue
            res = [c for c in cs if c.get("resolved")]
            print(f"{arm:14} {len(cs):>5} {len(res)/len(cs)*100:>7.0f}% "
                  f"{mean([c.get('turns') for c in res]):>7.1f} "
                  f"{mean([c.get('cost_usd') for c in res]):>6.3f}")

print("\n* over resolved cells only. multi_site n is small — read as directional.\n")
