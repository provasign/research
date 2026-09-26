#!/usr/bin/env python3
"""PostToolUse hook on mcp__prism__prism: record which (file, line-range)
windows prism has already delivered this session, so prism_read_guard.py can
block redundant native Read calls over the same ranges.

op=read gives an exact (file, from, to) in its own args -- no parsing needed.
op=lookup ALSO delivers a verbatim body (measured 2026-09-21, jackson-databind
pr6076: `lookup(name="JsonValueSerializer")` returned "file: ...\\nline: 36\\n
body: <full class text>", then the agent Read the same file at offsets 55 and
150 anyway -- a redundancy op=read-only tracking cannot catch, because this
was the agent's actual majority discovery pattern in that run, not op=read at
all). Parsed heuristically from the response text since lookup's structured
args don't carry a line range; a slightly-wrong end line under-tracks (safe:
worst case is an allowed redundant read) rather than over-tracks (which could
wrongly block a legitimate one).

Appends to .prism-read-tracker.json in the project dir (CLAUDE_PROJECT_DIR,
else the cwd; one file per worktree, one worktree per task). Entries carry the
session_id, and the guard ignores other sessions' entries.

Invalidation (PostToolUse on Edit/Write/MultiEdit/NotebookEdit/Bash): a range
prism delivered BEFORE the file changed no longer describes the file, yet the
guard kept denying Reads of it -- jackson pr5959 (2026-09-26): the agent edited
BeanDeserializer.java and stash-popped, then its Read at offset 1406 was denied
("You already have lines 1406-1480") and it re-fetched the same range through
prism.read. An edit tool drops that file's ranges; a Bash command that can
rewrite files wholesale (git checkout/stash/reset/apply/restore/..., patch,
sed -i, mv/cp, a formatter, a script that writes files, a redirect into a
repo path) drops ALL ranges -- conservative, since which files it touched
isn't knowable from the command line.
"""
import json
import os
import re
import sys
from pathlib import Path


def tracker_path() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".") / ".prism-read-tracker.json"


EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Bash commands that can change file contents without naming them to us.
REWRITE_RE = re.compile(r"""(?x)
    (?:^|[\s;&|(`])git(?:\s+-C\s+\S+|\s+-c\s+\S+)*\s+
        (?:checkout|switch|stash|reset|apply|am|restore|revert|cherry-pick|merge|rebase|pull|clean|mv|rm)\b
  | (?:^|[\s;&|(`])(?:patch|mv|cp|rsync|ln|rm|truncate|dd|unzip|tar|gofmt|goimports|
        prettier|black|ruff|isort|autopep8|clang-format|google-java-format|dos2unix)(?=\s|$)
  | (?:^|[\s;&|(`])(?:sed|perl|gsed)\s+(?:-\w*\s+)*-i
  | (?:^|[\s;&|(`])(?:go\s+fmt|go\s+generate|npx\s+prettier|npx\s+eslint\s+.*--fix|
        mvn\s+.*(?:spotless:apply|fmt:format|formatter:format))
  | \.write_text\s*\( | \.write\s*\( | open\s*\([^)]*['"][wa]\+?['"] | writeFileSync | fs\.writeFile
  | \btee\b
""")
# `> path` / `>> path` into anything but /dev/* or a temp dir.
REDIRECT_RE = re.compile(r"(?<![0-9&>])>>?\s*(?!&)(['\"]?)(?P<target>[^\s;&|'\"]+)")


def bash_rewrites_files(cmd: str) -> bool:
    if REWRITE_RE.search(cmd or ""):
        return True
    for m in REDIRECT_RE.finditer(cmd or ""):
        t = m.group("target")
        if not t.startswith(("/dev/", "/tmp/", "/private/tmp/", "/var/folders/", "$TMPDIR", "${TMPDIR")):
            return True
    return False


def invalidate(payload: dict, tracked: list) -> list:
    """The tracked ranges still valid after this Edit/Write/Bash call."""
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    if tool in EDIT_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not path:
            return []
        return [t for t in tracked if not _same_file(path, t["file"])]
    if tool == "Bash" and bash_rewrites_files(ti.get("command", "")):
        return []
    return tracked


def _same_file(path: str, tracked_file: str) -> bool:
    """path is absolute (Edit's file_path); tracked_file is what prism
    reported, usually repo-relative -- the guard's own endswith rule."""
    a, b = path.rstrip("/"), tracked_file.lstrip("./")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a.lstrip("/"))
LOOKUP_BLOCK_RE = re.compile(
    r"file:\s*(?P<file>\S+)\s*\nline:\s*(?P<line>\d+)\s*\nbody:\s*(?P<body>.*?)"
    r"(?=\nname:\s|\Z)", re.S)


def _response_text(tool_response) -> str:
    """Defensive extraction: tool_response may be a bare string, a list of
    {"type":"text","text":...} content blocks, or a dict wrapping either."""
    if tool_response is None:
        return ""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        if "content" in tool_response:
            return _response_text(tool_response["content"])
        return json.dumps(tool_response)
    if isinstance(tool_response, list):
        parts = []
        for item in tool_response:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(tool_response)


def main():
    payload = json.load(sys.stdin)
    tracker = tracker_path()
    if (payload.get("tool_name") or "") in EDIT_TOOLS + ("Bash",):
        if tracker.exists():
            tracked = json.loads(tracker.read_text())
            kept = invalidate(payload, tracked)
            if len(kept) != len(tracked):
                tracker.write_text(json.dumps(kept))
        return

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
    elif op == "lookup":
        text = _response_text(payload.get("tool_response"))
        for m in LOOKUP_BLOCK_RE.finditer(text):
            body_lines = m.group("body").count("\n") + 1
            start = int(m.group("line"))
            ranges.append((m.group("file"), start, start + body_lines - 1))

    if not ranges:
        return  # search/query results aren't verbatim line-range delivery; nothing to track

    tracked = json.loads(tracker.read_text()) if tracker.exists() else []
    sid = payload.get("session_id")
    for f, frm, to in ranges:
        tracked.append({"file": f, "from": frm, "to": to, "session_id": sid})
    tracker.write_text(json.dumps(tracked))


if __name__ == "__main__":
    main()
