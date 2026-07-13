"""Efficiency A/B: Prism vs CodeGraph — speed + tokens, reported NEXT TO recall.

Correctness first. Tokens/speed only matter at equal completeness — a cheaper
incomplete answer is a faster broken build. So for the SAME one-call use case
(get the change-impact/context for a symbol) we measure, per tool, per task:
  recall     (completeness — from codegraph_vs_prism, the headline metric)
  wall_ms    (speed — time to answer)
  out_tokens (context cost — len(stdout)//4)

Two context-delivery shapes, both measured (no LLM):
  - impact set:    prism `change-impact`     vs  codegraph `explore`
  - (note) explore bundles verbatim SOURCE (to spare later file reads); prism
    change-impact returns a compact site list. So raw token counts are NOT
    like-for-like on the delivery axis — we report both numbers and say so.

Usage: python efficiency_sweep.py
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import codegraph_vs_prism as cg

HOME = Path.home()
# (task label, corpus, prism Type.method target, recall_prism, recall_cg) — recall
# from the completeness sweep (codegraph-vs-prism-final.json), so this file only
# adds speed+tokens and never re-litigates correctness.
CASES = [
    ("jackson-jsonnode-get",     HOME/"gvg-corpus/jackson-databind", "JsonNode.get(int)",                       1.00, 0.75),
    ("jackson-settable-set",     HOME/"gvg-corpus/jackson-databind", "SettableBeanProperty.set(Object,Object)", 1.00, 0.27),
    ("jackson-serialize",        HOME/"gvg-corpus/jackson-databind", "JsonSerializer.serialize",                0.98, 0.56),
    ("jackson-deserialize",      HOME/"gvg-corpus/jackson-databind", "JsonDeserializer.deserialize",            1.00, 0.00),
    ("guava-forwarding-delegate",HOME/"gvg-corpus/guava/guava",      "ForwardingObject.delegate",               1.00, 0.17),
    ("gin-render-impact",        HOME/"gvg-corpus/gin",              "Render.Render",                           1.00, 1.00),
]


def timed(cmd: list[str], cwd: Path) -> tuple[float, int, str]:
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    ms = (time.monotonic() - t0) * 1000
    out = r.stdout or ""
    return round(ms), len(out) // 4, out


def main() -> None:
    print(f"{'task':28}{'recall':>14}{'wall_ms':>16}{'out_tokens':>18}")
    print(f"{'':28}{'prism  cg':>14}{'prism    cg':>16}{'prism      cg':>18}")
    agg = {"pms": [], "cms": [], "ptok": [], "ctok": []}
    for label, corpus, target, rp, rc in CASES:
        if not corpus.exists():
            print(f"  {label:26} corpus absent"); continue
        # prism change-impact (compact impact set)
        pms, ptok, _ = timed([str(cg.PRISM), "change-impact", target, "."], corpus)
        # codegraph explore (headline one-call context; bundles source)
        bare = cg.bare_symbol(target)
        cms, ctok, _ = timed([str(cg.CODEGRAPH), "explore", bare], corpus)
        agg["pms"].append(pms); agg["cms"].append(cms)
        agg["ptok"].append(ptok); agg["ctok"].append(ctok)
        print(f"  {label:26} {rp:.2f} {rc:.2f}   {pms:6} {cms:7}   {ptok:7} {ctok:8}")
    n = len(agg["pms"])
    if n:
        print(f"\n  {'MEAN':26} "
              f"          {sum(agg['pms'])//n:6} {sum(agg['cms'])//n:7}   "
              f"{sum(agg['ptok'])//n:7} {sum(agg['ctok'])//n:8}")
        print("\nNote: prism change-impact = compact impact SET (no source). codegraph "
              "explore = impact + relationships + verbatim SOURCE. Explore's larger token "
              "count buys front-loaded reads; it is NOT wasted. The like-for-like token "
              "claim (agent tokens with vs without the tool) needs an agentic A/B (a model).")


if __name__ == "__main__":
    main()
