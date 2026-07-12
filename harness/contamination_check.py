#!/usr/bin/env python3
"""Contamination check for the SWE-bench A/B: how similar is each agent
patch to the GOLD (merged human) patch?

A model that *solves* an issue writes its own fix; a model that has
*memorized* the repo's history reproduces the merged fix. Verbatim
reproduction of gold patches is direct, per-task evidence of training-data
contamination — it turns the "resolve rate exceeds SOTA, so it's probably
memorized" inference into a measured artifact.

Metrics per (task, arm):
  file-overlap : |files(gold) ∩ files(model)| / |files(gold)|
  line-sim     : difflib ratio over the ordered added-line sequences
  exact-line   : |added(gold) ∩ added(model)| / |added(gold)|  (order-free)

Usage:
  python3 contamination_check.py \
      --runs runs/swebench-20 --tasks /path/to/swebench_tasks.json
"""
import argparse
import difflib
import glob
import json
import os
import re
import statistics as st


def files_of(patch: str) -> set:
    return set(re.findall(r"^\+\+\+ b/(\S+)", patch, re.M))


def added_lines(patch: str) -> list:
    return [l[1:].strip() for l in patch.splitlines()
            if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]


def score(gold: str, model: str):
    gf, mf = files_of(gold), files_of(model)
    file_overlap = len(gf & mf) / len(gf) if gf else 0.0
    ga, ma = added_lines(gold), added_lines(model)
    line_sim = difflib.SequenceMatcher(None, ga, ma).ratio()
    exact = len(set(ga) & set(ma)) / len(set(ga)) if ga else 0.0
    return file_overlap, line_sim, exact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs/swebench-20")
    ap.add_argument("--tasks", required=True,
                    help="fetched SWE-bench task JSON (carries gold `patch`)")
    ap.add_argument("--arm", default="baseline", choices=["baseline", "prism"])
    args = ap.parse_args()

    tasks = {t["instance_id"]: t for t in json.load(open(args.tasks))}
    report_fp = os.path.join(args.runs, f"prism-ab-{args.arm}.ab20-{args.arm}.json")
    resolved = set(json.load(open(report_fp))["resolved_ids"])

    rows = []
    for fp in sorted(glob.glob(os.path.join(args.runs, f"*.{args.arm}.json"))):
        d = json.load(open(fp))
        if "instance_id" not in d:
            continue
        gold = tasks.get(d["instance_id"], {}).get("patch", "")
        if not gold:
            continue
        rows.append((d["instance_id"], d["instance_id"] in resolved,
                     *score(gold, d["model_patch"])))

    print(f"arm={args.arm}")
    print(f"{'instance':42} {'res':4} {'files':6} {'seqsim':7} {'exact-line'}")
    verbatim = 0
    for iid, res, fo, ls, ex in rows:
        if ex >= 0.999:
            verbatim += 1
        print(f"{iid:42} {'PASS' if res else '-':4} {fo:5.0%} {ls:6.2f} {ex:8.0%}")

    res_rows = [r for r in rows if r[1]]
    un_rows = [r for r in rows if not r[1]]

    def agg(rs):
        return (100 * st.mean(r[2] for r in rs), st.mean(r[3] for r in rs),
                100 * st.mean(r[4] for r in rs))

    if res_rows:
        print("\nRESOLVED  (n=%d): file-overlap %.0f%%, line-sim %.2f, exact-line %.0f%%" % (len(res_rows), *agg(res_rows)))
    if un_rows:
        print("UNRESOLVED(n=%d): file-overlap %.0f%%, line-sim %.2f, exact-line %.0f%%" % (len(un_rows), *agg(un_rows)))
    print(f"verbatim gold reproductions (exact-line = 100%): {verbatim}/{len(rows)}")


if __name__ == "__main__":
    main()
