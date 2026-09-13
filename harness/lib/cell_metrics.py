"""Auditable navigation metrics derived from an agent's recorded tool events."""
from __future__ import annotations

import json
from pathlib import Path


def _content_bytes(value: object) -> int:
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, list):
        return sum(_content_bytes(part.get("text", "")) for part in value
                   if isinstance(part, dict) and part.get("type") == "text")
    return 0


def claude_navigation_metrics(path: Path) -> dict:
    """Count actual MCP and native Read calls, using recorded results for bytes.

    A Read is an edit prerequisite only if the next tool call is an Edit of
    the same file. This deliberately narrow definition leaves ambiguous reads
    in discovery rather than claiming the edit forced them.
    """
    calls: list[dict] = []
    results: dict[str, int] = {}
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                calls.append(block)
            elif block.get("type") == "tool_result":
                results[block.get("tool_use_id", "")] = _content_bytes(block.get("content"))

    ops: list[str] = []
    reads = edits = read_bytes = prerequisite = whole_file = 0
    for i, call in enumerate(calls):
        name = str(call.get("name", ""))
        args = call.get("input") or {}
        if name == "mcp__prism__prism":
            ops.append(str(args.get("op", "unknown")))
        elif name.startswith("mcp__prism__"):
            ops.append(name.removeprefix("mcp__prism__").removeprefix("prism_"))
        if name in ("Edit", "Write"):
            edits += 1
        if name != "Read":
            continue
        reads += 1
        read_bytes += results.get(call.get("id", ""), 0)
        if args.get("limit") is None:
            whole_file += 1
        if i + 1 < len(calls):
            following = calls[i + 1]
            if (following.get("name") == "Edit" and
                    (following.get("input") or {}).get("file_path") == args.get("file_path")):
                prerequisite += 1
    after_search = False
    followup = False
    for op in ops:
        if after_search and op in ("read", "lookup"):
            followup = True
        if op == "search":
            after_search = True
    return {
        "prism_mcp_calls": len(ops), "prism_op_sequence": ops,
        "prism_second_call_read_or_lookup": (len(ops) > 1 and ops[0] == "search"
                                             and ops[1] in ("read", "lookup")),
        "prism_followup_read_or_lookup": followup,
        "native_read_calls": reads, "native_whole_file_reads": whole_file,
        "native_edit_prerequisite_reads": prerequisite,
        "native_discovery_reads": reads - prerequisite,
        "native_read_kib": round(read_bytes / 1024, 3), "native_edits": edits,
    }
