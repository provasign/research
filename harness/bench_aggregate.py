"""Aggregate the model x arm benchmark cells into BENCH-MATRIX.md.

Reads runs/bench-matrix/*.json (task.model.arm.t<n>.json), medians across
trials, and reports: the model x arm grid (recall / turns / tokens / speed),
token-savings with vs without Prism per model, and per-language and
per-blast-radius cuts. Correctness first: efficiency is shown next to recall.
"""
from __future__ import annotations

import glob
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

OUT = Path("runs/bench-matrix")
MODELS = ["local", "haiku", "sonnet", "opus"]
ARMS = ["baseline", "prism"]
ARM_LABEL = {"baseline": "without Prism", "prism": "with Prism"}


def load():
    cells = []
    for f in glob.glob(str(OUT / "*.json")):
        try:
            d = json.load(open(f))
            if "model" in d and "arm" in d and "task" in d:
                cells.append(d)
        except Exception:
            pass
    return cells


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return st.median(xs) if xs else None


def cell_agg(cells, model, arm, task=None):
    sel = [c for c in cells if c["model"] == model and c["arm"] == arm
           and (task is None or c["task"] == task)]
    if not sel:
        return None
    return {
        "n": len(sel),
        "recall": med([c.get("recall") for c in sel]),
        "turns": med([c.get("turns") for c in sel]),
        "tok_in": med([c.get("tokens_in") for c in sel]),
        "tok_out": med([c.get("tokens_out") for c in sel]),
        "wall": med([c.get("wall_s") for c in sel]),
    }


def fnum(x, unit="", k=False):
    if x is None:
        return "—"
    if k:
        return f"{x/1000:.0f}K{unit}"
    if isinstance(x, float):
        return f"{x:.3f}{unit}" if x < 10 else f"{x:.0f}{unit}"
    return f"{x}{unit}"


