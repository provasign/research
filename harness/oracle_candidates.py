"""Rank adversarial impact-task targets from a go-ssa-vta truth file.

The pilot showed implementation *count* alone doesn't defeat grep (gin's tidy
`render.Render`); what does is **findability** — a method whose impls/callers
are scattered across many packages AND whose name is ambiguous (grep
over-matches). This ranks methods by those factors so we pick targets where the
graph should actually beat text.

Usage:
  python oracle_candidates.py --truth /tmp/grafana-truth.jsonl [--top 25]
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def _base(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    edges = [
        json.loads(l) for l in Path(args.truth).read_text().splitlines()
        if l.strip() and '"caller"' in l
    ]
    impl_files = collections.defaultdict(set)   # method -> {callee files}
    impl_types = collections.defaultdict(set)    # method -> {callee qualified names}
    callers = collections.defaultdict(set)       # method -> {caller funcs}
    caller_pkgs = collections.defaultdict(set)   # method -> {caller dirs}
    for e in edges:
        m = _base(e["callee"]["name"])
        impl_files[m].add(e["callee"]["file"])
        impl_types[m].add(e["callee"]["name"])
        callers[m].add(e["caller"]["name"])
        caller_pkgs[m].add(str(Path(e["caller"]["file"]).parent))

    rows = []
    for m in impl_files:
        nfiles = len(impl_files[m])          # impl spread
        ntypes = len(impl_types[m])          # distinct same-named methods (ambiguity)
        ncallers = len(callers[m])
        npkgs = len(caller_pkgs[m])          # caller package spread
        # Adversarial score: reward scattered callers across packages and
        # name ambiguity (many distinct same-named methods => grep over-matches).
        score = ncallers * npkgs * max(1, ntypes)
        rows.append((score, m, nfiles, ntypes, ncallers, npkgs))

    rows.sort(reverse=True)
    print(f"{'score':>8}  {'method':<28}{'implFiles':>10}{'sameName':>9}"
          f"{'callers':>8}{'callerPkgs':>11}")
    for score, m, nf, nt, nc, npkgs in rows[: args.top]:
        print(f"{score:>8}  {m:<28}{nf:>10}{nt:>9}{nc:>8}{npkgs:>11}")


if __name__ == "__main__":
    main()
