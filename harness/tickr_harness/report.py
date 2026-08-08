"""Aggregate the tickr A/B into the three numbers the study is about:
correctness, token cost, and wall-clock — per arm, with per-trial spread so a
single lucky run cannot be mistaken for a result."""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ARM_ORDER = ["base", "prism"]


def _load(out: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(out.glob("*--*.json"))]


def _med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else 0.0


def _billable(r: dict) -> int:
    """Tokens the user pays for, cache reads included at their own rate but
    counted here as raw volume; cost_usd carries the real price."""
    return (r.get("input_tokens", 0) + r.get("output_tokens", 0)
            + r.get("cache_creation_tokens", 0) + r.get("cache_read_tokens", 0))


def main(out: Path) -> None:
    recs = _load(out)
    if not recs:
        print("no results yet")
        return

    cells = defaultdict(list)          # (arm, trial) -> records
    for r in recs:
        cells[(r["arm"], r["trial"])].append(r)
    for v in cells.values():
        v.sort(key=lambda r: r["turn"])

    print("=" * 78)
    print("tickr A/B — per cell (a cell is one continuous 9-turn Sonnet session)")
    print("=" * 78)
    hdr = (f"{'cell':<10} {'turns':>5} {'conf':>6} {'broken':>7} {'own':>5} "
           f"{'tokens':>10} {'cost$':>8} {'wall_min':>9} {'idx_s':>6}")
    print(hdr)
    summary = defaultdict(list)
    for (arm, trial), rs in sorted(cells.items()):
        last = rs[-1]
        g = last["grade"]
        tok = sum(_billable(r) for r in rs)
        cost = sum(r.get("cost_usd") or 0 for r in rs)
        wall = sum(r.get("wall_s") or 0 for r in rs)
        idx = sum(r.get("index_s") or 0 for r in rs)
        conf = g["conformance"]["score"]
        broken = g["broken_sites"]
        own = "Y" if g["own_tests"].get("green") else "n"
        print(f"{arm}-t{trial:<7} {len(rs):>5} {conf:>6.3f} {broken:>7} {own:>5} "
              f"{tok:>10,} {cost:>8.2f} {wall/60:>9.1f} {idx:>6.1f}")
        if len(rs) == 9:
            summary[arm].append(dict(conf=conf, broken=broken,
                                     own=g["own_tests"].get("green", False),
                                     tok=tok, cost=cost, wall=wall, idx=idx))

    print()
    print("=" * 78)
    print("ARM SUMMARY (median over complete cells)")
    print("=" * 78)
    agg = {}
    for arm in ARM_ORDER:
        s = summary.get(arm) or []
        if not s:
            continue
        agg[arm] = dict(
            n=len(s),
            conf=_med([x["conf"] for x in s]),
            broken=_med([x["broken"] for x in s]),
            own=sum(x["own"] for x in s) / len(s),
            tok=_med([x["tok"] for x in s]),
            cost=_med([x["cost"] for x in s]),
            wall=_med([x["wall"] for x in s]),
            idx=_med([x["idx"] for x in s]),
        )
        a = agg[arm]
        print(f"{arm:<6} n={a['n']}  conformance={a['conf']:.3f}  "
              f"broken_sites={a['broken']:.1f}  own_tests_green={a['own']:.0%}  "
              f"tokens={a['tok']:,.0f}  cost=${a['cost']:.2f}  "
              f"wall={a['wall']/60:.1f}min  (+{a['idx']:.0f}s indexing)")

    if len(agg) == 2:
        b, p = agg["base"], agg["prism"]
        print()
        print("PRISM vs BASE")
        d = lambda x, y: (f"{(y - x):+.3f}")
        print(f"  correctness   {b['conf']:.3f} -> {p['conf']:.3f}   "
              f"({d(b['conf'], p['conf'])} conformance)")
        print(f"  completeness  {b['broken']:.1f} -> {p['broken']:.1f} broken call sites")
        if p["tok"]:
            print(f"  tokens        {b['tok']:,.0f} -> {p['tok']:,.0f}   "
                  f"({(1 - p['tok'] / b['tok']) * 100:+.1f}% vs base)")
        if p["cost"]:
            print(f"  cost          ${b['cost']:.2f} -> ${p['cost']:.2f}   "
                  f"({(1 - p['cost'] / b['cost']) * 100:+.1f}%)")
        wp = p["wall"] + p["idx"]
        print(f"  wall-clock    {b['wall']/60:.1f} -> {wp/60:.1f} min "
              f"(prism incl. indexing)  ({(1 - wp / b['wall']) * 100:+.1f}%)")

    # ------------------------------------------------------------ per turn
    print()
    print("=" * 78)
    print("PER TURN (median across trials)")
    print("=" * 78)
    print(f"{'turn':<16} {'arm':<6} {'conf':>6} {'broken':>7} {'tokens':>10} "
          f"{'cost$':>7} {'wall_s':>7} {'agent_steps':>12}")
    by_turn = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_turn[(r["turn"], r["turn_id"])][r["arm"]].append(r)
    for (ti, tid), per_arm in sorted(by_turn.items()):
        for arm in ARM_ORDER:
            rs = per_arm.get(arm) or []
            if not rs:
                continue
            print(f"{tid:<16} {arm:<6} "
                  f"{_med([x['grade']['conformance']['score'] for x in rs]):>6.3f} "
                  f"{_med([x['grade']['broken_sites'] for x in rs]):>7.1f} "
                  f"{_med([_billable(x) for x in rs]):>10,.0f} "
                  f"{_med([x.get('cost_usd') for x in rs]):>7.2f} "
                  f"{_med([x.get('wall_s') for x in rs]):>7.0f} "
                  f"{_med([x.get('num_turns') for x in rs]):>12.0f}")

    # ------------------------------------------------------------ tool use
    print()
    print("=" * 78)
    print("TOOL USE (cumulative per session, median over cells)")
    print("=" * 78)
    for arm in ARM_ORDER:
        finals = [rs[-1] for (a, _), rs in cells.items() if a == arm and len(rs) == 9]
        if not finals:
            continue
        names = sorted({k for f in finals for k in (f.get("tools") or {})})
        row = {n: _med([(f.get("tools") or {}).get(n, 0) for f in finals]) for n in names}
        top = sorted(row.items(), key=lambda kv: -kv[1])[:12]
        print(f"{arm}: " + "  ".join(f"{k.replace('mcp__prism__', '')}={v:.0f}"
                                     for k, v in top if v))

    # ------------------------------------------------------------ failures
    print()
    print("=" * 78)
    print("WHERE THE BASE ARM LOSES CONFORMANCE (final snapshot, union of trials)")
    print("=" * 78)
    for arm in ARM_ORDER:
        fails = defaultdict(int)
        n = 0
        for (a, _), rs in cells.items():
            if a != arm or len(rs) != 9:
                continue
            n += 1
            for t in rs[-1]["grade"]["conformance"]["failed_tests"]:
                fails[t] += 1
        if not n:
            continue
        print(f"\n{arm} (n={n} cells):")
        for t, c in sorted(fails.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
            print(f"   {c}/{n}  {t}")


if __name__ == "__main__":
    import sys
    main(Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "tickr-ab" / "results"))
