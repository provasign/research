"""Fail-fast monitor for the native vs prism_init run.

Reads finished cells in OUT, pairs them per task, prints the running table and
exits 1 (with the reason) on the first bad number:
  - LOSS: native resolved a task that prism did not
  - ERROR: any cell recorded an error / agent_error
  - RATIO: after >= MIN_PAIRS pairs, prism/native summed cost above RATIO_MAX
    (tokens, API calls and turns are reported, not stop conditions: a ~15%
    token overhead from prism's fixed per-request prefix is expected)
  - PAIR: one pair where prism cost > PAIR_MAX x native (and prism >= $0.30)
  - GAP: one pair where prism made > GAP_RATIO x native's API calls and at
    least GAP_MIN more (2026-10-10: a hook bug cost 9 calls, 24 vs 16, far
    under PAIR_MAX). Reviewed pairs go in ACKNOWLEDGED like losses.
"""
import glob, json, os, sys

OUT = sys.argv[1]
MIN_PAIRS, RATIO_MAX, PAIR_MAX = 10, 1.25, 2.5
GAP_RATIO, GAP_MIN = 1.5, 6
NATIVE, PRISM = "native", "prism_init"

# Losses already reviewed (one task id per line, '#' comments): counted in the
# totals, no longer a stop reason.
ack_file = os.path.join(OUT, "ACKNOWLEDGED")
ack = set()
if os.path.exists(ack_file):
    ack = {l.split("#")[0].strip() for l in open(ack_file)} - {""}

cells = {}
for f in glob.glob(os.path.join(OUT, "*.json")):
    d = json.load(open(f))
    if "task" not in d or "arm" not in d:
        continue
    cells.setdefault(d["task"], {})[d["arm"]] = d

def tok(c):
    return (c.get("tokens_request") or 0) + (c.get("tokens_out") or 0)

rows, bad = [], []
for task, arms in cells.items():
    for c in arms.values():
        if c.get("error") or c.get("agent_error"):
            bad.append(f"ERROR {task} {c['arm']}: {c.get('error') or c.get('agent_error')}")
    if NATIVE not in arms or PRISM not in arms:
        continue
    n, p = arms[NATIVE], arms[PRISM]
    rows.append((task, n, p))
    if n.get("resolved") and not p.get("resolved") and task not in ack:
        bad.append(f"LOSS {task}: native resolved, prism did not")
    na, pa = n.get("api_calls") or 0, p.get("api_calls") or 0
    if na and pa >= GAP_RATIO * na and pa - na >= GAP_MIN and task not in ack:
        bad.append(f"GAP {task}: prism {pa} API calls vs native {na}")
    nc, pc = n.get("cost_usd") or 0, p.get("cost_usd") or 0
    if nc and pc >= 0.30 and pc > PAIR_MAX * nc:
        bad.append(f"PAIR {task}: prism ${pc:.2f} vs native ${nc:.2f} ({pc / nc:.1f}x)")

def total(arm_idx, fn):
    return sum(fn(r[arm_idx]) or 0 for r in rows)

print(f"{'task':52} {'native':>22} {'prism':>22}")
for task, n, p in rows:
    fmt = lambda c: f"{'Y' if c.get('resolved') else 'n'} {c.get('turns') or 0:3}t {c.get('api_calls') or 0:3}c ${c.get('cost_usd') or 0:5.2f}"
    print(f"{task[-52:]:52} {fmt(n):>22} {fmt(p):>22}")
if rows:
    rn, rp = sum(1 for r in rows if r[1].get("resolved")), sum(1 for r in rows if r[2].get("resolved"))
    print(f"\npairs {len(rows)}  resolved native {rn} prism {rp}")
    for name, fn in (("cost", lambda c: c.get("cost_usd")), ("tokens", tok),
                     ("api_calls", lambda c: c.get("api_calls")), ("turns", lambda c: c.get("turns"))):
        a, b = total(1, fn), total(2, fn)
        ratio = b / a if a else 0
        print(f"  {name:9} native {a:12,.2f} prism {b:12,.2f}  prism/native {ratio:.3f}")
        if name == "cost" and len(rows) >= MIN_PAIRS and ratio > RATIO_MAX:
            bad.append(f"RATIO {name}: prism/native {ratio:.3f} > {RATIO_MAX} over {len(rows)} pairs")
if bad:
    print("\nSTOP:")
    for b in bad:
        print("  " + b)
    sys.exit(1)
