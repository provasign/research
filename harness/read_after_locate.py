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
  located     prism had only named the file (search hit, caller list,
              location line) — the read fetched content prism never sent
  reread      the file was edited (Edit/Write/Bash) between delivery and
              the read — a necessary refresh
  cold        prism had said nothing about the file

The 2026-09-05 version counted any read of a file a prism result had named
as "after locate" (35/40 on v070sample), a window that advanced per tool
call, attributed bytes by filename, and missed root-level files. Those
counts were indicative only; this one is per assistant TURN, per tool-use
id, and separates "named" from "delivered".

Usage: python3 read_after_locate.py runs/wide/*.prism_plus.<tag>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import usage_account

PRISM_LOCATE = ("mcp__prism__prism_search", "mcp__prism__prism_change_impact",
                "mcp__prism__prism_verify")
PRISM_DELIVER = ("mcp__prism__prism_read", "mcp__prism__prism_lookup", "mcp__prism__prism_query",
                 "mcp__prism__prism_change_impact", "mcp__prism__prism_verify")
# A path: optional directories, a basename with an extension. Root-level
# files (main.go) match too; the shape must be followed by ':' , a line
# number or whitespace so prose words with dots are not paths.
_PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w-]+\.[A-Za-z]{1,5})(?=[:\s`)\]\",]|$)")
_WINDOW_LINE = re.compile(r"^\s*(\d+)\t", re.M)  # Read-shaped delivered source


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
        m = _WINDOW_LINE.match(line)
        if m and cur:
            out.setdefault(cur, set()).add(int(m.group(1)))
            continue
        ps = _PATH.findall(line)
        if ps:
            cur = ps[-1]
    return out


def _fingerprint_match(trace: dict) -> Path | None:
    for f in usage_account.PROJECTS.glob("*wide-*/*.jsonl"):
        counts: dict = {}
        for line in f.open(errors="ignore"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("type") != "assistant":
                continue
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    counts[c["name"]] = counts.get(c["name"], 0) + 1
        if counts == trace:
            return f
    return None


def analyze(transcript: Path) -> dict:
    turn = 0
    uses: dict[str, dict] = {}
    named: dict[str, int] = {}                 # file -> last turn prism named it
    delivered: dict[str, tuple[int, set[int]]] = {}  # file -> (turn, lines)
    edited: dict[str, int] = {}                # file -> last turn it was edited
    reads: list[dict] = []
    for line in transcript.open(errors="ignore"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("type") == "assistant":
            turn += 1  # one assistant message = one turn
            for c in ((j.get("message") or {}).get("content") or []):
                if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                    continue
                uses[c["id"]] = dict(c, turn=turn)
                if c["name"] in ("Edit", "Write"):
                    fp = str(c["input"].get("file_path", ""))
                    edited[fp] = turn
                elif c["name"] == "Bash":
                    cmd = str(c["input"].get("command", ""))
                    if any(k in cmd for k in ("sed -i", "git rm", "rm ", "mv ", ">")):
                        for p in _paths(cmd):
                            edited[p] = turn
        elif j.get("type") == "user":
            for c in ((j.get("message") or {}).get("content") or []):
                if not (isinstance(c, dict) and c.get("type") == "tool_result"):
                    continue
                u = uses.get(c.get("tool_use_id"))
                if not u:
                    continue
                text = _text(c)
                if u["name"] in PRISM_LOCATE:
                    for p in _paths(text):
                        named[p] = u["turn"]
                if u["name"] in PRISM_DELIVER:
                    for p, lines in _delivered_ranges(text).items():
                        prev = delivered.get(p, (0, set()))[1]
                        delivered[p] = (u["turn"], prev | lines)
                if u["name"] in ("Read", "mcp__prism__prism_read"):
                    fp = str(u["input"].get("file_path") or u["input"].get("file") or "")
                    rel = next((p for p in list(delivered) + list(named) if fp.endswith(p)), None)
                    off = int(u["input"].get("offset") or 1)
                    lim = int(u["input"].get("limit") or 0)
                    want = set(range(off, off + lim)) if lim else None
                    kind = "cold"
                    if rel and rel in delivered:
                        dt, lines = delivered[rel]
                        if edited.get(fp, 0) > dt or edited.get(rel, 0) > dt:
                            kind = "reread"
                        elif want is None or want <= lines:
                            kind = "duplicate"
                        else:
                            kind = "located"  # delivered, but not this range
                    elif rel and rel in named:
                        kind = "reread" if edited.get(fp, 0) > named[rel] else "located"
                    reads.append({"turn": u["turn"], "tool": u["name"], "file": fp,
                                  "kind": kind, "bytes": len(text),
                                  "gap": (u["turn"] - (delivered.get(rel, (named.get(rel, 0), set()))[0])) if rel else None})
    by = {}
    for r in reads:
        k = r["kind"]
        by.setdefault(k, [0, 0])
        by[k][0] += 1
        by[k][1] += r["bytes"]
    return {"turns": turn, "reads": len(reads), "by_kind": by, "detail": reads}


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
        print(f"{cell['task']:20} {cell.get('tag', cell['arm']):10} turns={a['turns']:3} reads={a['reads']:3}  {parts}"
              f"  cost=${cell.get('cost_usd') or 0:.2f}")


if __name__ == "__main__":
    main()
