#!/usr/bin/env python3
"""A/B: does MCP schema deferral still stop agents from using prism?

Arm 'always' = alwaysLoad:true (what prism init writes since v0.55.0, ~2k
tokens of schemas in every session). Arm 'deferred' = no alwaysLoad — the
client defers schemas behind a ToolSearch hop (~92 tokens fixed).

The v0.55.0 measurement said cheap tiers stop reaching for prism when
deferred; that predates current models. If 'deferred' holds prism_used and
recall on today's haiku, alwaysLoad can be dropped from init: the largest
remaining fixed token cost, deleted with a one-line change.

Decision rule (fail fast, cheapest tasks first):
  - prism_used=False in 'deferred' where 'always' used it -> count a routing
    loss; >=2 routing losses -> FAIL (deferral still harmful), stop.
  - recall rules identical to ab_gate (hard drop >0.15 w/ one fresh retry).
  - PASS requires: routing losses <=1 AND mean recall drop <=0.05.

Usage: python ab_deferral.py --prism ~/bin/prism [--model haiku] [--limit N]
Exit 0 = deferral safe, 1 = deferral still harmful, 2 = harness error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_agentic_mcp as bed  # noqa: E402
import ab_gate  # noqa: E402
from schema import Task  # noqa: E402

import hashlib
import os


def ledger_path(root: Path) -> Path:
    # Mirrors prism's ledgerPathForRoot: sha1 of the absolute root under the
    # user cache dir. v0.56.8+ MCP sessions persist per-tool ResultCalls
    # there — our own instrumentation is the ground truth for "did the agent
    # actually call prism", which the claude CLI's summary JSON cannot say.
    key = hashlib.sha1(str(root.resolve()).encode()).hexdigest()
    cache = Path.home() / "Library/Caches"
    if not cache.exists():
        cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return cache / "prism" / "ledger" / f"{key}.json"


def tool_calls(root: Path) -> dict:
    try:
        d = json.loads(ledger_path(root).read_text())
    except Exception:
        return {}
    return {t: s.get("resultCalls", 0) for t, s in (d.get("byTool") or {}).items()}


def run_cell_measured(arm, task, corpus, model, out, prism, sha):
    f = out / f"{task.id}.{model}.{sha}.json"
    if f.exists():
        return json.loads(f.read_text())
    before = tool_calls(corpus)
    rec = ab_gate.run_cell(arm, task, corpus, model, out, prism, sha)
    after = tool_calls(corpus)
    calls = {t: after.get(t, 0) - before.get(t, 0)
             for t in after if after.get(t, 0) > before.get(t, 0)}
    rec["prism_calls"] = calls
    rec["prism_used"] = sum(calls.values()) > 0
    f.write_text(json.dumps(rec, indent=2))
    return rec


def arm_with_config(prism: str, tag: str, always_load: bool) -> str:
    cfg = Path(f"/tmp/ab-agentic-mcp/deferral-{tag}.json")
    cfg.parent.mkdir(exist_ok=True)
    server = {"type": "stdio", "command": str(Path(prism).resolve()), "args": ["mcp"]}
    if always_load:
        server["alwaysLoad"] = True
    cfg.write_text(json.dumps({"mcpServers": {"prism": server}}))
    name = f"deferral-{tag}"
    bed.ARMS[name] = dict(bed.ARMS["prism"], mcp=str(cfg))
    return name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prism", required=True)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--limit", type=int, default=len(ab_gate.TASKS))
    ap.add_argument("--out", default="runs/ab-deferral")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sha = ab_gate.binary_sha(args.prism)
    a_arm = arm_with_config(args.prism, "always", True)
    d_arm = arm_with_config(args.prism, "deferred", False)

    routing_losses = 0
    drops = []
    for tp in ab_gate.TASKS[: args.limit]:
        task = Task.load(tp)
        corpus = Path(task.workdir or task.repo)
        if not corpus.exists():
            print(f"SKIP {task.id}: corpus absent")
            continue
        a = run_cell_measured(a_arm, task, corpus, args.model, out, args.prism, f"al-{sha}")
        d = run_cell_measured(d_arm, task, corpus, args.model, out, args.prism, f"df-{sha}")

        def used(rec):
            v = rec.get("prism_used")
            return bool(v) if v is not None else None

        au, du = used(a), used(d)
        ar, dr = a.get("recall"), d.get("recall")
        print(f"{task.id:30} always: used={au} calls={sum((a.get('prism_calls') or {}).values())} recall={ar} | "
              f"deferred: used={du} calls={sum((d.get('prism_calls') or {}).values())} recall={dr}")

        if au and du is False:
            routing_losses += 1
            print(f"  ROUTING LOSS ({routing_losses})")
            if routing_losses >= 2:
                print("FAIL: deferral still stops prism usage (>=2 routing losses)")
                return 1
        if ar is not None and dr is not None:
            if dr < ar - ab_gate.HARD_RECALL_DROP:
                # one fresh retry, same policy as ab_gate
                print(f"  hard drop — one fresh retry")
                (out / f"{task.id}.{args.model}.df-{sha}.json").unlink(missing_ok=True)
                d = run_cell_measured(d_arm, task, corpus, args.model, out, args.prism, f"df-{sha}")
                dr = d.get("recall")
                print(f"  retry: recall={dr}")
                if dr is not None and dr < ar - ab_gate.HARD_RECALL_DROP:
                    print(f"FAIL (reproduced): recall {ar} -> {dr} on {task.id}")
                    return 1
            drops.append(ar - (dr if dr is not None else 0))

    if not drops:
        print("HARNESS ERROR: no scored pairs")
        return 2
    mean_drop = sum(drops) / len(drops)
    print(f"\npairs={len(drops)} routing losses={routing_losses} "
          f"mean recall delta={-mean_drop:+.3f}")
    if mean_drop > ab_gate.MEAN_RECALL_DROP:
        print("FAIL: deferred arm loses recall")
        return 1
    print("PASS: deferral safe on this bed — alwaysLoad droppable "
          "(worth a spot-check on one more model tier before shipping)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
