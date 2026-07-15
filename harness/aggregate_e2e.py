"""Aggregate end-to-end benchmark cells into a resolve-rate report.

Reads runs/e2e/*.json, prints (and writes RESULTS-E2E.md) the resolve-rate grid
model x arm, a per-task grid, and a blast-radius split (churn as proxy) so the
localized-majority vs high-blast-radius tail contrast is visible.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

OUT = Path("runs/e2e")
ARMS = ["baseline", "prism_g", "prism_gstar", "prism_explore", "codegraph", "mason",
        "prism_g_nogrep", "prism_gstar_nogrep", "prism_explore_nogrep", "codegraph_nogrep"]


def load():
    cells = []
    for f in glob.glob(str(OUT / "*.json")):
        if Path(f).name in ("PAUSED.json",):
            continue
        try:
            d = json.load(open(f))
            if "arm" in d and "model" in d:
                cells.append(d)
        except Exception:
            pass
    return cells


def _rate(cells):
    n = len(cells); r = sum(1 for c in cells if c.get("resolved"))
    return f"{r}/{n}" if n else "-"


def main():
    cells = load()
    tasks = sorted({c["task"] for c in cells})
    models = sorted({c["model"] for c in cells})
    arms = [a for a in ARMS if any(c["arm"] == a for c in cells)]
    L = []
    L.append(f"# End-to-end benchmark — resolve rate (agent fixes the real 2026 bug, tests pass)\n")
    L.append(f"{len(tasks)} tasks · {len(cells)} cells · models: {', '.join(models)}\n")
    L.append("Resolve rate = FAIL_TO_PASS passes and no PASS_TO_PASS regression, "
             "scored in Docker. Tasks are post-cutoff (2026), issue-text prompts (no "
             "solution leak).\n")

    # model x arm grid
    L.append("## Resolve rate: model × arm\n")
    L.append("| model | " + " | ".join(arms) + " |")
    L.append("|" + "---|" * (len(arms) + 1))
    for m in models:
        row = [m]
        for a in arms:
            row.append(_rate([c for c in cells if c["model"] == m and c["arm"] == a]))
        L.append("| " + " | ".join(row) + " |")
    L.append("")

    # per-task grid (resolved flags), for one model at a time
    for m in models:
        L.append(f"## Per-task ({m})\n")
        L.append("| task | " + " | ".join(arms) + " |")
        L.append("|" + "---|" * (len(arms) + 1))
        for t in tasks:
            row = [t.split("__")[-1]]
            for a in arms:
                cs = [x for x in cells if x["task"] == t and x["model"] == m and x["arm"] == a]
                if not cs:
                    row.append("")
                elif len(cs) == 1:
                    row.append("✓" if cs[0].get("resolved") else "·")
                else:  # multiple trials: show resolved fraction
                    row.append(f"{sum(1 for c in cs if c.get('resolved'))}/{len(cs)}")
            L.append("| " + " | ".join(row) + " |")
        L.append("")

    report = "\n".join(L)
    (Path("RESULTS-E2E.md")).write_text(report)
    print(report)
    print(f"\n-> RESULTS-E2E.md   ({len(cells)} cells)")


if __name__ == "__main__":
    main()
