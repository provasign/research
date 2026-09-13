#!/usr/bin/env python3
"""What are the agents actually DOING in Bash?

Every A/B conclusion so far has been drawn from cost and turn counts, which
say an arm was more expensive without saying on what. This reads the cell
records and answers that: how much of each arm is shell work, what kind, how
much of it is the agent retrying itself, and how much got denied.

The first thing it turned up (v054-smoke-fixed, 2026-08-15): Bash is ~70% of
all tool calls in BOTH arms, and the largest Bash category is test-running and
Python environment wrangling -- not code navigation. A tool that changes how
an agent NAVIGATES is competing for a minority of the agent's actions, which
bounds how large any navigation effect can be in this benchmark.

Usage:
    python3 analyze_bash.py runs/swebench-live/v054-smoke-fixed
    python3 analyze_bash.py runs/swebench-live/ab38-t1 runs/swebench-live/ab38-f1

Reads tool_calls (full commands, runs after 2026-08-15) when present and falls
back to tool_trace (truncated to 120 chars) for older runs, so the historical
beds stay analysable -- with the truncation noted, because a category counted
off a clipped command is a weaker claim.
"""
from __future__ import annotations

import collections
import difflib
import json
import re
import sys
from pathlib import Path

# Ordered: first match wins, so the more specific patterns come first. This is
# a coarse bucketing meant for "where does the time go", not a parser -- a
# command can legitimately belong to two buckets (a pytest run that also sets
# PYTHONPATH is counted as a test run).
CATEGORIES = [
    ("test-run", r"\b(pytest|tox|unittest|nose2?)\b"),
    ("env-setup", r"\b(pip|venv|virtualenv|conda|poetry|uv)\b|which -a|command -v"
                  r"|PYTHONPATH=|site-packages|-c [\"']import "),
    ("search", r"(?:^|[\s;&|(])(?:grep|rg|ag|ack|find)\b"),
    ("read-file", r"(?:^|[\s;&|(])(?:cat|sed|head|tail|less|wc|nl)\b"),
    ("git", r"(?:^|[\s;&|(])git\b"),
    ("repro", r"python3?\s+-c\b|<<[\"']?EOF"),
    ("fs", r"(?:^|[\s;&|(])(?:ls|mkdir|rm|cp|mv|ln|touch|chmod)\b"),
]
RETRY_SIMILARITY = 0.80


def categorize(cmd: str) -> str:
    for name, pat in CATEGORIES:
        if re.search(pat, cmd):
            return name
    return "other"


def bash_commands(rec: dict) -> tuple[list[str], bool]:
    """Return (commands, truncated). Prefers tool_calls; falls back to the
    string trace for records written before argument capture landed."""
    if rec.get("tool_calls"):
        return ([str(c["input"].get("command", "")) for c in rec["tool_calls"]
                 if c["name"] == "Bash"], False)
    # tool_trace stores Bash entries as the raw command (clipped to 120) and
    # every other tool as a bare name; anything that looks like a tool name is
    # not a command.
    cmds = [t for t in rec.get("tool_trace", [])
            if not re.fullmatch(r"[A-Za-z_][\w]*|ToolSearch\(.*\)|mcp__\S+", str(t))]
    return (cmds, True)


def retry_runs(cmds: list[str]) -> tuple[int, int]:
    """Count maximal runs of consecutive near-identical commands.

    A retry loop is the agent re-issuing a command it just ran with a small
    edit -- the signature of fighting an environment rather than making
    progress. Returns (number of runs, redundant calls beyond the first).
    """
    runs = redundant = 0
    i = 0
    while i < len(cmds) - 1:
        j = i
        while (j + 1 < len(cmds)
               and difflib.SequenceMatcher(None, cmds[j], cmds[j + 1]).ratio() >= RETRY_SIMILARITY):
            j += 1
        if j > i:
            runs += 1
            redundant += j - i
            i = j + 1
        else:
            i += 1
    return runs, redundant


