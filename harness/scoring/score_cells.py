#!/usr/bin/env python3
"""Canonical correctness scorer for SWE-bench-Live agent cells.

Replaces the ad-hoc eval shell scripts. Two things it gets right that the
ad-hoc ones did not:

1. SERIAL BY DEFAULT (--workers 1). Parallel eval workers cause false
   negatives on repos with concurrency-sensitive tests. Measured
   2026-08-12: browser-use-2480 scored resolved=False at --workers 4 with
   P2P 14/1 (half the suite uncollected, failure in
   test_agent_multiprocessing::test_two_event_loops_sequential) and
   resolved=True at --workers 1 -- from a patch BYTE-IDENTICAL to a run
   that passed. Every multi-cell eval before this used workers 2-4, so
   their numbers carry unknown flake noise.

2. FLAKE RETRY. A cell that fails is re-evaluated once, serially. A result
   that flips between runs is reported as UNSTABLE rather than silently
   counted as a failure -- an unstable cell is not evidence about the
   agent's patch.

Usage:
  python3 score_cells.py <run-dir> [--arms baseline prism] [--retry-failures]

<run-dir> holds <instance>.<arm>.json cells. Writes eval-<arm>/ dirs and
prints a table plus a machine-readable verdicts.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

LIVE = Path("/private/tmp/claude-501/-Users-tapabratapal-Projects-provasign-prism/"
            "c92e7cda-68a2-458f-bb70-004cec486de3/scratchpad/SWE-bench-Live")
DATASET = "SWE-bench-Live/SWE-bench-Live"


def build_patches(run_dir: Path, arm: str) -> tuple[Path, list[str]]:
    preds, ids = {}, []
    for f in sorted(run_dir.glob(f"*.{arm}.json")):
        rec = json.loads(f.read_text())
        preds[rec["instance_id"]] = {"model_patch": rec["model_patch"]}
        ids.append(rec["instance_id"])
    out = run_dir / f"{arm}.patches.json"
    out.write_text(json.dumps(preds))
    return out, ids


def run_eval(patches: Path, out_dir: Path, ids: list[str], workers: int = 1) -> None:
    """Run the Live harness. LOUD on failure: a silently-swallowed eval error
    is how a 'retry' can appear to run while doing nothing (observed
    2026-08-12 — the retry pass produced no output dir and no warning
    because capture_output hid both the error and the empty result)."""
    if not ids:
        return
    # ABSOLUTE paths: the eval subprocess runs with cwd=LIVE, so any relative
    # path here resolves against the wrong directory. Caught 2026-08-12 by the
    # loud-failure check above -- the eval had been silently reading a stale
    # results dir and reporting old numbers as if freshly scored.
    proc = subprocess.run(
        [str(LIVE / ".venv/bin/python"), "-m", "evaluation.evaluation",
         "--dataset", DATASET, "--split", "full", "--platform", "linux",
         "--patch_dir", str(patches.resolve()), "--output_dir", str(out_dir.resolve()),
         "--workers", str(workers), "--overwrite", "1",
         "--instance_ids", *ids],
        cwd=str(LIVE), capture_output=True, text=True)
    wrote = sum(1 for i in ids if (out_dir / i / "report.json").exists())
    if proc.returncode != 0 or wrote < len(ids):
        print(f"!! eval incomplete: rc={proc.returncode}, {wrote}/{len(ids)} reports "
              f"written into {out_dir}", file=sys.stderr)
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        for line in tail:
            print(f"   {line}", file=sys.stderr)


def verdict(out_dir: Path, iid: str):
    p = out_dir / iid / "report.json"
    if not p.exists():
        return None, None
    r = json.loads(p.read_text())
    f2p, p2p = r.get("FAIL_TO_PASS", {}), r.get("PASS_TO_PASS", {})
    # Zero F2P collected at all = the target test never ran: an environment
    # failure, not a patch verdict.
    uncollected = not f2p.get("success") and not f2p.get("failure")
    return bool(r.get("resolved")), {
        "f2p_pass": len(f2p.get("success", [])), "f2p_fail": len(f2p.get("failure", [])),
        "p2p_pass": len(p2p.get("success", [])), "p2p_fail": len(p2p.get("failure", [])),
        "uncollected": uncollected,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--arms", nargs="+", default=["baseline", "prism"])
    ap.add_argument("--workers", type=int, default=1,
                    help="serial by default; >1 risks concurrency-flake false negatives")
    ap.add_argument("--no-retry", action="store_true")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    results = {}
    for arm in args.arms:
        patches, ids = build_patches(run_dir, arm)
        if not ids:
            continue
        out_dir = run_dir / f"eval-{arm}"
        run_eval(patches, out_dir, ids, args.workers)

        arm_res = {}
        for iid in ids:
            res, detail = verdict(out_dir, iid)
            arm_res[iid] = {"resolved": res, **(detail or {})}

        # Retry failures serially once; a flip means UNSTABLE, not a failure.
        if not args.no_retry:
            failed = [i for i, v in arm_res.items() if v.get("resolved") is False]
            if failed:
                retry_dir = run_dir / f"eval-{arm}-retry"
                run_eval(patches, retry_dir, failed, 1)
                for iid in failed:
                    res2, detail2 = verdict(retry_dir, iid)
                    if res2 is not None and res2 != arm_res[iid]["resolved"]:
                        arm_res[iid]["unstable"] = True
                        arm_res[iid]["retry_resolved"] = res2
                        arm_res[iid]["retry_detail"] = detail2
        results[arm] = arm_res

    (run_dir / "verdicts.json").write_text(json.dumps(results, indent=1))

    print(f"{'instance':<46}" + "".join(f"{a:<22}" for a in results))
    all_ids = sorted({i for a in results.values() for i in a})
    for iid in all_ids:
        row = f"{iid[:45]:<46}"
        for arm in results:
            v = results[arm].get(iid, {})
            s = str(v.get("resolved"))
            if v.get("unstable"):
                s = f"UNSTABLE({v['resolved']}->{v['retry_resolved']})"
            elif v.get("uncollected"):
                s += "[uncollected]"
            row += f"{s:<22}"
        print(row)
    print()
    for arm, a in results.items():
        stable = [v for v in a.values() if not v.get("unstable")]
        n_res = sum(1 for v in stable if v.get("resolved"))
        n_uns = sum(1 for v in a.values() if v.get("unstable"))
        print(f"{arm}: {n_res}/{len(stable)} resolved"
              + (f"  ({n_uns} UNSTABLE excluded)" if n_uns else ""))


if __name__ == "__main__":
    main()
