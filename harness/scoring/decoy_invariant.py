#!/usr/bin/env python3
"""Decoy invariant: comments and docstrings must not change the code graph.

Copies a corpus twice, injects code-shaped comments (and Python docstrings)
into every source file of one copy, indexes both with prism and requires the
two graphs to be identical: same symbols (file, kind, qualified name,
modifiers, exported flag) and same edges (source, type, target), compared by
name because injected lines shift spans and ids.

The decoys carry what the 2026-10-10 parsing audit found being read as code:
class/extends/implements text, calls, constructor calls, field declarations,
trait `use`, `#include`, crate paths, NotImplementedError, apostrophes and
lone quotes that desync hand-written lexers. A comment cannot change what a
program means, so any graph difference is a bug.

Usage:
  python decoy_invariant.py --prism /path/to/prism --injector /path/to/decoy <corpus_dir> [...]
Also called from ci_invariants.py (check_decoy_invariance).
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BLOB_SHA = re.compile(r"@[0-9a-f]{40}")  # synthesized member ids carry the file's blob sha
LINE_SUFFIX = re.compile(r"@\d+")  # anonymous symbols are named by line: `<anonymous@28>`, `func@12`


def inject(injector: Path, root: Path) -> int:
    """Decoy every source file under root in place with astkit's cmd/decoy,
    which places decoys only where the line ends in code (textmask-checked),
    so a decoy never lands inside a literal or changes the program."""
    r = subprocess.run([str(injector), str(root)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"decoy injector failed: {r.stderr[-400:]}")
    return int(r.stdout.strip() or 0)


def load_graph(repo: Path):
    db = sqlite3.connect(repo / ".grove" / "grove.db")
    db.text_factory = lambda b: b.decode("utf-8", "replace")
    syms = {}
    for sid, fp, kind, qn, mods, exp in db.execute(
            "select id,file_path,kind,qualified_name,modifiers,exports from symbols"):
        syms[sid] = (fp, kind, LINE_SUFFIX.sub("@L", qn), mods, exp)
    name = lambda n: f"{syms[n][0]}::{syms[n][2]}#{syms[n][1]}" if n in syms else BLOB_SHA.sub("@sha", n)
    edges = collections.Counter()
    meta = {}
    for f, t, et, src, conf in db.execute("select from_node,to_node,edge_type,source,confidence from edges"):
        k = (name(f), et, name(t))
        edges[k] += 1
        meta[k] = (src, conf)
    return collections.Counter(syms.values()), edges, meta


def index(prism: Path, repo: Path) -> None:
    r = subprocess.run([str(prism), "index", "--allow-heuristic", "."], cwd=repo,
                       capture_output=True, text=True, timeout=3600)
    if r.returncode not in (0, 3):
        raise RuntimeError(f"prism index failed in {repo}: {r.stderr[-600:]}")


def check_repo(prism: Path, injector: Path, src: Path, examples: int = 8, keep: bool = False) -> list[str]:
    work = Path(tempfile.mkdtemp(prefix="decoy-"))
    clean, decoy = work / "clean", work / "decoy"
    ignore = shutil.ignore_patterns(".git", ".grove", "node_modules")
    shutil.copytree(src, clean, ignore=ignore, symlinks=True)
    shutil.copytree(src, decoy, ignore=ignore, symlinks=True)
    n = inject(injector, decoy)
    index(prism, clean)
    index(prism, decoy)
    cs, ce, cm = load_graph(clean)
    ds, de, dm = load_graph(decoy)
    failures = []
    for label, a, b in (("symbols only in decoy", ds, cs), ("symbols missing in decoy", cs, ds)):
        d = a - b
        if d:
            failures.append(f"{src.name}: {sum(d.values())} {label}")
            for k in list(d)[:examples]:
                print(f"    {label}: {k[0]}::{k[2]} ({k[1]}) mods={k[3]} exported={k[4]}")
    for label, a, b, m in (("edges only in decoy", de, ce, dm), ("edges missing in decoy", ce, de, cm)):
        d = a - b
        if d:
            by = collections.Counter(k[1] for k in d)
            failures.append(f"{src.name}: {sum(d.values())} {label} {dict(by)}")
            for k in list(d)[:examples]:
                print(f"    {label}: {k[0]} -{k[1]}-> {k[2]} {m[k]}")
    print(f"  {src.name}: {n} files decoyed; symbols {sum(cs.values())}/{sum(ds.values())}, "
          f"edges {sum(ce.values())}/{sum(de.values())}  [{'OK' if not failures else 'MISMATCH'}]")
    if keep:
        print(f"  kept: {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prism", required=True)
    ap.add_argument("--injector", required=True,
                    help="astkit cmd/decoy binary (go install github.com/provasign/astkit/cmd/decoy@<tag>)")
    ap.add_argument("--keep", action="store_true", help="keep the clean/decoy copies for inspection")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("corpus", nargs="+")
    args = ap.parse_args()
    failures = []
    for c in args.corpus:
        failures += check_repo(Path(args.prism).resolve(), Path(args.injector).resolve(), Path(c).resolve(), args.examples, args.keep)
    if failures:
        print("FAILED:")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("Decoy invariant held.")


if __name__ == "__main__":
    main()
