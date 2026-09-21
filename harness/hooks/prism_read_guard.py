#!/usr/bin/env python3
"""PreToolUse hook on Read: deny a native Read call whose requested line
range substantially overlaps a range prism already delivered this session
(tracked by prism_read_tracker.py in .prism-read-tracker.json).

Measured 2026-09-21 (overnight-run/INVESTIGATION.md): the single largest
fixable driver of prism-arm token blowup was re-reading content already
delivered by prism -- 6 native Read calls into a file prism had already
returned in full, all landing inside the already-delivered window. Advisory
steering ("do not re-read") didn't hold up over multi-turn sessions;
enforcement (deny + reason) is the one mechanism this project has repeatedly
measured to actually change tool-use behavior.

OVERLAP_THRESHOLD: deny only when the requested window is MOSTLY covered
(not just touches) an already-delivered range, so legitimate pagination past
the end of a capped prism read (e.g. lines 200-475 after a 1-200 delivery)
is never blocked.
"""
import json
import sys
from pathlib import Path

TRACKER = Path(".prism-read-tracker.json")
OVERLAP_THRESHOLD = 0.7  # fraction of the REQUESTED window that must already be covered


def overlap_fraction(req_from: int, req_to: int, cov_from: int, cov_to: int) -> float:
    lo = max(req_from, cov_from)
    hi = min(req_to, cov_to)
    if hi < lo:
        return 0.0
    req_len = req_to - req_from + 1
    return (hi - lo + 1) / req_len if req_len > 0 else 0.0


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    offset = tool_input.get("offset") or 1
    limit = tool_input.get("limit")
    req_to = (offset + limit - 1) if limit else offset + 1999  # unbounded read: treat as huge window

    if not TRACKER.exists():
        return  # nothing tracked yet, allow

    tracked = json.loads(TRACKER.read_text())
    best_cov, best_frac = None, 0.0
    for t in tracked:
        if not file_path.endswith(t["file"]):
            continue
        frac = overlap_fraction(offset, req_to, t["from"], t["to"])
        if frac > best_frac:
            best_frac, best_cov = frac, t

    if best_cov and best_frac >= OVERLAP_THRESHOLD:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"You already have lines {best_cov['from']}-{best_cov['to']} of "
                    f"{best_cov['file']} from an earlier prism result in this "
                    f"session -- scroll back to it instead of re-reading. If you need "
                    f"content past line {best_cov['to']}, request only that range."
                ),
            }
        }))


if __name__ == "__main__":
    main()
