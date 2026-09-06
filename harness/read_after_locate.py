#!/usr/bin/env python3
"""Read-after-locate: the stage-2 decision metric.

For each prism result in a transcript (search/query/lookup/change_impact),
collect the repo-relative file paths it delivered. A later host `Read` of
one of those files within WINDOW assistant turns is a read-after-locate —
the agent had the location (and often the span) and fetched the whole file
anyway. 54% of the v070sample token excess was these Reads.

Reports per cell: prism results, files located, subsequent Reads that hit a
located file, and bytes those Reads returned. Cells are matched to their
transcript by session_id when the record has one (harness >= 2026-09-05)
or by tool_trace fingerprint for older cells.

Usage: python3 read_after_locate.py runs/wide/*.prism_plus.<tag>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import usage_account

WINDOW = 10
PRISM = ("mcp__prism__prism_search", "mcp__prism__prism_query",
         "mcp__prism__prism_lookup", "mcp__prism__prism_change_impact",
         "mcp__prism__prism_read")
# Text results ("path:line: text", **`path`**) and JSON results
# ("file":"path") both — the JSON shape was missed at first and zeroed
# prism_verify/change_impact located paths.
_PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z]{1,5})(?=[:\s`)\]\",]|$)")


def _paths(text: str) -> set[str]:
    return set(_PATH.findall(text))


def _result_text(c: dict) -> str:
    body = c.get("content")
    if isinstance(body, str):
        return body
    if isinstance(body, list):
        return "".join(x.get("text", "") for x in body if isinstance(x, dict))
    return ""


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
    turns = []  # (turn_idx, tool_use dict) in order
    results: dict[str, tuple[str, str]] = {}  # tool_use_id -> (name, text)
    events = []
    t = 0
    for line in transcript.open(errors="ignore"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("type") == "assistant":
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    t += 1
                    events.append((t, "use", c))
        elif j.get("type") == "user":
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    events.append((t, "result", c))
    uses = {c["id"]: c for _, k, c in events if k == "use"}
    located: list[tuple[int, str, set[str]]] = []  # (turn, tool, paths)
    reads = 0
    hits = []
    read_bytes = {}
    for turn, kind, c in events:
        if kind == "result":
            u = uses.get(c.get("tool_use_id"))
            if not u:
                continue
            if u["name"] in PRISM:
                p = _paths(_result_text(c))
                if p:
                    located.append((turn, u["name"], p))
            elif u["name"] == "Read":
                read_bytes[u["id"]] = len(_result_text(c))
        elif kind == "use" and c["name"] == "Read":
            reads += 1
            fp = str(c["input"].get("file_path", ""))
            for lt, tool, paths in located:
                if 0 <= turn - lt <= WINDOW and any(fp.endswith(p) for p in paths):
                    hits.append((turn, tool, fp, lt))
                    break
    return {
        "prism_results_with_paths": len(located),
        "reads": reads,
        "reads_after_locate": len(hits),
        "read_after_locate_bytes": sum(read_bytes.get(u["id"], 0) for _, k, u in events
                                       if k == "use" and u["name"] == "Read"
                                       and any(h[2] == str(u["input"].get("file_path", ""))
                                               for h in hits)),
        "read_bytes_total": sum(read_bytes.values()),
        "by_tool": {tool: sum(1 for h in hits if h[1] == tool) for _, tool, _ in located},
    }


def main() -> None:
    for p in sys.argv[1:]:
        cell = json.loads(Path(p).read_text())
        sid = (cell.get("usage") or {}).get("session_id")
        tp = usage_account.transcript_path(sid) if sid else _fingerprint_match(cell.get("tool_trace") or {})
        if tp is None:
            print(f"{cell['task']:20} {cell['arm']:10} no transcript")
            continue
        a = analyze(tp)
        rate = (a["reads_after_locate"] / a["reads"]) if a["reads"] else 0
        print(f"{cell['task']:20} {cell['arm']:10} prism_results={a['prism_results_with_paths']:3} "
              f"reads={a['reads']:3} after_locate={a['reads_after_locate']:3} ({rate:.0%}) "
              f"bytes={a['read_after_locate_bytes']//1000}k/{a['read_bytes_total']//1000}k "
              f"turns={cell.get('turns')} cost=${cell.get('cost_usd') or 0:.2f}")


if __name__ == "__main__":
    main()
