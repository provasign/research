#!/usr/bin/env python3
"""Strict scorer for the mandated-wide bed — one score per required change.

The original run_wide.score() credited a ground-truth file as "found" when
the agent's diff touched it at all, and a symbol as "found" when the string
appeared anywhere in the diff text (context lines and comments included).
The first replacement (2026-09-05 a.m.) scored (file, position) proximity,
which still counted a file with two required sites as done after one, and
credited a TODO comment dropped at the right line. Now:

  gold site     one contiguous hunk of `git diff -U0 base gold` in a gt file
                (hunks within TOL lines of each other merge into one site).
                sites_expected is the number of sites, not files.
  per site, four levels, each implying the previous (see score_site):
    proximity, removed, substituted, exact.
  site_recall   = substituted-level (old-contract line gone AND real code
                added in its place); exact/removed/proximity reported beside
                it. Measured on v070sample: agents' replacement lines differ
                textually from gold's on most sites of an otherwise complete
                sweep (dubbo__86dd98899b: exact 1/20, removed 17/20), so
                `exact` is a secondary signal, not the headline.
  symbol hit    the symbol appears in a +/- line of the agent's diff in a
                file where gold's +/- lines also carry it.

Also usable offline: `python3 wide_score.py runs/wide/<cell>.json [...]`
rescores stored cells (full diff from the .diff sidecar; cells stored under
the old 20k-char cap are flagged and their numbers are a LOWER bound).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SCORER_VERSION = 2
TOL = 3  # lines

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _norm(s: str) -> str:
    return " ".join(s.split())


class FileDiff:
    __slots__ = ("minus", "plus")

    def __init__(self) -> None:
        self.minus: list[tuple[int, str]] = []  # (old line, text)
        self.plus: list[tuple[int, str]] = []   # (old cursor, text)

    def positions(self) -> set[int]:
        return {p for p, _ in self.minus} | {p for p, _ in self.plus}


def parse_diff(text: str) -> dict[str, FileDiff]:
    """{file: FileDiff}. A '-' line carries its own old-side number; a '+'
    line carries the old-side cursor it inserts at. The old-side walk means
    -U0 and -U3 diffs of the same change agree. Deleted files keep their
    `--- a/` path."""
    out: dict[str, FileDiff] = {}
    cur: str | None = None
    old: int | None = None
    run_start: int | None = None  # first old line of the current '-' run
    for line in text.split("\n"):
        if line.startswith("diff --git"):
            cur, old, run_start = None, None, None
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
                out.setdefault(cur, FileDiff())
            old = None
            continue
        m = _HUNK.match(line)
        if m:
            old, run_start = int(m.group(1)), None
            continue
        if cur is None or old is None:
            continue
        if line.startswith("-"):
            if run_start is None:
                run_start = old
            out[cur].minus.append((old, line[1:]))
            old += 1
        elif line.startswith("+"):
            # A '+' directly after a '-' run REPLACES that run: attribute it
            # to the run's first line, so a one-line swap is one position.
            out[cur].plus.append((run_start if run_start is not None else old, line[1:]))
        elif line.startswith("\\"):
            pass  # "\ No newline at end of file"
        else:
            old += 1
            run_start = None
    return out


def gold_diff(task: dict) -> str:
    return subprocess.run(
        ["git", "-C", task["repo_path"], "diff", "-U0", task["base_commit"],
         task["gold_commit"]], capture_output=True, text=True, check=True).stdout


class Site:
    __slots__ = ("file", "lo", "hi", "minus", "plus")

    def __init__(self, file: str, pos: int) -> None:
        self.file, self.lo, self.hi = file, pos, pos
        self.minus: set[str] = set()
        self.plus: set[str] = set()

    def __str__(self) -> str:
        return f"{self.file}:{self.lo}" if self.lo == self.hi else f"{self.file}:{self.lo}-{self.hi}"


def gold_sites(gold: dict[str, FileDiff], gt_files: list[str]) -> list[Site]:
    """Contiguous change regions per gt file; edits within TOL merge."""
    sites: list[Site] = []
    for f in gt_files:
        fd = gold.get(f)
        if fd is None:
            continue
        events = sorted([(p, "-", t) for p, t in fd.minus] + [(p, "+", t) for p, t in fd.plus])
        cur: Site | None = None
        for p, kind, t in events:
            if cur is None or p > cur.hi + TOL:
                cur = Site(f, p)
                sites.append(cur)
            cur.hi = max(cur.hi, p)
            (cur.minus if kind == "-" else cur.plus).add(_norm(t))
    return sites


def _near(site: Site, items: list[tuple[int, str]]) -> list[str]:
    return [_norm(t) for p, t in items if site.lo - TOL <= p <= site.hi + TOL]


_COMMENT = re.compile(r"^\s*(//|#|/\*|\*|--|<!--|;)")

def _is_code(line: str) -> bool:
    return bool(line.strip()) and not _COMMENT.match(line)


LEVELS = ("missed", "proximity", "removed", "substituted", "exact")


def score_site(site: Site, agent: FileDiff | None) -> str:
    """One of LEVELS, each implying the ones before it:
      proximity    changed something within TOL of the site
      removed      a gold '-' line at the site is among the agent's '-' lines
                   (pure-addition sites: anything added nearby)
      substituted  removed AND a non-blank, non-comment '+' line nearby —
                   the headline. A TODO comment in place of the change stops
                   at `removed`; a real replacement whose text differs from
                   gold's (import order, formatting, an equivalent API form)
                   passes here and stops short of `exact`.
      exact        substituted AND a '+' line equals one gold added there
                   (pure deletions: exact == removed)"""
    if agent is None:
        return "missed"
    minus, plus = _near(site, agent.minus), _near(site, agent.plus)
    if not minus and not plus:
        return "missed"
    if site.minus:
        removed = any(m in site.minus for m in minus)
    else:
        removed = bool(plus)  # pure addition: something was added here
    if not removed:
        return "proximity"
    if not site.plus:
        return "exact"  # pure deletion: nothing to add
    # Code is required only where gold added code; a site whose whole
    # addition is a comment (gold-vs-gold self-test caught this) needs none.
    if any(_is_code(p) for p in site.plus) and not any(_is_code(p) for p in plus):
        return "removed"
    if any(p in site.plus for p in plus):
        return "exact"
    return "substituted"


def _has_word(sym: str, lines: list[str]) -> bool:
    rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(sym) + r"(?![A-Za-z0-9_])")
    return any(rx.search(l) for l in lines)


def score_diff(task: dict, agent_diff: str, gold: str | None = None,
               truncated: bool = False) -> dict:
    gold = gold if gold is not None else gold_diff(task)
    g, a = parse_diff(gold), parse_diff(agent_diff)
    gt = list(task["gt_files"])
    sites = gold_sites(g, gt)
    levels = {str(s): score_site(s, a.get(s.file)) for s in sites}
    n = len(sites)
    rank = {lv: i for i, lv in enumerate(LEVELS)}

    def at_least(lv: str) -> int:
        return sum(1 for v in levels.values() if rank[v] >= rank[lv])

    exact, subst, removed, prox = (at_least("exact"), at_least("substituted"),
                                   at_least("removed"), at_least("proximity"))
    files_hit = {s.file for s in sites if rank[levels[str(s)]] >= rank["substituted"]}
    extra = sorted(set(a) - set(gt))

    # Precision at the site level: every contiguous region the agent changed
    # (merged the same way gold sites are) that lies within TOL of NO gold
    # site is a false edit — including one inside an otherwise-correct file.
    # Until 2026-09-06 only whole extra files counted, so an agent that
    # edited the wrong place in the right file paid nothing.
    agent_regions = gold_sites(a, sorted(a))
    by_file: dict[str, list[Site]] = {}
    for s in sites:
        by_file.setdefault(s.file, []).append(s)
    false_regions = [r for r in agent_regions
                     if not any(g.lo - TOL <= r.hi and r.lo <= g.hi + TOL
                                for g in by_file.get(r.file, []))]
    site_precision = (round(subst / (subst + len(false_regions)), 3)
                      if subst + len(false_regions) else None)

    def lines(fd: FileDiff | None) -> list[str]:
        return [t for _, t in fd.minus] + [t for _, t in fd.plus] if fd else []

    syms = task.get("gt_symbols") or []
    sym_hit, sym_miss, sym_unscorable = [], [], []
    for s in syms:
        where = [f for f in gt if _has_word(s, lines(g.get(f)))]
        if not where:
            sym_unscorable.append(s)  # lives only in files outside gt (added ones)
        elif any(_has_word(s, lines(a.get(f))) for f in where):
            sym_hit.append(s)
        else:
            sym_miss.append(s)
    n_sym = len(sym_hit) + len(sym_miss)

    out = {
        "scorer_version": SCORER_VERSION,
        "site_recall": round(subst / n, 3) if n else None,
        "site_recall_exact": round(exact / n, 3) if n else None,
        "site_recall_removed": round(removed / n, 3) if n else None,
        "site_recall_proximity": round(prox / n, 3) if n else None,
        "sites_found": subst,
        "sites_expected": n,
        "sites_by_level": levels,
        "missed_sites": sorted(k for k, v in levels.items() if rank[v] < rank["substituted"]),
        "files_complete": len(files_hit),
        "files_expected_strict": len({s.file for s in sites}),
        "extra_files_strict": len(extra),
        "site_precision": site_precision,
        "false_edit_regions": len(false_regions),
        "false_edit_sites": sorted(str(r) for r in false_regions)[:40],
        "symbol_recall_strict": round(len(sym_hit) / n_sym, 3) if n_sym else None,
        "symbols_missed_strict": sym_miss,
        "symbols_unscorable": sym_unscorable,
        "diff_truncated": truncated,
    }
    if truncated:
        out["files_in_stored_diff"] = len(a)
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
        gold = golds.setdefault(task["instance_id"], gold_diff(task))
        s = score_diff(task, diff, gold, truncated)
        present = sum(1 for f in task["gt_files"] if f in parse_diff(diff))
        legacy_found = cell.get("files_found")
        s["files_unverifiable"] = (max(legacy_found - present, 0)
                                   if truncated and legacy_found is not None else 0)
        s.pop("sites_by_level", None)
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
              f"exact={r['site_recall_exact']} removed={r['site_recall_removed']} "
              f"prox={r['site_recall_proximity']} site_prec={r['site_precision']} "
              f"false_edits={r['false_edit_regions']} "
              f"sym={r['legacy_symbol_recall']}->{r['symbol_recall_strict']} "
              f"cost=${(r['cost_usd'] or 0):.2f}{flag}")
    print(json.dumps(rows, indent=1), file=open("wide-rescore.json", "w"))


if __name__ == "__main__":
    main()
