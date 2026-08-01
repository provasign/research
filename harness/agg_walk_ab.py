#!/usr/bin/env python3
"""Aggregate the graph-walk A/B: mason (code_context dump) vs mason_walk
(graph_focus part-by-part). Pre-registered metrics:

  PRIMARY:  resolve rate (fail->pass, from the cell JSON).
  WANDER:   turns (tool calls in the transcript), scratch files (files created
            that are NOT in the task's declared src_files — the off-task tell),
            distinct files touched, wall_s.

Success (decided before running): WIN if resolve up >=2 cells net, OR resolve
flat but median turns down >=30% and scratch-files ~0. Read the numbers, do not
move the line.
"""
import json, glob, re, statistics as st
from pathlib import Path

E2E = Path(__file__).parent / "runs" / "e2e"
TASKS = Path(__file__).parent / "tasks-e2e"
ARMS = ["mason", "mason_walk"]

# task -> declared source files (edits outside this set = scratch/off-task)
srcset = {}
for f in glob.glob(str(TASKS / "*.json")):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    if "instance_id" in d:
        srcset[d["instance_id"]] = set(d.get("src_files", []))


def diff_files(diff_text):
    return set(re.findall(r"^\+\+\+ b/(.+)$", diff_text, re.M))


def turns(transcript_path):
    try:
        t = open(transcript_path).read()
    except Exception:
        return None
    # count tool invocations (mason renders each as a bullet or ✎/$ line)
    return len(re.findall(r"^\s*[·✎$◆]", t, re.M)) or None


def cells(arm):
    out = []
    for f in glob.glob(str(E2E / f"*.{arm}.json")) + glob.glob(str(E2E / f"*.{arm}.t*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("arm") != arm:
            continue
        iid = d["task"]
        diff_path = str(f).replace(".json", ".diff")
        dfiles = diff_files(open(diff_path).read()) if Path(diff_path).exists() else set()
        scratch = len([x for x in dfiles if x not in srcset.get(iid, set())
                       and not x.endswith((".grove", ".shale"))])
        d["_scratch"] = scratch
        d["_files_touched"] = len(dfiles)
        d["_turns"] = turns(str(f).replace(".json", ".transcript.txt").replace(f".{arm}.", f".{arm}."))
        out.append(d)
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else float("nan")


print(f"\nGraph-walk A/B — mason (dump) vs mason_walk (part-by-part), qwen3-coder:30b\n")
print(f"{'arm':12} {'cells':>5} {'resolve':>8} {'turns~':>7} {'scratch~':>8} {'files~':>7} {'wall~':>6}")
rows = {}
for arm in ARMS:
    cs = cells(arm)
    if not cs:
        print(f"{arm:12} {'-- no cells (run it first) --':>40}")
        continue
    res = sum(1 for c in cs if c.get("resolved"))
    rows[arm] = dict(n=len(cs), res=res,
                     turns=med([c.get("_turns") for c in cs]),
                     scratch=med([c.get("_scratch") for c in cs]),
                     files=med([c.get("_files_touched") for c in cs]),
                     wall=med([c.get("wall_s") for c in cs]))
    r = rows[arm]
    print(f"{arm:12} {r['n']:>5} {res}/{len(cs):>3}{'':>1} {r['turns']:>7.0f} "
          f"{r['scratch']:>8.1f} {r['files']:>7.1f} {r['wall']:>5.0f}s")

if "mason" in rows and "mason_walk" in rows:
    a, b = rows["mason"], rows["mason_walk"]
    print("\nVerdict (pre-registered):")
    dres = b["res"] - a["res"]
    dturns = (a["turns"] - b["turns"]) / a["turns"] * 100 if a["turns"] and a["turns"] == a["turns"] else 0
    print(f"  resolve delta: {dres:+d} cells   turns delta: {dturns:+.0f}%   "
          f"scratch: {a['scratch']:.1f} -> {b['scratch']:.1f}")
    if dres >= 2:
        print("  => WIN (resolve up >=2 cells)")
    elif dres >= 0 and dturns >= 30 and b["scratch"] <= 0.5:
        print("  => WIN (resolve held, wander down hard)")
    elif dres < 0:
        print("  => LOSS (walk resolved fewer)")
    else:
        print("  => INCONCLUSIVE — needs more tasks")
