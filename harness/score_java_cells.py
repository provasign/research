#!/usr/bin/env python3
"""Score agent cells for the Java bed (java_eval instead of docker_eval).

Kept separate from score_cell.py rather than branching it: the Python path
is load-bearing for every result this project has, and a shared edit risks
both. Same contract — resolve FIRST, then efficiency, contamination voids.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import java_eval, score_cell

H = Path(__file__).parent

def main():
    run_dir = Path(sys.argv[1])
    tasks = {t["instance_id"]: t for t in json.load(open(H / "runs/swebench-live/slice-java12.json"))}
    lut = {k.lower(): v for k, v in java_eval.REPO_DIR.items()}
    results = []
    for tid, t in sorted(tasks.items()):
        arms = {}
        for arm in ("baseline", "prism"):
            p = run_dir / f"{tid}.{arm}.json"
            if not p.exists():
                continue
            rec = json.load(open(p))
            contam = score_cell.contamination(rec)
            if contam:
                arms[arm] = {"resolved": None, "voided": True, "why": contam[0][:80],
                             "turns": rec["turns"], "cost": rec["cost_usd"]}
                continue
            task = dict(t)
            def ids(v):
                if isinstance(v, str):
                    try: v = json.loads(v)
                    except Exception: v = [v]
                return list(v or [])
            f2p, p2p = ids(t["FAIL_TO_PASS"]), ids(t["PASS_TO_PASS"])
            def cls(n):
                n = n.split(":", 1)[-1] if n.startswith(("src:", "test:", "tests:")) else n
                return n.split("::")[0].split("#")[0]
            task.update(test_classes=sorted({cls(n) for n in f2p if n}),
                        fail_to_pass=[n.replace("#", "::") for n in f2p],
                        pass_to_pass=[n.replace("#", "::") for n in p2p])
            try:
                sc = java_eval.score(Path(lut[t["repo"].lower()]), task, rec["model_patch"]) \
                     if rec["model_patch"].strip() else {"resolved": False, "note": "empty patch"}
            except Exception as e:
                sc = {"resolved": None, "error": str(e)[:100]}
            arms[arm] = {"resolved": sc.get("resolved"), "turns": rec["turns"],
                         "cost": rec["cost_usd"], "prism_used": rec.get("prism_used"),
                         "n_run": sc.get("n_run"), "fresh": rec["fresh_input_tokens"],
                         "cache": rec["cache_read_tokens"]}
        if arms:
            results.append({"instance_id": tid, "arms": arms})
            print(f"{tid[:42]:42} " + "  ".join(
                f"{a}={arms[a].get('resolved')}(t{arms[a]['turns']},${arms[a]['cost']:.2f})"
                for a in sorted(arms)), flush=True)
            json.dump(results, open(run_dir / "scored.json", "w"), indent=1)
    both = [r for r in results if len(r["arms"]) == 2 and not any(x.get("voided") for x in r["arms"].values())]
    if both:
        b = sum(1 for r in both if r["arms"]["baseline"]["resolved"])
        p = sum(1 for r in both if r["arms"]["prism"]["resolved"])
        import statistics
        cb = [r["arms"]["baseline"]["cost"] for r in both]
        cp = [r["arms"]["prism"]["cost"] for r in both]
        tb = [r["arms"]["baseline"]["turns"] for r in both]
        tp = [r["arms"]["prism"]["turns"] for r in both]
        print(f"\nJAVA RESOLVE over {len(both)} clean pairs: baseline {b}/{len(both)}  prism {p}/{len(both)}")
        print(f"cost  mean ${statistics.mean(cb):.3f} vs ${statistics.mean(cp):.3f}"
              f"   turns mean {statistics.mean(tb):.1f} vs {statistics.mean(tp):.1f}")
        print(f"adoption: {sum(1 for r in both if r['arms']['prism'].get('prism_used'))}/{len(both)}")

main()
