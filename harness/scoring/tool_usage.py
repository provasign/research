"""Tool usage per benchmark cell, from the agent's session transcript.

Recorded on every cell by run_e2e (rec["tool_usage"]) and usable after the
fact on any results directory:

    python3 scoring/tool_usage.py results/e2e-minimal [--arms native,prism_init] [--model claude-sonnet-5-5]

Prism calls are counted per op; native calls are grouped by what they do
(search, read, edit, build/test, other) so both arms read on one scale.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

TEST_CMD = re.compile(r"pytest|go test|mvn |gradle|npm (run )?test|vitest|jest|tox|cargo test|go build|go vet|tsc\b|npx |uv run|python3? -m")
SEARCH_CMD = re.compile(r"(^|[\s;&|(])(grep|rg|find|git grep|ag)\s")
READ_CMD = re.compile(r"(^|[\s;&|(])(cat|sed -n|head|tail|nl|less)\s")
EDIT_CMD = re.compile(r"sed -i|perl -pi|tee |> ?[\w./-]+\.\w+\s*$")
PRISM_TOOL = "mcp__prism__prism"


def _transcript(session_id: str) -> Path | None:
    hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl"))
    return Path(hits[0]) if hits else None


def usage(session_id: str | None) -> dict:
    """Counts of tool calls in one session: prism ops, native groups, totals."""
    out = {"prism_ops": {}, "native": {}, "prism_calls": 0, "tool_calls": 0, "transcript": False}
    if not session_id:
        return out
    path = _transcript(session_id)
    if path is None:
        return out
    out["transcript"] = True
    ops, native = Counter(), Counter()
    for line in path.open():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        for part in (d.get("message") or {}).get("content") or []:
            if not isinstance(part, dict) or part.get("type") != "tool_use":
                continue
            name, inp = part.get("name", ""), part.get("input") or {}
            out["tool_calls"] += 1
            if name == PRISM_TOOL:
                ops[str(inp.get("op") or "?")] += 1
                continue
            if name.startswith("mcp__prism__"):
                ops[name[len("mcp__prism__"):]] += 1  # legacy multi-tool surface
                continue
            if name in ("Grep", "Glob"):
                native["search"] += 1
            elif name == "Read":
                native["read"] += 1
            elif name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                native["edit"] += 1
            elif name.lower() == "bash":
                cmd = inp.get("command", "")
                if TEST_CMD.search(cmd):
                    native["build/test"] += 1
                elif EDIT_CMD.search(cmd):
                    native["edit"] += 1
                elif SEARCH_CMD.search(cmd):
                    native["search"] += 1
                elif READ_CMD.search(cmd):
                    native["read"] += 1
                else:
                    native["bash other"] += 1
            else:
                native[name] += 1
    out["prism_ops"] = dict(ops)
    out["native"] = dict(native)
    out["prism_calls"] = sum(ops.values())
    return out


def summarize(results_dir: str, arms: list[str] | None = None, model: str | None = None) -> None:
    by_arm: dict[str, list[dict]] = {}
    for f in sorted(glob.glob(os.path.join(results_dir, "*.json"))):
        try:
            rec = json.load(open(f))
        except ValueError:
            continue
        if not isinstance(rec, dict) or "arm" not in rec:
            continue
        if arms and rec["arm"] not in arms:
            continue
        if model and rec.get("model") != model:
            continue
        u = rec.get("tool_usage") or usage(rec.get("session_id"))
        u["resolved"] = bool(rec.get("resolved"))
        u["turns"] = rec.get("turns") or 0
        by_arm.setdefault(rec["arm"], []).append(u)
    for arm, cells in sorted(by_arm.items()):
        n = len(cells)
        seen = sum(1 for c in cells if c["transcript"])
        print(f"== {arm}: {n} cells ({seen} with transcripts), resolved {sum(c['resolved'] for c in cells)}/{n}, "
              f"turns {sum(c['turns'] for c in cells) / n:.1f}")
        ops = Counter()
        used = Counter()
        for c in cells:
            ops.update(c["prism_ops"])
            used.update({op: 1 for op in c["prism_ops"]})
        if ops:
            print(f"   prism calls/cell {sum(ops.values()) / n:.1f}; by op (calls/cell, % of cells using it):")
            for op, v in ops.most_common():
                print(f"      {op:14} {v / n:5.2f}   {100 * used[op] / n:4.0f}%")
        else:
            print("   no prism calls")
        nat = Counter()
        for c in cells:
            nat.update(c["native"])
        print("   native calls/cell: " + ", ".join(f"{k} {v / n:.1f}" for k, v in nat.most_common()))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    arms = model = None
    if "--arms" in args:
        arms = args[args.index("--arms") + 1].split(",")
    if "--model" in args:
        model = args[args.index("--model") + 1]
    summarize(args[0], arms, model)