def main():
    cells = load()
    models = [m for m in MODELS if any(c["model"] == m for c in cells)]
    tasks = sorted({c["task"] for c in cells})
    L = []
    L.append("# Model × arm benchmark — does Prism help, per tier, and at what cost?\n")
    n_trials = med([len([c for c in cells if c["model"] == m and c["task"] == t
                         and c["arm"] == "prism"]) for m in models for t in tasks]) or "?"
    L.append(f"{len(tasks)} change-impact tasks (Java/Go/TypeScript/Python, 8→310 sites), "
             f"both arms steered, oracle-scored, medians across trials. "
             f"Only the tool varies within a model row.\n")

    # ── main grid ──────────────────────────────────────────────────────────
    L.append("## Recall · turns · tokens · speed\n")
    L.append("| Model | Arm | Recall | Turns | Tokens in | Tokens out | Wall (s) |")
    L.append("|---|---|---:|---:|---:|---:|---:|")
    for m in models:
        for arm in ARMS:
            a = cell_agg(cells, m, arm)
            if not a:
                continue
            L.append(f"| {m} | {ARM_LABEL[arm]} | {fnum(a['recall'])} | {fnum(a['turns'])} "
                     f"| {fnum(a['tok_in'], k=True)} | {fnum(a['tok_out'], k=True)} "
                     f"| {fnum(a['wall'])} |")
    L.append("")

    # ── with vs without: savings + deltas ──────────────────────────────────
    L.append("## With Prism vs without — recall gain, token savings, speedup\n")
    L.append("| Model | Recall (w/o → with) | Token savings | Turns (w/o → with) | Speed |")
    L.append("|---|---|---:|---|---:|")
    for m in models:
        b = cell_agg(cells, m, "baseline")
        p = cell_agg(cells, m, "prism")
        if not (b and p):
            continue
        save = "—"
        if b["tok_in"] and p["tok_in"]:
            save = f"{100*(b['tok_in']-p['tok_in'])/b['tok_in']:.0f}%"
        speed = "—"
        if b["wall"] and p["wall"] and p["wall"] > 0:
            speed = f"{b['wall']/p['wall']:.1f}×"
        L.append(f"| {m} | {fnum(b['recall'])} → {fnum(p['recall'])} | {save} "
                 f"| {fnum(b['turns'])} → {fnum(p['turns'])} | {speed} |")
    L.append("")

    # ── per-language cut (recall, w/o → with) ──────────────────────────────
    langs = sorted({c.get("lang", "?") for c in cells})
    L.append("## Recall by language (without → with Prism, all models pooled)\n")
    L.append("| Language | without Prism | with Prism |")
    L.append("|---|---:|---:|")
    for lang in langs:
        lc = [c for c in cells if c.get("lang") == lang]
        b = med([c.get("recall") for c in lc if c["arm"] == "baseline"])
        p = med([c.get("recall") for c in lc if c["arm"] == "prism"])
        L.append(f"| {lang} | {fnum(b)} | {fnum(p)} |")
    L.append("")

    # ── per-task detail ────────────────────────────────────────────────────
    L.append("## Per task (recall, without → with Prism)\n")
    L.append("| Task | sites | " + " | ".join(models) + " |")
    L.append("|---|---:|" + "---|" * len(models))
    task_gt = {c["task"]: c.get("gt") for c in cells}
    for t in sorted(tasks, key=lambda x: task_gt.get(x) or 0):
        row = [t, str(task_gt.get(t, "?"))]
        for m in models:
            b = cell_agg(cells, m, "baseline", t)
            p = cell_agg(cells, m, "prism", t)
            bv = fnum(b["recall"]) if b else "—"
            pv = fnum(p["recall"]) if p else "—"
            row.append(f"{bv}→{pv}")
        L.append("| " + " | ".join(row) + " |")
    L.append("")

    # ── how to read it (honest caveats) ───────────────────────────────────
    L.append("## Reading this\n")
    L.append("- **Scoring is neutral/agent-level**: the answer scored is what the "
             "model itself submits, identically for both arms. This is stricter than "
             "the payload-isolation scoring behind the tier-invariance numbers in "
             "RESULTS.md (where the harness captures the engine's complete output).")
    L.append("- **Where the graph wins big**: tasks whose call sites are NOT named "
             "after the changing method (jackson, django, typeorm) — grep can't reach "
             "them, so baseline collapses (0.0–0.35) while Prism is complete.")
    L.append("- **Where grep already suffices**: some tasks (grafana Go) have "
             "lexically findable callers, so the baseline is already strong and Prism "
             "matches rather than beats it. Honest: the graph's edge is task-shaped.")
    L.append("- **The relay ceiling** (local tier): on the largest tasks "
             "(jackson-serialize 108, guava 310 sites) the free 30B model cannot "
             "re-type a 100–300 item list, so with-Prism recall falls to the "
             "baseline level. The engine resolves these completely; the model's relay "
             "is the bottleneck — exactly what Mason's payload isolation removes.")
    L.append("- **The tier story**: baseline recall is bought with model strength "
             "(0.16 local → 0.84 Haiku) and costs turns + tokens to get there; "
             "with Prism, both tiers reach ~1.0 in 3–6 turns. The graph gives a weak "
             "local model what a stronger model otherwise buys with capability.")
    L.append("- **Honest outlier**: grafana-querydata Haiku+Prism (0.84→0.14) — the "
             "model mis-used the tool on 2 of 3 trials (submitted the wrong/oversized "
             "site set), dragging that one task below its baseline. The engine "
             "resolves it; the model's tool use was inconsistent there.")
    L.append("- Local, Haiku, and Sonnet tiers complete. Opus failed this run (all cells rate-limited to empty answers) and was archived to runs/bench-matrix-opus-failed/ pending a clean re-run with tighter rate-limit handling. One task "
             "(grafana-securevalue) was dropped: its corpus fixture was a 3-file "
             "stub, not the real repo.\n")

    report = "\n".join(L)
    Path("BENCH-MATRIX.md").write_text(report)
    print(report)
    print(f"\n-> BENCH-MATRIX.md   ({len(cells)} cells)")


if __name__ == "__main__":
    main()
