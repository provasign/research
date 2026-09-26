#!/usr/bin/env python3
"""PreToolUse hook on Bash and WebFetch, installed for EVERY run_e2e arm:
deny fetching from the upstream code host.

Each task is a merged upstream PR, so the fix is one request away. Measured
2026-09-26: a sweep50 prism cell ran `gh pr diff 3466 --repo pallets/click`
(the task's own PR) and resolved; another ran
`curl -s https://github.com/psf/requests/pull/7315.diff`. The worktree has no
remote and no post-base refs (run_e2e._worktree), but the network was open.

A Bash command is denied when one shell segment both FETCHES (curl, wget,
httpie, git clone/fetch/pull/ls-remote/remote add/submodule, go get/install,
pip/uv/npm/pnpm/yarn/bun install from a URL, an HTTP library call inside
python/node -c) and names a code host (github.com, *.githubusercontent.com,
api.github.com, codeload.github.com, gitlab.com); and any `gh` subcommand that
talks to the host (pr, api, issue, repo, release, search, browse, ...) is
denied outright. Heredoc bodies are dropped first: agents write Go files with
`import "github.com/..."` through `cat <<EOF`, and that must stay allowed.
Mentioning a URL without fetching it (echo, grep, a comment) stays allowed.
WebFetch to those hosts is denied; other WebFetch (go.dev playground links an
issue cites) stays allowed.
"""
import json
import re
import sys
from urllib.parse import urlparse

REASON = ("The upstream repository (its pull requests, issues, commits and "
          "releases on GitHub/GitLab) is off-limits for this task. Work from the "
          "local checkout only.")

HOST_RE = re.compile(r"(?i)(?<![\w.-])(?:[\w-]+\.)*(?:github\.com|githubusercontent\.com|"
                     r"gitlab\.com)(?![\w-])")
HOSTS = ("github.com", "githubusercontent.com", "gitlab.com")

FETCH_RE = re.compile(r"""(?ix)
    (?:^|[\s(`'"=])(?:curl|wget|https?|aria2c|lynx|links|w3m)(?=\s|$)
  | (?:^|[\s(`])git(?:\s+-C\s+\S+|\s+-c\s+\S+)*\s+
        (?:clone|fetch|pull|ls-remote|remote\s+(?:add|set-url)|submodule|archive\s+--remote)\b
  | (?:^|[\s(`])go\s+(?:get|install|mod\s+download)\b
  | (?:^|[\s(`])(?:pip3?|uv\s+pip|uv|python3?\s+-m\s+pip|npm|pnpm|yarn|bun|npx|bunx)\s+
        (?:install|i|add|download|dlx|x)\b
  | urllib | urlopen | urlretrieve | http\.client | \brequests\.(?:get|post|request|Session)
  | \bhttpx\b | \baiohttp\b | \bfetch\s*\( | \baxios\b | \bhttps?\.(?:get|request)\s*\(
  | \bnet/http\b | \bhttp\.Get\s*\( | \bInvoke-WebRequest\b
""")

# gh subcommands that reach the host. `gh --version`/`gh help` stay allowed.
GH_RE = re.compile(r"(?:^|[\s;&|(`])gh\s+(?:-R\s+\S+\s+|--repo[\s=]\S+\s+)?"
                   r"(?:pr|api|issue|repo|release|search|browse|gist|run|workflow|"
                   r"cache|codespace|label|project|ruleset|secret|variable|attestation|"
                   r"status|org)\b")

HEREDOC_RE = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][\w-]*)\2")
SEGMENT_SPLIT = re.compile(r"\|\||&&|[;|\n]")


def strip_heredocs(cmd: str) -> str:
    """Drop heredoc bodies (the lines after `<<TAG` up to the TAG line)."""
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        tags = [(m.group(1), m.group(3)) for m in HEREDOC_RE.finditer(line)]
        i += 1
        for dash, tag in tags:
            while i < len(lines):
                body = lines[i].lstrip("\t") if dash else lines[i]
                i += 1
                if body.strip() == tag:
                    break
    return "\n".join(out)


def bash_blocked(cmd: str) -> bool:
    text = strip_heredocs(cmd or "")
    if GH_RE.search(text):
        return True
    return any(FETCH_RE.search(seg) and HOST_RE.search(seg)
               for seg in SEGMENT_SPLIT.split(text))


def url_blocked(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in HOSTS)


def decide(payload: dict):
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    if tool == "Bash" and bash_blocked(ti.get("command", "")):
        return REASON
    if tool == "WebFetch" and url_blocked(ti.get("url", "")):
        return REASON
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    reason = decide(payload)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    main()
