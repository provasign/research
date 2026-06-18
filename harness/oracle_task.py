"""Build an impact task with compiler-grade ground truth (design §5, oracle).

Given a go-ssa-vta truth file (from `grove-eval truth`) and a target method
name, the ground truth for "change this method's signature, what must change?"
is computed *independently of grove*:

  ground_truth = every implementation matching the target name
               + every function that calls one of them (direct callers).

This is the design's primary, non-circular oracle: it can surface call sites a
PR diff or a grep on the method name would silently miss (the H2/H3 case), and
it is the only fair way to score recall on a distributed-dispatch task.

Usage:
  grove-eval truth --repo <repo> --commit <pin> --out truth.jsonl
  python oracle_task.py --truth truth.jsonl --repo <repo> --commit <pin> \
      --target Get --id grafana-secretsget --prompt "..." --out tasks/...json
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from schema import Site, Task
from score import _is_test_path


def _base(name: str) -> str:
    """Bare method name from a truth name like 'pkgType.Method' or 'Func'."""
    return name.rsplit(".", 1)[-1]


def load_edges(truth_path: str) -> list[dict]:
    edges = []
    for line in Path(truth_path).read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if "caller" in obj and "callee" in obj:
            edges.append(obj)
    return edges


def build(edges: list[dict], target: str, impl_scope: str = "",
          full: bool = False) -> tuple[list[Site], dict]:
    """Return (ground-truth sites, stats) for changing `target`'s signature.

    By default `target` matches a callee by bare-name (e.g. "Get" matches every
    `T.Get`). With `full=True` it matches the fully-qualified callee name
    exactly (e.g. "secureValueClient.Get") -- the right mode for changing one
    concrete method whose bare name is ambiguous across the repo. `impl_scope`
    (a repo-relative path prefix) is an alternative disambiguator (gin's
    `Context.Render` vs the `render.Render` interface: scope to `render/`).
    """
    impls: set[Site] = set()
    callers: set[Site] = set()
    impl_fns: set[str] = set()
    for e in edges:
        cn = e["callee"]["name"]
        if cn != target if full else _base(cn) != target:
            continue
        if impl_scope and not e["callee"]["file"].startswith(impl_scope):
            continue
        # Production change-site completeness is the headline; test/test-helper
        # callers are out of scope (consistent with the scorer's test-neutrality).
        if _is_test_path(e["caller"]["file"]):
            continue
        impls.add(Site(e["callee"]["file"], _base(e["callee"]["name"])))
        impl_fns.add(e["callee"]["name"])
        callers.add(Site(e["caller"]["file"], _base(e["caller"]["name"])))
    sites = sorted(impls | callers, key=str)
    stats = {
        "impl_count": len(impls),
        "distinct_impl_fns": len(impl_fns),
        "caller_count": len(callers),
        "files": len({s.relpath for s in sites}),
        "packages": len({str(Path(s.relpath).parent) for s in sites}),
    }
    return sites, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--commit", required=True, help="pin (the truth's commit)")
    ap.add_argument("--target", required=True,
                    help="bare method name (e.g. Get), or full Type.Method with --full")
    ap.add_argument("--full", action="store_true",
                    help="match the fully-qualified callee name exactly")
    ap.add_argument("--impl-scope", default="", dest="impl_scope",
                    help="repo-relative path prefix the implementations live "
                         "under (disambiguates same-named methods)")
    ap.add_argument("--id", required=True)
    ap.add_argument("--lang", default="go")
    ap.add_argument("--pr", default="")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--workdir", default="",
                    help="run in this existing checkout instead of a git worktree "
                         "(use when the repo's git dir is unavailable)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rp = subprocess.run(
        ["git", "-C", args.repo, "rev-parse", args.commit],
        capture_output=True, text=True,
    )
    pin = rp.stdout.strip() or args.commit  # tolerate a detached/odd git dir
    edges = load_edges(args.truth)
    sites, stats = build(edges, args.target, args.impl_scope, args.full)
    if not sites:
        raise SystemExit(f"no edges reference a method named {args.target!r}")
    Task(
        id=args.id, repo=args.repo, lang=args.lang, pin=pin,
        pr=args.pr or f"oracle:{args.target}", task_type="impact",
        prompt=args.prompt, ground_truth=sites, workdir=args.workdir,
    ).save(args.out)
    print(f"[oracle-task] {args.id}  target={args.target}  sites={len(sites)}  {stats}")
    print(f"       -> {args.out}")


if __name__ == "__main__":
    main()
