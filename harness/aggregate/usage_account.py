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
import math
import subprocess
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"

USAGE_VERSION = 3
TOKEN_FIELDS = {
    "input_uncached": "input_tokens",
    "cache_creation": "cache_creation_input_tokens",
    "cache_read": "cache_read_input_tokens",
    "output": "output_tokens",
}


def normalized_tokens(usage: dict) -> dict:
    """Missing/invalid counters remain unknown, never free tokens."""
    usage = usage if isinstance(usage, dict) else {}
    result = {}
    for name, source in TOKEN_FIELDS.items():
        value = usage.get(source)
        result[name] = value if type(value) is int and value >= 0 else None
    return result


def input_total(tokens: dict) -> int | None:
    values = [tokens.get(k) for k in ("input_uncached", "cache_creation", "cache_read")]
    return sum(values) if all(type(v) is int and v >= 0 for v in values) else None


def content_bytes(body) -> int:
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return len(text.encode("utf-8"))


def transcript_lines(path: Path):
    with path.open(errors="replace") as stream:
        yield from stream


@functools.lru_cache(maxsize=1)
def claude_version() -> str:
    try:
        return subprocess.run(["claude", "--version"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return "unknown"


def cli_usage(j: dict) -> dict:
    u = j.get("usage") or {}
    tokens = normalized_tokens(u)
    cost = j.get("total_cost_usd")
    valid_cost = type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
    return {
        "usage_version": USAGE_VERSION,
        "session_id": j.get("session_id"),
        "tokens": tokens,
        "input_total": input_total(tokens),
        "usage_complete": all(v is not None for v in tokens.values()) and valid_cost,
        "raw_usage": u,
        "model_usage": j.get("modelUsage"),
        "cost_usd_cli": cost if valid_cost else None,
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
    return analyze_transcript(p)


def analyze_transcript(p: Path) -> dict:
    """Count main-loop messages and tool IDs once; retain final streamed usage."""
    messages: dict[str, dict] = {}
    lines = dup = 0
    requests: set[str] = set()
    calls: dict[str, int] = {}
    result_bytes: dict[str, int] = {}
    pending: dict[str, str] = {}  # tool_use_id -> tool name
    results: dict[str, int] = {}
    warnings: set[str] = set()
    final_usage = None
    for line in transcript_lines(p):
        try:
            j = json.loads(line)
        except (ValueError, TypeError):
            warnings.add("malformed transcript event")
            continue
        if not isinstance(j, dict):
            warnings.add("non-object transcript event")
            continue
        if j.get("parent_tool_use_id") or j.get("isSidechain"):
            continue
        t = j.get("type")
        if t == "result" and isinstance(j.get("usage"), dict):
            final_usage = normalized_tokens(j["usage"])
        if t == "assistant":
            lines += 1
            m = j.get("message") or {}
            if not isinstance(m, dict):
                warnings.add("invalid assistant message")
                continue
            for c in m.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    tid, name = c.get("id"), c.get("name")
                    if not tid or not name:
                        warnings.add("tool use missing identity")
                        continue
                    if tid not in pending:
                        calls[name] = calls.get(name, 0) + 1
                        pending[tid] = name
            mid = m.get("id")
            if not mid:
                warnings.add("assistant message missing identity")
                continue
            if mid in messages:
                dup += 1
            if j.get("requestId"):
                requests.add(j["requestId"])
            u = m.get("usage") or {}
            if not isinstance(u, dict):
                warnings.add("invalid assistant usage")
                u = {}
            previous = messages.setdefault(mid, {})
            # Streaming fragments may carry only some counters.
            previous.update({k: v for k, v in u.items() if k in TOKEN_FIELDS.values()})
        elif t == "user":
            m = j.get("message") or {}
            if not isinstance(m, dict):
                warnings.add("invalid user message")
                continue
            for c in (m.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tid = c.get("tool_use_id")
                    if not tid:
                        warnings.add("tool result missing identity")
                        continue
                    results[tid] = content_bytes(c.get("content"))
    for tid, size in results.items():
        name = pending.get(tid, "?")
        result_bytes[name] = result_bytes.get(name, 0) + size
    normalized = [normalized_tokens(u) for u in messages.values()]
    tok = {}
    for key in TOKEN_FIELDS:
        values = [u[key] for u in normalized]
        tok[key] = sum(values) if values and all(v is not None for v in values) else None
    # Transcript step output may be a streaming placeholder, so never use it
    # as the authoritative output total without a final aggregate.
    observed_output = tok["output"]
    tok["output"] = final_usage.get("output") if final_usage is not None else None
    diagnostics_complete = not warnings and input_total(tok) is not None
    if not diagnostics_complete:
        warnings.add("transcript diagnostics incomplete")
    # Session JSONL normally lacks the CLI stdout result. This is an expected
    # source boundary, not a failed cell or a missing transcript input counter.
    aggregate_status = "not_present_in_transcript" if final_usage is None else (
        "present" if tok["output"] is not None else "invalid")
    usage_complete = (all(v is not None for v in tok.values()) and diagnostics_complete
                      if final_usage is not None else None)
    notes = ["no final aggregate in transcript; use the saved CLI result for total usage"] if final_usage is None else []
    if aggregate_status == "invalid":
        warnings.add("invalid final aggregate in transcript")
    ctx = input_total(tok)
    return {
        "usage_version": USAGE_VERSION,
        "transcript": str(p),
        "messages": len(messages),
        "duplicate_lines": dup,
        "requests": len(requests),
        "tokens": tok,
        "step_output_observed": observed_output,
        "usage_complete": usage_complete,
        "diagnostics_complete": diagnostics_complete,
        "aggregate_status": aggregate_status,
        "notes": notes,
        "warnings": sorted(warnings),
        "cache_hit_rate": round(tok["cache_read"] / ctx, 3) if ctx else None,
        "tool_calls": calls,
        "tool_result_bytes": result_bytes,
    }
