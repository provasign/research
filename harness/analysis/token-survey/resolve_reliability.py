"""Two questions that decide whether more n=50 A/Bs can see resolve effects:
(1) how much of the failure set is shared across arms (task-inherent), and
(2) test-retest: same task, near-identical prism config, two runs -- how often
does resolve agree?"""
import json
from pathlib import Path
R = Path("/Users/tapabratapal/Projects/provasign/research/harness/results")
gfr = {r["task"]: r for r in json.loads((R/"guard-fix-run/results.json").read_text())}
sba = {r["task"]: r for r in json.loads((R/"search-body-ab/results.json").read_text())}
tasks = sorted(set(gfr) & set(sba))
print(f"tasks in both runs: {len(tasks)}")

# four prism_init-config cells per task: gfr.prism, sba.native(base binary), sba.prism(exp binary); one native: gfr.native
rows = []
for t in tasks:
    rows.append({"task": t,
        "native": gfr[t]["native"]["resolved"],
        "prism_gfr": gfr[t]["prism"]["resolved"],
        "prism_base": sba[t]["native"]["resolved"],
        "prism_exp": sba[t]["prism"]["resolved"]})

# (1) failure overlap
both_fail = [r for r in rows if not r["native"] and not r["prism_gfr"]]
only_native_fail = [r for r in rows if not r["native"] and r["prism_gfr"]]
only_prism_fail = [r for r in rows if r["native"] and not r["prism_gfr"]]
print(f"\nguard-fix-run: native fails {sum(1 for r in rows if not r['native'])}, prism fails {sum(1 for r in rows if not r['prism_gfr'])}")
print(f"  fail in BOTH arms: {len(both_fail)}  |  only native fails: {len(only_native_fail)}  |  only prism fails: {len(only_prism_fail)}")

# (2) test-retest across the three prism_init-config runs
agree_gb = sum(1 for r in rows if r["prism_gfr"] == r["prism_base"])
agree_be = sum(1 for r in rows if r["prism_base"] == r["prism_exp"])
agree_ge = sum(1 for r in rows if r["prism_gfr"] == r["prism_exp"])
print(f"\ntest-retest, same task, prism_init config:")
print(f"  gfr.prism vs sba.baseline (no engine change between them beyond version drift): agree {agree_gb}/{len(rows)}")
print(f"  sba.baseline vs sba.exp (the actual A/B):                                      agree {agree_be}/{len(rows)}")
print(f"  gfr.prism vs sba.exp:                                                          agree {agree_ge}/{len(rows)}")

always_pass = [r["task"] for r in rows if r["prism_gfr"] and r["prism_base"] and r["prism_exp"]]
always_fail = [r["task"] for r in rows if not r["prism_gfr"] and not r["prism_base"] and not r["prism_exp"]]
flaky = [r for r in rows if len({r["prism_gfr"], r["prism_base"], r["prism_exp"]}) > 1]
print(f"\nacross the 3 prism runs: always pass {len(always_pass)}, always fail {len(always_fail)}, flip at least once {len(flaky)}")
print("  flaky tasks (gfr/base/exp):")
for r in flaky:
    print(f"    {r['task']:38s} {int(r['prism_gfr'])}/{int(r['prism_base'])}/{int(r['prism_exp'])}   native={int(r['native'])}")
print("  always-fail tasks:")
for t in always_fail: print(f"    {t}   native={int(gfr[t]['native']['resolved'])}")
hard_core = [t for t in always_fail if not gfr[t]["native"]["resolved"]]
print(f"\nfail in ALL FOUR cells (native + 3 prism): {len(hard_core)}")
