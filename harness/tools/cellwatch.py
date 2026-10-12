#!/usr/bin/env python3
"""Emit one line per finished cell and one per finished pair (same task+trial).
Per prism cell: impact answers that said complete, and greps after the first impact."""
import json, glob, os, re, time, sys

D = sys.argv[1]
seen = set(); cells = {}

def grep_like(name, inp):
    if name in ("Grep", "Glob"):
        return True
    if name != "Bash":
        return False
    c = inp.get("command", "")
    return bool(re.search(r"(^|[;&|\n(]\s*)(grep|rg|git grep|find)\b", c)) and not re.search(r"\b(mvn|gradle|pytest|npx|tsc|go (test|build|vet)|vitest|pnpm|bun)\b", c)

def impact_info(path):
    if not path or not os.path.exists(path):
        return None
    res = {}; calls = []
    for l in open(path):
        m = json.loads(l)
        if m.get("type") == "user" and isinstance(m["message"]["content"], list):
            for b in m["message"]["content"]:
                if b.get("type") == "tool_result":
                    c = b.get("content")
                    if isinstance(c, list):
                        c = "".join(x.get("text", "") for x in c if isinstance(x, dict))
                    res[b["tool_use_id"]] = c or ""
        if m.get("type") == "assistant":
            for b in m["message"]["content"]:
                if b.get("type") == "tool_use":
                    calls.append(b)
    impacts = [b for b in calls if "prism" in b["name"] and b.get("input", {}).get("op") == "change_impact"]
    complete = sum(1 for b in impacts if "safeToClaimComplete: true" in res.get(b["id"], ""))
    after = 0
    if impacts:
        i0 = calls.index(impacts[0])
        after = sum(1 for b in calls[i0 + 1:] if grep_like(b["name"], b.get("input", {})))
    prism = sum(1 for b in calls if "prism" in b["name"])
    greps = sum(1 for b in calls if grep_like(b["name"], b.get("input", {})))
    return dict(impacts=len(impacts), complete=complete, greps_after=after, prism=prism, greps=greps)

def line(d):
    tok = (d.get("tokens_request") or 0) + (d.get("tokens_out") or 0)
    s = f"{d['arm']:10} {'RESOLVED' if d.get('resolved') else 'FAILED  '} calls {d.get('api_calls')}  tokens {tok/1e6:.2f}M  ${d.get('cost_usd',0):.2f}"
    ii = impact_info(d.get("transcript"))
    if ii:
        s += f"  greps {ii['greps']}"
        if d["arm"] != "native":
            s += f"  prism {ii['prism']}  impact {ii['impacts']} (complete {ii['complete']})  greps-after-impact {ii['greps_after']}"
    return s, tok

deadline = time.time() + 6 * 3600
while time.time() < deadline:
    for f in sorted(glob.glob(os.path.join(D, "*.json"))):
        if f in seen:
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        seen.add(f)
        task = d["task"].split("__", 1)[1]; trial = d.get("trial", 1)
        s, tok = line(d)
        print(f"CELL {task} t{trial}: {s}", flush=True)
        cells.setdefault((task, trial), {})[d["arm"]] = (d, tok)
        p = cells[(task, trial)]
        if "native" in p and "prism_init" in p:
            (n, nt), (q, qt) = p["native"], p["prism_init"]
            r = lambda x, y: f"{x/y:.2f}x" if y else "n/a"
            print(f"PAIR {task} t{trial}: resolved native {n.get('resolved')} / prism {q.get('resolved')};"
                  f" prism vs native: calls {r(q.get('api_calls') or 0, n.get('api_calls') or 0)},"
                  f" tokens {r(qt, nt)}, cost {r(q.get('cost_usd') or 0, n.get('cost_usd') or 0)}", flush=True)
    log = os.path.join(D, "driver.log")
    if os.path.exists(log):
        t = open(log).read()
        if re.search(r"Traceback|RuntimeError", t) and "TB" not in seen:
            seen.add("TB"); print("ERROR in driver.log: " + t[-400:].replace("\n", " | "), flush=True)
    if len([x for x in seen if x.endswith(".json")]) >= int(sys.argv[2]) if len(sys.argv) > 2 else 32:
        print("DONE all cells", flush=True); break
    time.sleep(15)