def analyse(run_dir: Path) -> None:
    cells = collections.defaultdict(dict)
    for f in run_dir.glob("*.json"):
        if f.name in ("prism_provenance.json",) or f.name.endswith(".predictions.jsonl"):
            continue
        try:
            rec = json.load(open(f))
        except (json.JSONDecodeError, IsADirectoryError):
            continue
        if "arm" in rec and "instance_id" in rec:
            cells[rec["instance_id"]][rec["arm"]] = rec
    if not cells:
        print(f"{run_dir}: no cell records found")
        return

    arms = sorted({a for t in cells for a in cells[t]})
    prov = run_dir / "prism_provenance.json"
    print(f"\n{'=' * 78}\n{run_dir}   {len(cells)} tasks, arms: {', '.join(arms)}")
    if prov.exists():
        p = json.load(open(prov))
        print(f"prism under test: {p['version']} sha256:{p['sha256'][:12]} "
              f"({p['mcp_tool_count']} MCP tools)")
    print("=" * 78)

    truncated = any(bash_commands(cells[t][a])[1] for t in cells for a in cells[t])
    if truncated:
        print("NOTE: this run predates argument capture — commands are clipped to")
        print("      120 chars, so categories are weaker than in newer runs.\n")

    stats = {a: collections.Counter() for a in arms}
    totals = {a: collections.Counter() for a in arms}
    for t in cells:
        for a, rec in cells[t].items():
            cmds, _ = bash_commands(rec)
            allcalls = len(rec.get("tool_calls") or rec.get("tool_trace") or [])
            totals[a]["bash"] += len(cmds)
            totals[a]["all"] += allcalls
            totals[a]["denied"] += len(rec.get("permission_denials") or [])
            r, red = retry_runs(cmds)
            totals[a]["retry_runs"] += r
            totals[a]["retry_calls"] += red
            for c in cmds:
                stats[a][categorize(c)] += 1

    print(f"{'':14}" + "".join(f"{a:>14}" for a in arms))
    print(f"{'bash / all':14}" + "".join(
        f"{str(totals[a]['bash']) + '/' + str(totals[a]['all']):>14}" for a in arms))
    print(f"{'bash share':14}" + "".join(
        f"{totals[a]['bash'] / max(totals[a]['all'], 1):>13.0%} " for a in arms))
    print()
    for name, _ in CATEGORIES + [("other", None)]:
        row = "".join(
            f"{str(stats[a][name]) + f'  ({stats[a][name] / max(totals[a]["bash"], 1):.0%})':>14}"
            for a in arms)
        print(f"{name:14}{row}")
    print()
    print(f"{'retry loops':14}" + "".join(
        f"{str(totals[a]['retry_runs']) + ' / ' + str(totals[a]['retry_calls']) + ' calls':>14}"
        for a in arms))
    print(f"{'denied':14}" + "".join(f"{totals[a]['denied']:>14}" for a in arms))

    # A grep/rg denial in a prism arm means the deny-config regression is back
    # (see swebench_ab.py's deployment note) and the run is not measuring the
    # shipped product. Loud, because it fails in the flattering direction.
    search_re = re.compile(r"(?:^|[\s;&|(])(?:[^\s;&|(]*/)?(?:sudo\s+)?(?:rg|grep)\b")
    bad = [(t, a) for t in cells for a in cells[t]
           for d in (cells[t][a].get("permission_denials") or [])
           if search_re.search(str(d.get("tool_input", {}).get("command", "")))]
    if bad:
        print(f"\n!! {len(bad)} grep/rg DENIALS — this run had search blocked; "
              f"adoption numbers are not comparable to a free-choice run:")
        for t, a in bad[:6]:
            print(f"     {t} :: {a}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for d in sys.argv[1:]:
        analyse(Path(d))


if __name__ == "__main__":
    main()
