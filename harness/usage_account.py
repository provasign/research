"""Billing-equivalent usage accounting for headless `claude -p` cells.

Before 2026-09-05 the harness kept `tokens_in = input + cache_read` and
dropped cache CREATION tokens entirely, though they are billed (at a premium
over uncached input). It also recovered per-turn usage after the fact by
summing transcript lines — and a transcript repeats an assistant message
(one line per streamed content block: measured 57 lines / 33 message ids in
one wide cell), so a naive sum overcounts.

Two sources, both recorded raw so the analysis can be redone later:

  cli_usage(j)           the CLI's own result JSON: aggregate `usage` with all
                         four categories, `modelUsage` (per-model, includes
                         the CLI's costUSD), `total_cost_usd`, `session_id`.
                         total_cost_usd is the billed figure — it already
                         prices cache writes and reads at their own rates.
  transcript_usage(sid)  the session transcript, deduplicated by message id:
                         per-request usage, tool-result bytes per tool, and
                         call counts, so payload cost can be attributed.
"""
from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"


@functools.lru_cache(maxsize=1)
def claude_version() -> str:
    try:
        return subprocess.run(["claude", "--version"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return "unknown"


def cli_usage(j: dict) -> dict:
    u = j.get("usage") or {}
    return {
        "session_id": j.get("session_id"),
        "tokens": {
            "input_uncached": u.get("input_tokens", 0),
            "cache_creation": u.get("cache_creation_input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0),
            "output": u.get("output_tokens", 0),
        },
        "model_usage": j.get("modelUsage"),
        "cost_usd_cli": j.get("total_cost_usd"),
        "pricing_source": f"claude-cli total_cost_usd ({claude_version()})",
    }


def transcript_path(session_id: str | None) -> Path | None:
    if not session_id:
        return None
    hits = list(PROJECTS.glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None


def transcript_usage(session_id: str | None) -> dict:
    """Usage summed once per assistant message id; tool-result bytes per tool.

    Returns {"_unavailable": reason} when the transcript cannot be found so a
    caller can record the gap instead of silently zeroing it.
    """
    p = transcript_path(session_id)
    if p is None:
        return {"_unavailable": "no transcript for session"}
    seen: set[str] = set()
    lines = dup = 0
    tok = {"input_uncached": 0, "cache_creation": 0, "cache_read": 0, "output": 0}
    requests: set[str] = set()
    calls: dict[str, int] = {}
    result_bytes: dict[str, int] = {}
    pending: dict[str, str] = {}  # tool_use_id -> tool name
    for line in p.open(errors="ignore"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        t = j.get("type")
        if t == "assistant":
            lines += 1
            m = j.get("message") or {}
            for c in m.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    calls[c["name"]] = calls.get(c["name"], 0) + 1
                    pending[c.get("id", "")] = c["name"]
            mid = m.get("id")
            if mid in seen:
                dup += 1
                continue
            seen.add(mid)
            if j.get("requestId"):
                requests.add(j["requestId"])
            u = m.get("usage") or {}
            tok["input_uncached"] += u.get("input_tokens", 0)
            tok["cache_creation"] += u.get("cache_creation_input_tokens", 0)
            tok["cache_read"] += u.get("cache_read_input_tokens", 0)
            tok["output"] += u.get("output_tokens", 0)
        elif t == "user":
            for c in ((j.get("message") or {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    name = pending.get(c.get("tool_use_id", ""), "?")
                    body = c.get("content")
                    n = len(body) if isinstance(body, str) else len(json.dumps(body or ""))
                    result_bytes[name] = result_bytes.get(name, 0) + n
    ctx = tok["input_uncached"] + tok["cache_creation"] + tok["cache_read"]
    return {
        "transcript": str(p),
        "messages": len(seen),
        "duplicate_lines": dup,
        "requests": len(requests),
        "tokens": tok,
        "cache_hit_rate": round(tok["cache_read"] / ctx, 3) if ctx else None,
        "tool_calls": calls,
        "tool_result_bytes": result_bytes,
    }
