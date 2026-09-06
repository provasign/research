#!/usr/bin/env python3
"""Read-after-locate: classify every host Read against what prism had
already delivered for that file.

For each host `Read` (and `prism_read`) in a transcript, look back at the
prism results delivered before it and classify:

  duplicate   prism had already delivered SOURCE LINES of that file
              (prism_read / prism_lookup / prism_query windows / verify or
              change_impact site windows) covering the read range, and the
              file was not edited in between — the read fetched what the
              context already held
  located     prism named the file, but current full-range source coverage
              is not established (absent, partial, or invalidated coverage)
  reread      a successful Edit/Write changed the file after it was located
  cold        prism had said nothing about the file

The 2026-09-05 version counted any read of a file a prism result had named
as "after locate" (35/40 on v070sample), a window that advanced per tool
call, attributed bytes by filename, and missed root-level files. Those
counts were indicative only; this one is per assistant TURN, per tool-use
id, and separates "named" from "delivered".

Shell calls invalidate coverage but do not establish that any file changed.
Report freshness="unknown" separately; located_then_read retains the location
signal across all kinds. Do not infer historical changes from current mtimes
or assume a command can only modify paths literally present in its arguments.

Usage: python3 read_after_locate.py runs/wide/*.prism_plus.<tag>.json
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import usage_account

PRISM_LOCATE = ("mcp__prism__prism_search", "mcp__prism__prism_change_impact",
                "mcp__prism__prism_verify")
PRISM_DELIVER = ("mcp__prism__prism_search", "mcp__prism__prism_read", "mcp__prism__prism_lookup", "mcp__prism__prism_query",
                 "mcp__prism__prism_change_impact", "mcp__prism__prism_verify")
# A path: optional directories, a basename with an extension. Root-level
# files (main.go) match too; the shape must be followed by ':' , a line
# number or whitespace so prose words with dots are not paths.
_PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w-]+\.[A-Za-z]{1,5})(?=[:\s`)\]\",]|$)")
_WINDOW_LINE = re.compile(r"^\s*(\d+)(?:\t|[:-]\s)", re.M)
_INLINE_LINE = re.compile(r"^(?://\s*)?([^\s:]+\.[A-Za-z]{1,5}):(\d+)[:-]\s")


def _text(c: dict) -> str:
    body = c.get("content")
    if isinstance(body, str):
        return body
    if isinstance(body, list):
        return "".join(x.get("text", "") for x in body if isinstance(x, dict))
    return ""


def _paths(text: str) -> set[str]:
    return set(_PATH.findall(text))


def _delivered_ranges(text: str) -> dict[str, set[int]]:
    """{file: delivered line numbers} for source windows in a prism result.
    A window belongs to the most recent path mentioned before it."""
    out: dict[str, set[int]] = {}
    cur = None
    for line in text.split("\n"):
        inline = _INLINE_LINE.match(line)
        if inline:
            cur = inline.group(1)
            out.setdefault(cur, set()).add(int(inline.group(2)))
            continue
        m = _WINDOW_LINE.match(line)
        if m and cur:
            out.setdefault(cur, set()).add(int(m.group(1)))
            continue
        ps = _PATH.findall(line)
        if ps:
            cur = ps[-1]
    return out


def _fingerprint_match(trace: dict) -> Path | None:
    matches = []
    for f in usage_account.PROJECTS.glob("*wide-*/*.jsonl"):
        counts = usage_account.analyze_transcript(f)["tool_calls"]
        if counts == trace:
            matches.append(f)
    return matches[0] if len(matches) == 1 else None


def _same_file(a: str, b: str) -> bool:
    a, b = a.replace("\\", "/"), b.replace("\\", "/")
    return a == b or (not b.startswith("/") and a.endswith("/" + b)) or (
        not a.startswith("/") and b.endswith("/" + a))


def analyze(transcript: Path) -> dict:
    turn = 0
    turns: dict[str, int] = {}
    uses: dict[str, dict] = {}
    results: set[str] = set()
    named: dict[str, int] = {}
    delivered: dict[str, tuple[int, set[int]]] = {}
    edited: dict[str, int] = {}
    uncertain: dict[str, int] = {}
    reads: list[dict] = []
    for line in usage_account.transcript_lines(transcript):
        try:
            j = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(j, dict) or j.get("parent_tool_use_id") or j.get("isSidechain"):
            continue
        if j.get("subtype") == "compact_boundary" or j.get("type") == "summary":
            delivered.clear()
        if j.get("type") == "assistant":
            message = j.get("message") or {}
            mid = message.get("id")
            if mid not in turns or not mid:
                turn += 1
                if mid:
                    turns[mid] = turn
            current = turns.get(mid, turn)
            for c in message.get("content") or []:
                if not (isinstance(c, dict) and c.get("type") == "tool_use" and c.get("id")):
                    continue
                tid = c["id"]
                if tid in uses:
                    continue
                u = uses[tid] = dict(c, turn=current)
                args = c.get("input") or {}
                fp = str(args.get("file_path") or args.get("file") or "")
                if c["name"] in ("Edit", "Write", "Bash"):
                    affected = set(delivered) | set(named)
                    u["edit_paths"] = []
                    for key in affected:
                        if c["name"] == "Bash" or _same_file(fp, key):
                            delivered.pop(key, None)
                            uncertain[key] = current
                            if c["name"] != "Bash":
                                u["edit_paths"].append(key)
                if c["name"] in ("Read", "mcp__prism__prism_read"):
                    matches = [p for p in set(delivered) | set(named) if _same_file(fp, p)]
                    rel = fp if fp in matches else matches[0] if len(matches) == 1 else None
                    off = int(args.get("offset") or 1)
                    lim = int(args.get("limit") or 0)
                    prior = named.get(rel, 0)
                    kind = "cold"
                    freshness = "unseen"
                    if rel in delivered:
                        dt, lines = delivered[rel]
                        prior = dt
                        # An unbounded whole-file request cannot be proven covered
                        # by a partial source window.
                        covered = lim > 0 and off > 0 and lim <= len(lines) and all(
                            n in lines for n in range(off, off + lim))
                        kind = "duplicate" if covered else "located"
                        freshness = "no_observed_change"
                    elif rel in named:
                        kind = "reread" if edited.get(rel, 0) >= prior else "located"
                        freshness = "changed" if kind == "reread" else (
                            "unknown" if rel in uncertain else "no_observed_change")
                    # Freeze classification before this read's result arrives.
                    u["read"] = {"turn": current, "tool_use_id": tid, "tool": c["name"],
                                 "file": fp, "kind": kind, "freshness": freshness,
                                 "located_before_read": rel in named,
                                 "gap": current - prior if rel else None}
        elif j.get("type") == "user":
            for c in ((j.get("message") or {}).get("content") or []):
                if not (isinstance(c, dict) and c.get("type") == "tool_result"):
                    continue
                tid = c.get("tool_use_id")
                u = uses.get(tid)
                if not u or tid in results:
                    continue
                results.add(tid)
                text = _text(c)
                if "read" in u:
                    reads.append(dict(u["read"], bytes=len(text.encode("utf-8")), error=bool(c.get("is_error"))))
                if c.get("is_error"):
                    continue
                for p in u.get("edit_paths", []):
                    edited[p] = u["turn"]
                if u["name"] in PRISM_LOCATE or u["name"] in PRISM_DELIVER:
                    for p in _paths(text):
                        named[p] = u["turn"]
                if u["name"] in PRISM_DELIVER:
                    for p, lines in _delivered_ranges(text).items():
                        if max(edited.get(p, 0), uncertain.get(p, 0)) >= u["turn"]:
                            continue
                        previous = delivered.get(p, (0, set()))[1]
                        delivered[p] = (u["turn"], previous | lines)
                        uncertain.pop(p, None)
    by = {}
    by_freshness = {}
    located_then_read = {"reads": 0, "bytes": 0}
    for r in reads:
        k = r["kind"]
        by.setdefault(k, [0, 0])
        by[k][0] += 1
        by[k][1] += r["bytes"]
        by_freshness.setdefault(r["freshness"], [0, 0])
        by_freshness[r["freshness"]][0] += 1
        by_freshness[r["freshness"]][1] += r["bytes"]
        if r["located_before_read"]:
            located_then_read["reads"] += 1
            located_then_read["bytes"] += r["bytes"]
    return {"analysis_version": 3, "turns": turn, "reads": len(reads), "by_kind": by,
            "by_freshness": by_freshness, "located_then_read": located_then_read, "detail": reads}


def main() -> None:
    for p in sys.argv[1:]:
        cell = json.loads(Path(p).read_text())
        sid = (cell.get("usage") or {}).get("session_id")
        tp = usage_account.transcript_path(sid) if sid else _fingerprint_match(cell.get("tool_trace") or {})
        if tp is None:
            print(f"{cell['task']:20} {cell['arm']:10} no transcript")
            continue
        a = analyze(tp)
        parts = "  ".join(f"{k}={n}/{b // 1000}k" for k, (n, b) in sorted(a["by_kind"].items()))
        parts += (f"  located_then_read={a['located_then_read']['reads']}"
                  f"  freshness_unknown={a['by_freshness'].get('unknown', [0, 0])[0]}")
        cost = cell.get("cost_usd")
        price = f"${cost:.2f}" if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0 else "unknown"
        print(f"{cell['task']:20} {cell.get('tag', cell['arm']):10} turns={a['turns']:3} reads={a['reads']:3}  {parts}"
              f"  cost={price}")


if __name__ == "__main__":
    main()
