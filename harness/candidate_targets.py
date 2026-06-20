"""Mine a go-ssa-vta truth file for *valid adversarial* impact-task candidates (W1).

The completeness effect lives on tasks where a method NAME is shared by many real
implementations reached through interface dispatch -- grep on the name over- or
under-matches, while the resolved graph is exact (the H2/H3 case). This ranks
callee names by (distinct implementations x callers x caller-packages) so we can
pick targets for `oracle_task.py`, after excluding generated/mock/test sites.

VALIDITY GUARDRAILS (see HANDOFF.md W1 -- do not relitigate):
  * This finds interface-impl-ENUMERATION candidates (many impls of one name).
    That is the valid adversarial. It is NOT the excluded concrete-caller design
    (one concrete method reached via a k8s-style interface = VTA-only, unfair to
    grep AND graph). Avoid `*.Get`-family targets for that reason.
  * Every candidate still needs a quick source check before it becomes a task:
    is the interface internal (changeable) and are the impls hand-written
    (no codegen/mock churn that would pollute ground truth)?

Usage:
  python candidate_targets.py --truth /tmp/grafana-truth.jsonl --top 30
  python candidate_targets.py --truth /tmp/grafana-truth.jsonl --min-impls 4 \
      --min-callers 8 --exclude-get
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

GEN = re.compile(r"(_gen|\.pb|mock|generated|\.gen)\.go$|/mocks?/|_test\.go$", re.I)
# Boilerplate names that are noise, not interface dispatch (constructors, codegen
# hooks, deepcopy). Targets here are almost never real change-impact tasks.
NOISE = {
    "New", "ProvideService", "GetOpenAPIDefinitions", "DeepCopyInto",
    "DeepCopyObject", "OpenAPIModelName",
}


def _pkg(relpath: str, depth: int = 3) -> str:
    return "/".join(relpath.split("/")[:depth])


def mine(truth_path: str) -> dict[str, dict]:
    impls: dict[str, set] = collections.defaultdict(set)
    callers: dict[str, set] = collections.defaultdict(set)
    caller_pkgs: dict[str, set] = collections.defaultdict(set)
    with open(truth_path) as f:
        for line in f:
            obj = json.loads(line)
            if "callee" not in obj or "caller" not in obj:
                continue  # header
            ce, ca = obj["callee"], obj["caller"]
            if GEN.search(ce["file"]):  # skip generated/mock/test *implementations*
                continue
            n = ce["name"]
            impls[n].add((ce["file"], ce["line"]))
            callers[n].add((ca["file"], ca["line"]))
            caller_pkgs[n].add(_pkg(ca["file"]))
    return {
        n: {
            "impls": len(impls[n]),
            "callers": len(callers[n]),
            "caller_pkgs": len(caller_pkgs[n]),
        }
        for n in impls
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--min-impls", type=int, default=4)
    ap.add_argument("--min-callers", type=int, default=8)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--exclude-get", action="store_true",
                    help="drop *.Get / Get (the concrete-caller-via-interface trap)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    stats = mine(args.truth)
    rows = []
    for n, s in stats.items():
        bare = n.rsplit(".", 1)[-1]
        if bare in NOISE:
            continue
        if args.exclude_get and bare == "Get":
            continue
        if s["impls"] < args.min_impls or s["callers"] < args.min_callers:
            continue
        rows.append((s["impls"], s["callers"], s["caller_pkgs"], n))
    rows.sort(reverse=True)
    rows = rows[: args.top]

    if args.json:
        print(json.dumps(
            [{"name": n, "impls": i, "callers": c, "caller_pkgs": p}
             for i, c, p, n in rows], indent=2))
        return
    print(f"{'impls':>5} {'callers':>7} {'callerpkgs':>10}  name")
    for i, c, p, n in rows:
        print(f"{i:>5} {c:>7} {p:>10}  {n}")
    print(f"\n{len(rows)} candidates. Validate each in source before "
          f"`oracle_task.py --target <name>`.")


if __name__ == "__main__":
    main()
