"""Aggregate the ledger A/B.

The headline is `silent_misses` — failures on t07/t08, where the compiler and
the agent's own tests are both blind. Correctness on the compiler-caught turns
is expected to tie; there, the interesting column is cost.
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ARM_ORDER = ["base", "prism"]
SILENT = ("t07_provider_audit", "t08_minor_units")
COMPILED = ("t06_trace_param", "t09_describe", "t10_rename_move")


def _tok(r):
    return (r.get("input_tokens", 0) + r.get("output_tokens", 0)
            + r.get("cache_creation_tokens", 0) + r.get("cache_read_tokens", 0))


def _med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else 0.0


def at_point_of_change(rs: list[dict]) -> dict:
    """Misses measured in the record for the turn that MADE the change.

    This is the headline, and getting it wrong hid the entire effect on the
    first cell: a silent miss made at t07 was incidentally repaired by later
    turns, so the FINAL conformance read 1.000 while the agent had in fact
    shipped an incomplete change. The end-state score answers "was it ever
    fixed"; only the at-the-turn count answers "did the agent complete the
    change it was asked to make".
    """
    by_id = {r["turn_id"]: r for r in rs}
    out = {}
    for tid in SILENT + COMPILED:
        r = by_id.get(tid)
        if not r:
            continue
        out[tid] = r["grade"]["conformance"]["per_turn"].get(tid, {}).get("fail", 0)
    out["silent_at_change"] = sum(out.get(t, 0) for t in SILENT)
    out["compiler_at_change"] = sum(out.get(t, 0) for t in COMPILED)
    return out


def main(out: Path) -> None:
    recs = [json.loads(p.read_text()) for p in sorted(out.glob("*--*.json"))]
    if not recs:
        print("no results yet")
        return
    cells = defaultdict(list)
    for r in recs:
        cells[(r["arm"], r["trial"])].append(r)
    for v in cells.values():
        v.sort(key=lambda r: r["turn"])
    n_turns = max(len(v) for v in cells.values())

    print("=" * 92)
    print("ledger A/B — per cell (one continuous 13-turn Sonnet session)")
    print("=" * 92)
    print(f"{'cell':<10}{'turns':>6}{'SILENT@chg':>11}{'comp@chg':>9}"
          f"{'conf_end':>9}{'tsc':>5}{'own':>5}"
          f"{'src_loc':>9}{'tokens':>12}{'cost$':>8}{'wall':>7}")
    done = defaultdict(list)
    for (arm, trial), rs in sorted(cells.items()):
        last = rs[-1]
        g = last["grade"]
        poc = at_point_of_change(rs)
        row = dict(
            poc=poc,
            silent_poc=poc.get("silent_at_change", 0),
            comp_poc=poc.get("compiler_at_change", 0),
            conf=g["conformance"]["score"], silent=g["silent_misses"],
            tsc=bool(g["typecheck"].get("clean")),
            own=bool(g["own_tests"].get("green")),
            loc=g["stats"]["src_loc"],
            tok=sum(_tok(r) for r in rs),
            cost=sum(r.get("cost_usd") or 0 for r in rs),
            wall=sum(r.get("wall_s") or 0 for r in rs),
            idx=sum(r.get("index_s") or 0 for r in rs))
        print(f"{arm}-t{trial:<6}{len(rs):>6}{row['silent_poc']:>11}"
              f"{row['comp_poc']:>9}{row['conf']:>9.3f}"
              f"{'Y' if row['tsc'] else 'n':>5}{'Y' if row['own'] else 'n':>5}"
              f"{row['loc']:>9,}{row['tok']:>12,}{row['cost']:>8.2f}"
              f"{row['wall']/60:>7.1f}")
        if len(rs) == n_turns:
            done[arm].append(row)

    print()
    print("=" * 92)
    print("ARM SUMMARY (median over complete cells)")
    print("=" * 92)
    agg = {}
    for arm in ARM_ORDER:
        rows = done.get(arm) or []
        if not rows:
            continue
        agg[arm] = dict(
            n=len(rows),
            conf=_med([r["conf"] for r in rows]),
            silent_poc=_med([r["silent_poc"] for r in rows]),
            comp_poc=_med([r["comp_poc"] for r in rows]),
            t07=_med([r["poc"].get("t07_provider_audit", 0) for r in rows]),
            t08=_med([r["poc"].get("t08_minor_units", 0) for r in rows]),
            silent=_med([r["silent"] for r in rows]),
            tsc=sum(r["tsc"] for r in rows) / len(rows),
            loc=_med([r["loc"] for r in rows]),
            tok=_med([r["tok"] for r in rows]),
            cost=_med([r["cost"] for r in rows]),
            wall=_med([r["wall"] for r in rows]),
            idx=_med([r["idx"] for r in rows]))
        a = agg[arm]
        print(f"{arm:<6} n={a['n']}  SILENT@change={a['silent_poc']:.1f} "
              f"(t07={a['t07']:.1f} t08={a['t08']:.1f})  "
              f"compiler@change={a['comp_poc']:.1f}  "
              f"conf_end={a['conf']:.3f}  tsc_clean={a['tsc']:.0%}  "
              f"src_loc={a['loc']:,.0f}  tokens={a['tok']:,.0f}  "
              f"cost=${a['cost']:.2f}  wall={a['wall']/60:.1f}min")

    if len(agg) == 2:
        b, p = agg["base"], agg["prism"]
        print()
        print("PRISM vs BASE  (positive % = prism better)")
        print(f"  conformance    {b['conf']:.3f} -> {p['conf']:.3f}")
        print(f"  SILENT@CHANGE  {b['silent_poc']:.1f} -> {p['silent_poc']:.1f}   "
              f"<-- the measurement this study exists for")
        print(f"     t07 audit    {b['t07']:.1f} -> {p['t07']:.1f} missed of 24")
        print(f"     t08 units    {b['t08']:.1f} -> {p['t08']:.1f} missed of 40")
        print(f"  compiler@change {b['comp_poc']:.1f} -> {p['comp_poc']:.1f} "
              f"(expected ~0 both: tsc catches these)")
        print(f"  conformance_end {b['conf']:.3f} -> {p['conf']:.3f} "
              f"(later turns repair earlier misses — not the headline)")
        if b["tok"]:
            print(f"  tokens         {b['tok']:,.0f} -> {p['tok']:,.0f}   "
                  f"({(b['tok']-p['tok'])/b['tok']*100:+.1f}%)")
        if b["cost"]:
            print(f"  cost           ${b['cost']:.2f} -> ${p['cost']:.2f}   "
                  f"({(b['cost']-p['cost'])/b['cost']*100:+.1f}%)")
        wp = p["wall"] + p["idx"]
        print(f"  wall           {b['wall']/60:.1f} -> {wp/60:.1f} min  "
              f"({(b['wall']-wp)/b['wall']*100:+.1f}%, prism incl. indexing)")

    print()
    print("=" * 92)
    print("PER TURN (median across trials)   [S]=silent  [C]=compiler-caught")
    print("=" * 92)
    print(f"{'turn':<20}{'arm':<7}{'conf':>7}{'silent':>8}{'tsc':>6}"
          f"{'tokens':>12}{'cost$':>8}{'wall_s':>8}{'steps':>7}")
    by = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by[(r["turn"], r["turn_id"])][r["arm"]].append(r)
    for (ti, tid), per_arm in sorted(by.items()):
        mark = "[S]" if tid in SILENT else ("[C]" if tid in COMPILED else "   ")
        for arm in ARM_ORDER:
            rs = per_arm.get(arm) or []
            if not rs:
                continue
            print(f"{mark+tid:<20}{arm:<7}"
                  f"{_med([x['grade']['conformance']['score'] for x in rs]):>7.3f}"
                  f"{_med([x['grade']['silent_misses'] for x in rs]):>8.1f}"
                  f"{sum(bool(x['grade']['typecheck'].get('clean')) for x in rs):>6}"
                  f"{_med([_tok(x) for x in rs]):>12,.0f}"
                  f"{_med([x.get('cost_usd') for x in rs]):>8.2f}"
                  f"{_med([x.get('wall_s') for x in rs]):>8.0f}"
                  f"{_med([x.get('num_turns') for x in rs]):>7.0f}")

    print()
    print("=" * 92)
    print("TOOL USE (cumulative per session, median over complete cells)")
    print("=" * 92)
    for arm in ARM_ORDER:
        finals = [rs[-1] for (a, _), rs in cells.items()
                  if a == arm and len(rs) == n_turns]
        if not finals:
            continue
        names = sorted({k for f in finals for k in (f.get("tools") or {})})
        row = {n: _med([(f.get("tools") or {}).get(n, 0) for f in finals])
               for n in names}
        top = sorted(row.items(), key=lambda kv: -kv[1])[:12]
        print(f"{arm}: " + "  ".join(f"{k.replace('mcp__prism__','')}={v:.0f}"
                                     for k, v in top if v))

    print()
    print("=" * 92)
    print("SILENT-TURN FAILURES (final snapshot, union over cells)")
    print("=" * 92)
    for arm in ARM_ORDER:
        fails = defaultdict(int)
        n = 0
        for (a, _), rs in cells.items():
            if a != arm or len(rs) != n_turns:
                continue
            n += 1
            for t in rs[-1]["grade"]["conformance"]["failed_tests"]:
                if any(t.startswith(f"[{s}]") for s in SILENT):
                    fails[t] += 1
        print(f"\n{arm} (n={n}):" + ("" if fails else "  none"))
        for t, c in sorted(fails.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
            print(f"   {c}/{n}  {t}")


if __name__ == "__main__":
    import sys
    main(Path(sys.argv[1] if len(sys.argv) > 1
              else Path.home() / "ledger-ab" / "results"))
