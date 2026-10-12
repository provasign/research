"""Print one line per finished native/prism pair as the run produces them.

usage: bench_pairs.py <out_dir> [--skip-existing]
Polls <out_dir> every few seconds; each newly completed pair prints
  task | native: res turns calls tokens $ | prism: ... | running totals
Exits when <out_dir>/DONE exists or the monitor stop file appears.
"""
import glob, json, os, sys, time

OUT = sys.argv[1]
seen = set()
SKIP_EXISTING = "--skip-existing" in sys.argv  # resumed run: totals still count them
tot = {"n": 0, "rn": 0, "rp": 0, "cn": 0.0, "cp": 0.0}


def fmt(c):
    tok = (c.get("tokens_request") or 0) + (c.get("tokens_out") or 0)
    err = " ERROR" if c.get("error") or c.get("agent_error") else ""
    return (f"{'RESOLVED' if c.get('resolved') else 'failed  '} {c.get('turns') or 0:>3} turns "
            f"{c.get('api_calls') or 0:>3} calls {tok / 1000:>6.0f}k tok ${c.get('cost_usd') or 0:.2f}{err}")


first_pass = True
while True:
    cells = {}
    for f in glob.glob(os.path.join(OUT, "*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if "task" in d and "arm" in d:
            cells.setdefault(d["task"], {})[d["arm"]] = d
    for task, arms in sorted(cells.items()):
        if task in seen or "native" not in arms or "prism_init" not in arms:
            continue
        seen.add(task)
        n, p = arms["native"], arms["prism_init"]
        tot["n"] += 1
        tot["rn"] += bool(n.get("resolved"))
        tot["rp"] += bool(p.get("resolved"))
        tot["cn"] += n.get("cost_usd") or 0
        tot["cp"] += p.get("cost_usd") or 0
        ratio = tot["cp"] / tot["cn"] if tot["cn"] else 0
        if SKIP_EXISTING and first_pass:
            continue
        print(f"#{tot['n']} {task} | native {fmt(n)} | prism {fmt(p)} | "
              f"so far resolved native {tot['rn']} prism {tot['rp']}, cost prism/native {ratio:.2f}", flush=True)
    first_pass = False
    if os.path.exists(os.path.join(OUT, "DONE")):
        stop = os.path.join(OUT, "STOPPED")
        if os.path.exists(stop):
            print("RUN STOPPED: " + " / ".join(l.strip() for l in open(stop) if l.strip()), flush=True)
        else:
            print("RUN DONE", flush=True)
        break
    time.sleep(5)
