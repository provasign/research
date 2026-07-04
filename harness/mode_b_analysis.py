"""Mode B analysis: expected compile failures from recall deficit.

A change-impact task requires updating every listed site. A site missed
by the agent == a method call or override that still uses the old signature
== a compile error. This script computes, for each run, how many sites
would be broken in the build if the agent's answer were applied as-is.

No code modification required — the oracle miss set is deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
TASKS_DIR = Path(__file__).resolve().parent / "tasks"

TASKS = [
    "jackson-jsonnode-get",
    "jackson-settable-set",
    "jackson-writetypeprefix",
    "jackson-serializewithtype",
    "jackson-deserialize",
    "jackson-serialize",
]

SYSTEMS = [
    ("Opus+T",       "opus",                 "T.t1.json"),
    ("Sonnet+T",     "sonnet",               "T.t1.json"),
    ("Haiku+T",      "haiku",                "T.t1.json"),
    ("Haiku+G*",     "haiku",                "Gstar.t1.json"),
    ("Sonnet+G*",    "sonnet",               "Gstar.t1.json"),
    ("Opus+G*",      "opus",                 "Gstar.t1.json"),
    ("Local30B+G*",  "qwen3-coder-30b-gstar","L.t1.json"),
]

# ── load ground truth ──────────────────────────────────────────────────────

def load_gt(task_id: str) -> set[str]:
    f = TASKS_DIR / f"{task_id}.json"
    return set(json.loads(f.read_text())["ground_truth"])


# ── load a single run ──────────────────────────────────────────────────────

def load_run(task_id: str, model_dir: str, fname: str) -> dict | None:
    f = RUNS / task_id / model_dir / fname
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    if d.get("violation"):
        return None
    return d


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    gt: dict[str, set[str]] = {t: load_gt(t) for t in TASKS}
    sizes = {t: len(gt[t]) for t in TASKS}

    # ── per-system aggregate table ─────────────────────────────────────────
    print("\n=== MODE B: Expected compile failures per system (mean over 6 tasks) ===\n")
    print(f"{'System':<22}  {'mean recall':>11}  {'avg missed':>10}  {'any miss':>8}  {'zero-miss tasks':>15}")
    print("-" * 75)

    for label, model_dir, fname in SYSTEMS:
        recalls, missed_counts, zero_miss = [], [], 0
        for task_id in TASKS:
            d = load_run(task_id, model_dir, fname)
            if d is None:
                continue
            found = set(d.get("found", []))
            missed = gt[task_id] - found
            recalls.append(d["recall"])
            missed_counts.append(len(missed))
            if len(missed) == 0:
                zero_miss += 1

        if not recalls:
            continue
        mean_r = sum(recalls) / len(recalls)
        avg_missed = sum(missed_counts) / len(missed_counts)
        any_miss = sum(1 for m in missed_counts if m > 0)
        print(f"{label:<22}  {mean_r:>11.3f}  {avg_missed:>10.1f}  {any_miss:>8}/6  {zero_miss:>15}/6")

    # ── per-task breakdown for the two key comparators ─────────────────────
    print("\n=== PER-TASK breakdown: missed sites (= expected compile errors) ===\n")
    print(f"{'task':<28}  {'|GT|':>5}", end="")
    key_systems = [
        ("Opus+T",      "opus",                 "T.t1.json"),
        ("Haiku+G*",    "haiku",                "Gstar.t1.json"),
        ("Local30B+G*", "qwen3-coder-30b-gstar","L.t1.json"),
    ]
    for label, _, _ in key_systems:
        print(f"  {label:>12}", end="")
    print()
    print("-" * (28 + 7 + 3 * 14))

    for task_id in TASKS:
        sz = sizes[task_id]
        row = f"{task_id:<28}  {sz:>5}"
        for _, model_dir, fname in key_systems:
            d = load_run(task_id, model_dir, fname)
            if d is None:
                row += f"  {'  ---':>12}"
                continue
            missed = len(gt[task_id] - set(d.get("found", [])))
            row += f"  {missed:>12}"
        print(row)

    # ── the headline numbers ───────────────────────────────────────────────
    print("\n=== HEADLINE: worst-case task (jackson-deserialize, 104 sites) ===\n")
    for label, model_dir, fname in SYSTEMS:
        d = load_run("jackson-deserialize", model_dir, fname)
        if d is None:
            continue
        missed = gt["jackson-deserialize"] - set(d.get("found", []))
        cost = d.get("cost", {}).get("total_cost_usd", 0) or 0
        turns = d.get("cost", {}).get("num_turns", 0) or 0
        cost_str = "free" if cost == 0 else f"${cost:.2f}"
        print(f"  {label:<22}  recall={d['recall']:.3f}  missed={len(missed):>3}  "
              f"cost={cost_str:>6}  turns={turns}")

    print()


if __name__ == "__main__":
    main()
