#!/usr/bin/env python3
"""Show exactly which change-impact sites the scorer counts as extra/missed.

Used 2026-09-06 to explain the ci_invariants "regression" after score.py
went strict: the engine output was byte-identical across three prism
versions; what moved was which sites the scorer excused. Prints, per task,
the sites the strict scorer calls `extra` (same symbol name, different
file — previously excused) and `missed` (found only by name in another
file — previously credited as a weak match).

Mirrors ci_invariants' own query derivation so the numbers agree with the
gate. Usage:
  python3 ci_site_diff.py --prism BIN [--corpus-root DIR] task-id [...]
"""
from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)


import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ci_invariants as ci  # noqa: E402
from schema import Answer, Site, Task  # noqa: E402
from score import score  # noqa: E402

JAVA_TS_PY = {
    "jackson-jsonnode-get": "jackson-databind", "jackson-settable-set": "jackson-databind",
    "jackson-writetypeprefix": "jackson-databind", "jackson-serializewithtype": "jackson-databind",
    "jackson-deserialize": "jackson-databind", "jackson-serialize": "jackson-databind",
    "typeorm-driver-escape": "typeorm", "django-quotename": "django",
    "guava-forwarding-delegate": "guava",
    "commons-collections-transformer-transform": "commons-collections",
}


def sites_for(prism: Path, tid: str, corpus_root: Path) -> tuple[list[str], Task]:
    task = Task.load(str(ci.HARNESS_DIR / "tasks" / "manual" / f"{tid}.json"))
    if tid in JAVA_TS_PY:
        workdir = ci.fetch_corpus(JAVA_TS_PY[tid], ci.CORPORA[JAVA_TS_PY[tid]], corpus_root)
        fqn = task.pr.split(":", 1)[1]
        query = (fqn.split("#", 1)[0].rsplit(".", 1)[-1] + "." + fqn.split("#", 1)[1]
                 if "#" in fqn else fqn)
        ci.index(prism, workdir)
        raw, _ = ci.engine_sites(prism, query, workdir)
        return raw, task
    corpus_key = ci.CORPUS_ALIAS.get(tid, tid)
    workdir = ci.fetch_corpus(corpus_key, ci.CORPORA[corpus_key], corpus_root)
    ci.index(prism, workdir)
    seen: dict[str, bool] = {}
    for q in ci.GO_QUERIES[tid]:
        raw, _ = ci.engine_sites(prism, q, workdir)
        for s in raw:
            seen[s] = True
    return list(seen), task


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prism", default=str(Path.home() / "bin" / "prism"))
    ap.add_argument("--corpus-root", default=str(Path.home() / ".cache/prism-research/ci-corpus"))
    ap.add_argument("tasks", nargs="+")
    a = ap.parse_args()
    for tid in a.tasks:
        raw, task = sites_for(Path(a.prism), tid, Path(a.corpus_root))
        card = score(task, Answer(sites=[Site.parse(s) for s in raw], complete=True), "engine", 1)
        print(f"== {tid}: recall={card.recall} weak_recall={card.weak_recall} "
              f"precision={card.precision} sites={len(raw)} gt={len(task.ground_truth)}")
        for s in card.missed:
            print(f"  MISSED {s}")
        for s in card.extra:
            print(f"  EXTRA  {s}")


if __name__ == "__main__":
    main()
