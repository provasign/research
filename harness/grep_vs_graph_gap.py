"""How often does the graph know something a text search does NOT?

The question behind the "volunteer the blast radius" design: when an agent
greps for a symbol name, is the answer it gets already complete? If text
search almost always finds every real reference, a graph has nothing to
volunteer and the feature is pointless. If the two sets diverge often, the
size of that divergence is what is currently dropped on the floor every time
an agent greps instead of asking the graph.

Deterministic, no LLM, no agent. For each sampled symbol:

  TEXT  = rg -w <leafname>  -> {(file, line)}     (what the agent sees)
  GRAPH = prism references  -> {(file, line)}     (resolved references)

  graph_only = GRAPH - TEXT   the sites a grep-driven agent never sees
  text_only  = TEXT  - GRAPH   grep hits that are not resolved references
                               (same name, other type / comments / strings)

Both directions matter to the design: graph_only is a completeness gap worth
announcing ("grep found 6, the graph resolves 20"); text_only is a noise
level worth announcing ("200 hits, 8 are real references").

Symbols are sampled from the repo's own index, production files only,
excluding trivially-short names (<4 chars) whose grep hits are meaningless.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
from pathlib import Path

PRISM = str(Path.home() / "bin" / "prism")
TEST_RE = re.compile(r"(^|/)(tests?|testing)/|_test\.|test_|\.test\.|spec\.", re.I)


def sh(*a, cwd=None, timeout=120):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.stdout


def sample_symbols(repo: Path, n: int, seed: int) -> list[dict]:
    """Methods/functions from the repo's index, production files only.

    Sampled straight from Grove's sqlite index — an UNBIASED draw over the
    repo's real symbols. (Sampling via prism_search seed words would bias
    the set toward whatever words were seeded, which is exactly the kind of
    selection effect this measurement is trying to avoid.)
    """
    import sqlite3
    db = repo / ".grove" / "grove.db"
    if not db.exists():
        sh(PRISM, "index", str(repo), timeout=900)
    if not db.exists():
        return []
    con = sqlite3.connect(str(db))
    syms = [{"name": r[0], "qualifiedName": r[1] or r[0], "file": r[2], "kind": r[3]}
            for r in con.execute(
                "select name, qualified_name, file_path, kind from symbols "
                "where kind in ('method','function')")]
    con.close()
    cands = []
    seen = set()
    for s in syms:
        name = s.get("name") or ""
        kind = s.get("kind") or ""
        fp = s.get("filePath") or s.get("file") or ""
        if kind not in ("method", "function"):
            continue
        if len(name) < 4 or TEST_RE.search(fp) or not fp:
            continue
        qn = s.get("qualifiedName") or name
        if qn in seen:
            continue
        seen.add(qn)
        cands.append({"name": name, "qualifiedName": qn, "file": fp})
    random.Random(seed).shuffle(cands)
    return cands[:n]


def text_sites(repo: Path, leaf: str) -> set:
    """What `rg -w <leaf>` shows an agent: whole-word hits, prod files."""
    out = sh("rg", "--no-config", "--line-number", "--no-heading", "--color=never",
             "--word-regexp", "--fixed-strings", "-e", leaf, "--", ".", cwd=str(repo), timeout=120)
    sites = set()
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            continue
        f = parts[0].lstrip("./")
        if TEST_RE.search(f):
            continue
        sites.add((f, int(parts[1])))
    return sites


def graph_sites(repo: Path, qn: str) -> set | None:
    out = sh(PRISM, "references", qn, "--format", "json", str(repo), timeout=180)
    try:
        d = json.loads(out)
    except Exception:
        return None
    sites = set()
    for f, refs in (d.get("byFile") or {}).items():
        if TEST_RE.search(f):
            continue
        for r in refs:
            if isinstance(r, dict) and r.get("line"):
                sites.add((f, int(r["line"])))
    return sites


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--per-repo", type=int, default=25)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="runs/grep-vs-graph-gap.json")
    a = ap.parse_args()

    rows = []
    for rp in a.repos:
        repo = Path(rp).expanduser()
        if not repo.exists():
            print(f"SKIP {repo}: missing"); continue
        syms = sample_symbols(repo, a.per_repo, a.seed)
        print(f"{repo.name}: {len(syms)} symbols sampled")
        for s in syms:
            g = graph_sites(repo, s["qualifiedName"])
            if g is None or not g:
                continue  # unresolvable name: nothing to compare, not a finding
            t = text_sites(repo, s["name"])
            rows.append({
                "repo": repo.name, "symbol": s["qualifiedName"], "leaf": s["name"],
                "text": len(t), "graph": len(g),
                "graph_only": len(g - t), "text_only": len(t - g),
            })
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rows, indent=2))

    if not rows:
        print("no comparable symbols"); return
    n = len(rows)
    with_gap = [r for r in rows if r["graph_only"] > 0]
    noisy = [r for r in rows if r["text_only"] > 2 * r["graph"] and r["graph"] > 0]
    print(f"\n{n} symbols compared across {len({r['repo'] for r in rows})} repos")
    print(f"  graph knows sites grep missed : {len(with_gap)}/{n} "
          f"({100*len(with_gap)/n:.0f}%), median extra = "
          f"{sorted(r['graph_only'] for r in with_gap)[len(with_gap)//2] if with_gap else 0}")
    print(f"  grep noise > 2x real refs     : {len(noisy)}/{n} ({100*len(noisy)/n:.0f}%)")
    tot_t = sum(r["text"] for r in rows); tot_g = sum(r["graph"] for r in rows)
    print(f"  totals: text hits {tot_t}, resolved refs {tot_g}, "
          f"graph-only {sum(r['graph_only'] for r in rows)}, "
          f"text-only {sum(r['text_only'] for r in rows)}")
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
