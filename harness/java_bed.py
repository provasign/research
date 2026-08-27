#!/usr/bin/env python3
"""Gold-validate Multi-SWE-bench java_verified tasks into a usable bed.

Schema bridge: Multi-SWE-bench gives FAIL_TO_PASS/PASS_TO_PASS as node ids;
java_eval wants test_classes (simple names) + fail_to_pass/pass_to_pass.
A task is usable only if GOLD makes every F2P pass while the same run on
base+tests alone fails at least one — the same two-sided gate the Python
bed uses.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import java_eval

H = Path(__file__).parent
RAW = H / "runs/swebench-live/java91-raw.json"
OUT = H / "runs/swebench-live/java-bed-validation.json"

def norm(t):
    """Multi-SWE-bench row -> java_eval task dict."""
    def ids(v):
        if isinstance(v, str):
            try: v = json.loads(v)
            except Exception: v = [v]
        return list(v or [])
    f2p, p2p = ids(t.get("FAIL_TO_PASS")), ids(t.get("PASS_TO_PASS"))
    def cls(n):
        n = n.split(":", 1)[-1] if n.startswith(("src:", "test:", "tests:")) else n
        return n.split("::")[0].split("#")[0]
    classes = sorted({cls(n) for n in f2p if n})
    return {**t, "test_classes": classes,
            "fail_to_pass": [n.replace("#", "::") for n in f2p],
            "pass_to_pass": [n.replace("#", "::") for n in p2p]}

def main():
    rows = json.load(open(RAW))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    done = json.load(open(OUT)) if OUT.exists() and not only else {}
    for t in rows:
        tid = t["instance_id"]
        if only and only not in tid: continue
        if tid in done: continue
        lut = {k.lower(): v for k, v in java_eval.REPO_DIR.items()}
        repo_dir = lut.get(t["repo"].lower())
        if not repo_dir or not Path(repo_dir).exists():
            done[tid] = {"scoreable": False, "why": f"no local clone for {t['repo']}"}
            print(f"{tid[:40]:40} SKIP no clone", flush=True); continue
        task = norm(t)
        if not task["test_classes"]:
            done[tid] = {"scoreable": False, "why": "no test classes parsed"}
            print(f"{tid[:40]:40} SKIP no classes", flush=True); continue
        try:
            gold = java_eval.score(Path(repo_dir), task, task["patch"])
            empty = java_eval.score(Path(repo_dir), task, "") if gold.get("resolved") else {"resolved": None}
            rec = {"gold": gold, "empty": empty,
                   "scoreable": bool(gold.get("resolved") and not empty.get("resolved")),
                   "classes": task["test_classes"][:3]}
        except Exception as e:
            rec = {"scoreable": False, "why": str(e)[:120]}
        done[tid] = rec
        json.dump(done, open(OUT, "w"), indent=1)
        print(f"{tid[:40]:40} scoreable={rec.get('scoreable')} "
              f"gold={rec.get('gold',{}).get('resolved')} n_run={rec.get('gold',{}).get('n_run')} "
              f"{rec.get('why','')[:50]}", flush=True)
    ok = sum(1 for v in done.values() if v.get("scoreable"))
    print(f"\nJAVA BED: {ok} scoreable of {len(done)} checked")

main()
