#!/usr/bin/env python3
"""PreToolUse hook for the prism_forced arm (2026-10-11): code discovery goes
through prism. Denies the Grep and Glob tools, and Bash commands that start a
search (grep, rg, ag, ack, find, git grep) at the head of a command. A grep that
filters piped output (`npx tsc | grep error`) is not discovery and is allowed.
Harness-only: this measures what happens when the agent has to use prism; it
is not shipped behaviour."""
import json
import re
import shlex
import sys

REASON = (
    "In this session code search goes through prism. Use "
    'prism(op="search", args={"terms":["a","b"], "scope":"text"}) for text '
    "(it runs ripgrep over the repo, same hits as grep; add \"paths\" or "
    '"glob" to narrow), op="lookup" for known symbols, op="change_impact" for '
    'every site of a symbol you change, op="read" for a file range. If prism is '
    'not callable yet, run ToolSearch("select:mcp__prism__prism") once.'
)
SEARCH = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "find"}


def heads(command: str):
    """First word of each command that does not read from a pipe."""
    for seg in re.split(r"&&|\|\||;|\n|\$\(|`", command):
        first = seg.split("|")[0].strip()
        words = first.split()
        while words and ("=" in words[0] and not words[0].startswith("-")):
            words = words[1:]  # FOO=bar cmd
        if words and words[0] in ("xargs", "time", "command", "sudo"):
            words = words[1:]
        # grep over a scratch file (a saved tsc log) is not code search
        try:
            parsed = shlex.split(first)
        except ValueError:
            parsed = words
        scratch = [w for w in parsed[1:] if not w.startswith("-")][1:]
        if scratch and all(w.startswith(("/tmp/", "/private/tmp/")) for w in scratch):
            continue
        if words:
            yield words[0].rsplit("/", 1)[-1], words[1:2]
        # xargs grep after a pipe is still a search over files
        for piped in seg.split("|")[1:]:
            w = piped.split()
            if len(w) >= 2 and w[0] == "xargs" and w[1] in SEARCH:
                yield w[1], []


def denied(tool: str, inp: dict) -> bool:
    if tool in ("Grep", "Glob"):
        return True
    if tool != "Bash":
        return False
    for head, rest in heads(inp.get("command", "")):
        if head in SEARCH or (head == "git" and rest[:1] == ["grep"]):
            return True
    return False


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    if denied(ev.get("tool_name", ""), ev.get("tool_input") or {}):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON}}))


if __name__ == "__main__":
    main()
