"""Engine-ceiling A/B: Prism change_impact vs CodeGraph, no LLM.

For each task: derive the change-impact target the SAME way engine_ceiling.py
does (from the oracle `pr` field), run BOTH engines, and score their output
against the SAME oracle ground truth with the SAME scorer the agent arms use
(score.py). Recall = completeness (the task's axis).

Fairness:
  - CodeGraph is queried through `explore` — its HEADLINE tool, not the weaker
    `impact`/`callers` CLI. We extract every (symbol,file) it surfaces in the
    blast-radius section PLUS every name it ties to the target in the
    calls/references edges (symbol-only matches still count for recall — the
    scorer credits them, flagged weak). This maximizes CodeGraph's recall.
  - Same oracle, same scorer, same target as Prism.
  - Corpus checked out at the task's pin before indexing.

Usage:
  python codegraph_vs_prism.py tasks/jackson-*.json
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from schema import Answer, Site, Task
from score import score

PRISM = Path.home() / "bin" / "prism"
CODEGRAPH = Path.home() / ".local" / "bin" / "codegraph"


def prism_query(task: Task) -> str:
    fqn = task.pr.split(":", 1)[1]
    if "#" in fqn:
        type_part, mspec = fqn.split("#", 1)
        simple = type_part.rsplit(".", 1)[-1]
        return f"{simple}.{mspec}"
    return fqn


def bare_symbol(query: str) -> str:
    """Type.method(params) -> 'Type.method' (drop the param list) for CLI/explore."""
    return query.split("(", 1)[0]


# ---------------------------------------------------------------------------
# Prism arm
# ---------------------------------------------------------------------------
def prism_sites(query: str, workdir: Path) -> list[Site]:
    subprocess.run([str(PRISM), "index", "."], cwd=workdir, capture_output=True, text=True, timeout=600)
    r = subprocess.run([str(PRISM), "change-impact", query, "."],
                       capture_output=True, text=True, cwd=workdir, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"prism: {r.stderr[:300]}")
    data = json.loads(r.stdout)
    sites: list[Site] = []
    for group in ("declarations", "family", "callers", "declaringTypes"):
        for sym in data.get(group, []):
            fp = sym.get("filePath") or sym.get("file", "")
            name = sym.get("name", "")
            if name:
                sites.append(Site.parse(f"{fp}:{name}"))
    return sites


# ---------------------------------------------------------------------------
# CodeGraph arm (explore — the headline tool)
# ---------------------------------------------------------------------------
_BLAST = re.compile(r"^- `([^`]+)`\s*\(([^:)]+):\d+\)", re.M)   # - `get` (path:line)
_EDGE = re.compile(r"^- (\w[\w$]*)\s*(?:→|->)\s*(\w[\w$]*)", re.M)  # a → b


def codegraph_index(workdir: Path) -> None:
    if (workdir / ".codegraph").exists():
        return
    subprocess.run([str(CODEGRAPH), "init", "."], cwd=workdir,
                   capture_output=True, text=True, timeout=1200)


def codegraph_sites(bare: str, workdir: Path) -> list[Site]:
    codegraph_index(workdir)
    r = subprocess.run([str(CODEGRAPH), "explore", bare], cwd=workdir,
                       capture_output=True, text=True, timeout=300)
    txt = r.stdout
    target = bare.rsplit(".", 1)[-1]
    sites: list[Site] = []
    # (1) blast-radius entries carry symbol + file — strong sites.
    for sym, path in _BLAST.findall(txt):
        sites.append(Site.parse(f"{path}:{sym}"))
    # (2) call/reference edges touching the target contribute symbol-only sites
    #     (the scorer credits a symbol match even without a file, flagged weak).
    for a, b in _EDGE.findall(txt):
        if target in (a, b):
            other = b if a == target else a
            sites.append(Site.parse(other))
    return sites


# ---------------------------------------------------------------------------
def run_task(task_path: Path) -> dict | None:
    task = Task.load(task_path)
    if not task.workdir:
        return None
    workdir = Path(task.workdir or task.repo)
    if not workdir.exists():
        return {"task": task.id, "skip": f"corpus absent: {workdir}"}
    # pin the corpus for reproducibility
    subprocess.run(["git", "-C", str(workdir), "checkout", "-q", task.pin],
                   capture_output=True, text=True)
    q = prism_query(task)
    bare = bare_symbol(q)
    out = {"task": task.id, "lang": task.lang, "gt": len(task.ground_truth)}
    try:
        ps = prism_sites(q, workdir)
        out["prism_recall"] = round(score(task, Answer(sites=ps, complete=True), "prism", 1).recall, 3)
    except Exception as e:
        out["prism_recall"] = None
        out["prism_err"] = str(e)[:80]
    try:
        cs = codegraph_sites(bare, workdir)
        out["cg_recall"] = round(score(task, Answer(sites=cs, complete=True), "codegraph", 1).recall, 3)
    except Exception as e:
        out["cg_recall"] = None
        out["cg_err"] = str(e)[:80]
    return out


def main() -> None:
    rows = []
    for arg in sys.argv[1:]:
        r = run_task(Path(arg))
        if r is None:
            continue
        rows.append(r)
        if "skip" in r:
            print(f"  SKIP {r['task']}: {r['skip']}")
        else:
            print(f"  {r['task']:34} {r['lang']:6} GT={r['gt']:3}  "
                  f"prism={r.get('prism_recall')}  codegraph={r.get('cg_recall')}"
                  + (f"  [prism_err {r.get('prism_err')}]" if r.get('prism_err') else "")
                  + (f"  [cg_err {r.get('cg_err')}]" if r.get('cg_err') else ""))
    scored = [r for r in rows if r.get("prism_recall") is not None and r.get("cg_recall") is not None]
    if scored:
        pm = sum(r["prism_recall"] for r in scored) / len(scored)
        cm = sum(r["cg_recall"] for r in scored) / len(scored)
        print(f"\nMEAN over {len(scored)} scored tasks:  prism {pm:.3f}   codegraph {cm:.3f}")
    Path("runs").mkdir(exist_ok=True)
    json.dump(rows, open("runs/codegraph-engine/codegraph-vs-prism.json", "w"), indent=2)
    print("-> runs/codegraph-engine/codegraph-vs-prism.json")


if __name__ == "__main__":
    main()
