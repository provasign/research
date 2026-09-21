#!/usr/bin/env python3
"""PostToolUse hook on mcp__prism__prism: record which (file, line-range)
windows prism has already delivered this session, so prism_read_guard.py can
block redundant native Read calls over the same ranges.

Appends to .prism-read-tracker.json in the cwd (one file per worktree, one
worktree per task -- no session_id disambiguation needed).
"""
import json
import sys
from pathlib import Path

TRACKER = Path(".prism-read-tracker.json")


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}
    op = tool_input.get("op")
    args = tool_input.get("args") or {}

    ranges = []
    if op == "read":
        f = args.get("file")
        if f:
            frm = args.get("from") or 1
            to = args.get("to")
            if to:
                ranges.append((f, frm, to))
            for r in args.get("ranges") or []:
                if r.get("file"):
                    ranges.append((r["file"], r.get("from", 1), r.get("to", r.get("from", 1))))

    if not ranges:
        return  # search/lookup/query results aren't verbatim line-range delivery; nothing to track

    tracked = json.loads(TRACKER.read_text()) if TRACKER.exists() else []
    for f, frm, to in ranges:
        tracked.append({"file": f, "from": frm, "to": to})
    TRACKER.write_text(json.dumps(tracked))


if __name__ == "__main__":
    main()
