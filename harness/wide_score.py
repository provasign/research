#!/usr/bin/env python3
"""Strict scorer for the mandated-wide bed — site identity, not file identity.

The original run_wide.score() credited a ground-truth file as "found" when
the agent's diff touched it at all, and a symbol as "found" when the string
appeared anywhere in the diff text (context lines and comments included).
Both are false-credit paths: a file edited in the wrong place, or a name
that merely survives in a context line, scored the same as the real change.

Here a site is (file, old-line position) against the SAME base commit both
diffs are taken from:

  gold sites   positions changed by `git diff -U0 base gold` in each gt file
  agent sites  positions changed by the agent's diff (any context width —
               the parser walks the old-side cursor, so -U3 and -U0 agree)
  site hit     a gt file counts when at least one agent change lands within
               TOL lines of a gold change IN THAT FILE. Touching the file
               elsewhere is not a hit.
  symbol hit   the symbol appears in a +/- line of the agent's diff in a file
               where gold's +/- lines also carry it (context lines never count)

Also usable offline: `python3 wide_score.py runs/wide/<cell>.json [...]`
rescores stored cells. Cells whose stored diff was truncated (the 20k-char
cap in effect before 2026-09-05) are flagged — their strict numbers are a
LOWER bound, and the number of legacy-credited files that are simply not
present in the surviving diff is reported as `files_unverifiable`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TOL = 3  # lines; a hunk whose old-side span is within this of a gold change

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(text: str) -> tuple[dict[str, set[int]], dict[str, list[str]]]:
    """({file: old-line positions changed}, {file: +/- line bodies}).

    A '-' line marks its own old-side line; a '+' line marks the old-side
    cursor it inserts at, so pure insertions still get a location. Deleted
    files (`+++ /dev/null`) keep their `--- a/` path.
    """
    pos: dict[str, set[int]] = {}
    lines: dict[str, list[str]] = {}
    cur: str | None = None
    old: int | None = None
    for line in text.split("\n"):
        if line.startswith("diff --git"):
            cur, old = None, None
            continue
        if line.startswith("--- "):
            p = line[4:].split("\t")[0].strip()
            if p != "/dev/null":
                cur = p[2:] if p.startswith("a/") else p
            continue
        if line.startswith("+++ "):
            p = line[4:].split("\t")[0].strip()
            if p != "/dev/null":
                cur = p[2:] if p.startswith("b/") else p
            if cur is not None:
                pos.setdefault(cur, set())
                lines.setdefault(cur, [])
            old = None
            continue
        m = _HUNK.match(line)
        if m:
            old = int(m.group(1))
            continue
        if cur is None or old is None:
            continue
        if line.startswith("-"):
            pos[cur].add(old)
            lines[cur].append(line[1:])
            old += 1
        elif line.startswith("+"):
            pos[cur].add(old)
            lines[cur].append(line[1:])
        elif line.startswith("\\"):
            pass  # "\ No newline at end of file"
        else:
            old += 1
    return pos, lines


def gold_diff(task: dict) -> str:
    return subprocess.run(
        ["git", "-C", task["repo_path"], "diff", "-U0", task["base_commit"],
         task["gold_commit"]], capture_output=True, text=True, check=True).stdout


def _near(gold: set[int], agent: set[int]) -> bool:
    if not gold or not agent:
        return False
    if gold & agent:
        return True
    lo, hi = min(agent) - TOL, max(agent) + TOL
    cand = [g for g in gold if lo <= g <= hi]
    return any(abs(g - a) <= TOL for g in cand for a in agent)


def _has_word(sym: str, body: list[str]) -> bool:
    rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(sym) + r"(?![A-Za-z0-9_])")
    return any(rx.search(l) for l in body)


def score_diff(task: dict, agent_diff: str, gold: str | None = None,
               truncated: bool = False) -> dict:
    gold = gold if gold is not None else gold_diff(task)
    gpos, glines = parse_diff(gold)
    apos, alines = parse_diff(agent_diff)
    gt = [f for f in task["gt_files"]]
    scored = [f for f in gt if gpos.get(f)]  # gt files gold actually changed
    hit = [f for f in scored if _near(gpos[f], apos.get(f, set()))]
    touched_only = [f for f in scored if f in apos and f not in hit]
    extra = sorted(set(apos) - set(gt))

    # A symbol is scorable only where gold's own +/- lines in a gt file carry
    # it. gt_symbols was mined from the whole commit, so some names live only
    # in ADDED files (unscored by construction) — scoring those against the
    # gt files would put the ceiling below 1.0 (self-test: gold vs gold hit
    # 0.714 on prism__4f22f3947c before this exclusion).
    syms = task.get("gt_symbols") or []
    sym_hit, sym_miss, sym_unscorable = [], [], []
    for s in syms:
        where = [f for f in gt if _has_word(s, glines.get(f, []))]
        if not where:
            sym_unscorable.append(s)
        elif any(_has_word(s, alines.get(f, [])) for f in where):
            sym_hit.append(s)
        else:
            sym_miss.append(s)
    syms = [s for s in syms if s not in sym_unscorable]

    out = {
        "site_recall": round(len(hit) / len(scored), 3) if scored else None,
        "sites_found": len(hit),
        "sites_expected": len(scored),
        "missed_sites": sorted(set(scored) - set(hit)),
        "touched_not_at_site": touched_only,
        "extra_files_strict": len(extra),
        "symbol_recall_strict": round(len(sym_hit) / len(syms), 3) if syms else None,
        "symbols_missed_strict": sym_miss,
        "symbols_unscorable": sym_unscorable,
        "diff_truncated": truncated,
    }
    if truncated:
        # The tail of a truncated diff is a partial file; everything after it
        # is unknown. Report so the reader sees a lower bound, not a number.
        out["files_in_stored_diff"] = len(apos)
    return out


# --- offline rescore of stored cells --------------------------------------

def _task_for(cell: dict, tasks_dir: Path) -> dict:
    p = tasks_dir / f"{cell['task']}.json"
    if not p.exists():
        p = tasks_dir / f"{cell['task']}.json.excluded"
    return json.loads(p.read_text())


def rescore(paths: list[str], tasks_dir: str = "tasks-wide") -> list[dict]:
    golds: dict[str, str] = {}
    rows = []
    for p in paths:
        cell = json.loads(Path(p).read_text())
        task = _task_for(cell, Path(tasks_dir))
        side = Path(p).with_suffix(".diff")
        diff = side.read_text() if side.exists() else cell.get("diff", "")
        truncated = not side.exists() and len(diff) >= 20000
        g = golds.setdefault(task["instance_id"], gold_diff(task))
        s = score_diff(task, diff, g, truncated)
        legacy_found = cell.get("files_found")
        apos, _ = parse_diff(diff)
        present = sum(1 for f in task["gt_files"] if f in apos)
        s["files_unverifiable"] = (max(legacy_found - present, 0)
                                   if truncated and legacy_found is not None else 0)
        rows.append({"cell": Path(p).name, "task": cell["task"], "arm": cell["arm"],
                     "legacy_file_recall": cell.get("file_recall"),
                     "legacy_symbol_recall": cell.get("symbol_recall"),
                     "turns": cell.get("turns"), "cost_usd": cell.get("cost_usd"),
                     **s})
    return rows


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    rows = rescore(sys.argv[1:])
    for r in rows:
        flag = (f" TRUNCATED(unverifiable={r['files_unverifiable']})"
                if r["diff_truncated"] else "")
        print(f"{r['task']:20} {r['arm']:10} file={r['legacy_file_recall']} "
              f"site={r['site_recall']} ({r['sites_found']}/{r['sites_expected']}) "
              f"touched_not_site={len(r['touched_not_at_site'])} "
              f"sym={r['legacy_symbol_recall']}->{r['symbol_recall_strict']} "
              f"cost=${(r['cost_usd'] or 0):.2f}{flag}")
    print(json.dumps(rows, indent=1), file=open("wide-rescore.json", "w"))


if __name__ == "__main__":
    main()
