"""Re-score Java runs, normalizing line-number answers to enclosing methods.

The graph (prism) reports authoritative file:line, so graph-arm agents often
answer sites as "File.java:114" instead of "File.java:methodName". The scorer
matches on bare symbol, so a line number matches nothing -> a correct answer is
scored 0 (e.g. jackson-deserialize G.t4: 148 real sites, recall 0.0). This is a
graph-arm-specific penalty, not a real miss.

Fix: load the Spoon line->method index (oracle --index) and map any numeric
answer symbol to the *innermost* enclosing executable before scoring. Non-numeric
symbols pass through unchanged. Rewrites each ok run's scorecard fields in place.

Usage:
  python rescore_java.py --task tasks/jackson-deserialize.json \
      [--index java-oracle/jackson-lineindex.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema import Answer, Site, Task
from score import score

RUNS_DIR = Path(__file__).resolve().parent / "runs"
DEFAULT_INDEX = Path(__file__).resolve().parent / "java-oracle" / "jackson-lineindex.json"


def load_index(path: Path) -> dict[str, list]:
    return json.loads(path.read_text())


def line_to_method(index: dict, relpath: str, line: int) -> str | None:
    """Innermost enclosing executable name for (relpath, line), or None."""
    spans = index.get(relpath)
    if not spans:  # try basename match (agents cite paths loosely)
        base = Path(relpath).name
        for k, v in index.items():
            if Path(k).name == base:
                spans = v
                break
    if not spans:
        return None
    best = None
    best_size = None
    for s, e, name in spans:
        if s <= line <= e:
            size = e - s
            if best_size is None or size < best_size:
                best, best_size = name, size
    return best


def normalize(raw: str, index: dict) -> str:
    raw = raw.strip().strip("`").strip()
    relpath, _, sym = raw.rpartition(":")
    if sym.isdigit() and relpath:
        m = line_to_method(index, relpath, int(sym))
        if m:
            return f"{relpath}:{m}"
    return raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--index", default=str(DEFAULT_INDEX))
    args = ap.parse_args()

    task = Task.load(args.task)
    index = load_index(Path(args.index))
    base = RUNS_DIR / task.id
    dirs = [base] + [d for d in base.iterdir() if d.is_dir()] if base.exists() else []

    changed = 0
    for d in dirs:
        for f in sorted(d.glob("[TGV].t*.json")):
            rec = json.loads(f.read_text())
            if rec.get("status") != "ok":
                continue
            ans = rec.get("answer") or {}
            raw_sites = ans.get("sites", [])
            norm = [normalize(s, index) for s in raw_sites]
            answer = Answer(
                sites=[Site.parse(s) for s in norm if str(s).strip()],
                complete=bool(ans.get("complete", False)),
                unresolved=[str(u) for u in ans.get("unresolved", [])],
            )
            card = score(task, answer, rec["arm"], rec["trial"]).to_dict()
            before = rec.get("recall")
            rec.update(card)
            f.write_text(json.dumps(rec, indent=2) + "\n")
            if before != rec["recall"]:
                changed += 1
                print(f"  {f.parent.name}/{f.name}: recall {before} -> {rec['recall']}")
    print(f"[rescore_java] {task.id}: {changed} run(s) changed")


if __name__ == "__main__":
    main()
