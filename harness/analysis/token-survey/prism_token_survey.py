#!/usr/bin/env python3
"""Corpus-wide survey of prism MCP usage across every local Claude Code
transcript: op mix, payload sizes, redundant-read incidence, session token
cost vs prism-call-count, live (dogfood) vs e2e-benchmark split.

Read-only, aggregates only -- never prints raw transcript content.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"

def is_benchmark_dir(dirname: str) -> bool:
    # e2e harness worktrees are macOS mkdtemp paths under /var/folders or
    # /tmp, sluggified with dashes. Live dogfood sessions are real project
    # checkouts under /Users/.../Projects/...
    return ("e2e-run" in dirname or "ab-endtoend" in dirname or
            "-var-folders-" in dirname or "-private-tmp-" in dirname or
            "TestReadGuard" in dirname or "TestCmdInit" in dirname)

def content_len(c):
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        n = 0
        for item in c:
            if isinstance(item, dict) and item.get("type") == "text":
                n += len(item.get("text", ""))
            else:
                n += len(json.dumps(item))
        return n
    return len(json.dumps(c)) if c is not None else 0

def response_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for item in c:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "\n".join(parts)
    return ""

PRISM_NAME_RE = re.compile(r"^mcp__prism__")

def op_of(tool_input, tool_name: str) -> str:
    # compact tool: {"op": "...", "args": {...}}. Legacy tools: mcp__prism__prism_search etc.
    if isinstance(tool_input, dict) and "op" in tool_input:
        return tool_input["op"]
    return tool_name.replace("mcp__prism__prism_", "").replace("mcp__prism__", "")

def args_of(tool_input) -> dict:
    if not isinstance(tool_input, dict):
        return {}
    a = tool_input.get("args", tool_input)
    return a if isinstance(a, dict) else {}

def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def overlap_frac(a_from, a_to, b_from, b_to):
    a_from, a_to, b_from, b_to = _int(a_from), _int(a_to), _int(b_from), _int(b_to)
    lo, hi = max(a_from, b_from), min(a_to, b_to)
    if hi < lo or a_to < a_from:
        return 0.0
    return (hi - lo + 1) / (a_to - a_from + 1)

def scan_file(path: Path, stats: dict, is_bench: bool):
    tool_use = {}   # id -> (name, tool_input, ts)
    tool_result_len = {}  # id -> bytes
    session_tokens = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}
    prism_calls = []  # list of (op, args)
    read_calls = []   # list of (file_path, offset, limit)
    delivered_ranges = []  # (file, from, to) in call order, for redundancy check
    n_lines = 0

    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return
    for line in lines:
        n_lines += 1
        try:
            j = json.loads(line)
        except Exception:
            continue
        typ = j.get("type")
        msg = j.get("message") or {}
        if typ == "assistant":
            usage = msg.get("usage") or {}
            session_tokens["input"] += usage.get("input_tokens", 0) or 0
            session_tokens["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
            session_tokens["cache_write"] += usage.get("cache_creation_input_tokens", 0) or 0
            session_tokens["output"] += usage.get("output_tokens", 0) or 0
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    name = c.get("name", "")
                    tool_use[c["id"]] = (name, c.get("input") or {})
                    if name == "Read":
                        ti = c.get("input") or {}
                        read_calls.append((ti.get("file_path", ""), ti.get("offset") or 1, ti.get("limit")))
        elif typ == "user":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tid = c.get("tool_use_id")
                    if tid:
                        tool_result_len[tid] = content_len(c.get("content"))
                        # stash text for range-parsing prism responses
                        if tid in tool_use and PRISM_NAME_RE.match(tool_use[tid][0]):
                            tool_result_len[("text", tid)] = response_text(c.get("content"))

    if not tool_use:
        return

    any_prism = any(PRISM_NAME_RE.match(n) for n, _ in tool_use.values())
    if not any_prism:
        return

    bucket = stats["bench"] if is_bench else stats["live"]
    bucket["sessions"] += 1
    total_tok = sum(session_tokens.values())
    bucket["session_tokens"].append(total_tok)

    LOOKUP_BLOCK_RE = re.compile(
        r"file:\s*(?P<file>\S+)\s*\nline:\s*(?P<line>\d+)\s*\nbody:\s*(?P<body>.*?)"
        r"(?=\nname:\s|\Z)", re.S)

    n_prism = 0
    for tid, (name, tin) in tool_use.items():
        if not PRISM_NAME_RE.match(name):
            continue
        n_prism += 1
        op = op_of(tin, name)
        args = args_of(tin)
        plen = tool_result_len.get(tid, 0)
        bucket["op_count"][op] += 1
        bucket["op_bytes"][op].append(plen)
        if args.get("exhaustive"):
            bucket["exhaustive_calls"] += 1
        if args.get("scope") == "text":
            bucket["scope_text_calls"] += 1
        text = tool_result_len.get(("text", tid), "")
        if op == "read":
            f = args.get("file")
            frm = args.get("from") or 1
            to = args.get("to")
            if f and to:
                delivered_ranges.append((f, frm, to))
            for r in args.get("ranges") or []:
                if r.get("file"):
                    delivered_ranges.append((r["file"], r.get("from", 1), r.get("to", r.get("from", 1))))
        elif op == "lookup" and text:
            for m in LOOKUP_BLOCK_RE.finditer(text):
                body_lines = m.group("body").count("\n") + 1
                start = int(m.group("line"))
                delivered_ranges.append((m.group("file"), start, start + body_lines - 1))

    bucket["prism_calls_per_session"].append(n_prism)

    # Redundant-read heuristic: a native Read whose window is >=70% covered by
    # an EARLIER prism delivery in the same session.
    redundant = 0
    for f, offset, limit in read_calls:
        offset = _int(offset, 1)
        limit = _int(limit, 0) or None
        req_to = (offset + limit - 1) if limit else offset + 1999
        best = 0.0
        for df, dfrom, dto in delivered_ranges:
            if not f.endswith(df) and not df.endswith(f):
                continue
            best = max(best, overlap_frac(offset, req_to, dfrom, dto))
        if best >= 0.7:
            redundant += 1
    bucket["read_calls"] += len(read_calls)
    bucket["redundant_reads"] += redundant


def main():
    stats = {
        "live": {"sessions": 0, "session_tokens": [], "op_count": defaultdict(int),
                  "op_bytes": defaultdict(list), "exhaustive_calls": 0,
                  "scope_text_calls": 0, "prism_calls_per_session": [],
                  "read_calls": 0, "redundant_reads": 0},
        "bench": {"sessions": 0, "session_tokens": [], "op_count": defaultdict(int),
                   "op_bytes": defaultdict(list), "exhaustive_calls": 0,
                   "scope_text_calls": 0, "prism_calls_per_session": [],
                   "read_calls": 0, "redundant_reads": 0},
    }

    candidates = []
    for d in ROOT.iterdir():
        if not d.is_dir():
            continue
        is_bench = is_benchmark_dir(d.name)
        for f in d.glob("*.jsonl"):
            candidates.append((f, is_bench))

    print(f"scanning {len(candidates)} transcript files...", file=sys.stderr)
    done = 0
    for f, is_bench in candidates:
        try:
            with open(f, "rb") as fh:
                head = fh.read(4096)
            if b"mcp__prism" not in head and b"mcp__prism" not in open(f, "rb").read():
                continue
        except Exception:
            continue
        try:
            scan_file(f, stats, is_bench)
        except Exception as e:
            print(f"  !! skipping {f.name}: {e!r}", file=sys.stderr)
        done += 1
        if done % 200 == 0:
            print(f"  ...{done} scanned", file=sys.stderr)

    def pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        return s[int(len(s) * p)]

    for label in ("live", "bench"):
        b = stats[label]
        print(f"\n=== {label.upper()} ({b['sessions']} prism-using sessions) ===")
        if b["sessions"] == 0:
            continue
        tok = b["session_tokens"]
        print(f"session total tokens: mean={sum(tok)/len(tok):,.0f} median={pct(tok,0.5):,.0f} p90={pct(tok,0.9):,.0f} max={max(tok):,.0f}")
        calls = b["prism_calls_per_session"]
        print(f"prism calls/session: mean={sum(calls)/len(calls):.1f} median={pct(calls,0.5)} p90={pct(calls,0.9)} max={max(calls)}")
        print(f"op mix: {dict(sorted(b['op_count'].items(), key=lambda kv:-kv[1]))}")
        for op, byts in sorted(b["op_bytes"].items(), key=lambda kv: -sum(kv[1])):
            if not byts:
                continue
            print(f"  {op:15s} n={len(byts):5d} mean_bytes={sum(byts)/len(byts):8.0f} median={pct(byts,0.5):8.0f} p90={pct(byts,0.9):8.0f} max={max(byts):8.0f} total_KB={sum(byts)/1024:10.0f}")
        print(f"exhaustive=true calls: {b['exhaustive_calls']}  scope=text calls: {b['scope_text_calls']}")
        rr = b["redundant_reads"]
        rc = b["read_calls"]
        print(f"native Read calls in prism-using sessions: {rc}, of which >=70% overlap an earlier prism delivery: {rr} ({100*rr/rc:.1f}%)" if rc else "no native Read calls")


if __name__ == "__main__":
    main()
