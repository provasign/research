#!/usr/bin/env python3
"""Truer redundant-read estimate: the shipped read-guard hook only tracks
ranges delivered by op=read and op=lookup. But op=search (`include_bodies`)
and op=query ALSO deliver verbatim line-numbered windows per prism's own
steering ("do NOT re-read those files"). This checks whether a meaningful
number of native Reads overlap a window delivered by search/query too --
range the current hook is blind to.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"

def is_benchmark_dir(dirname):
    return ("e2e-run" in dirname or "ab-endtoend" in dirname or
            "-var-folders-" in dirname or "-private-tmp-" in dirname or
            "TestReadGuard" in dirname or "TestCmdInit" in dirname)

def response_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(item.get("text", "") for item in c if isinstance(item, dict) and "text" in item)
    return ""

PRISM_NAME_RE = re.compile(r"^mcp__prism__")
WINDOW_RE = re.compile(r"WINDOW\s+(\S+):(\d+)-(\d+)")
READ_HDR_RE = re.compile(r"^// (\S+) lines (\d+)-(\d+) of \d+", re.M)
LOOKUP_BLOCK_RE = re.compile(
    r"file:\s*(?P<file>\S+)\s*\nline:\s*(?P<line>\d+)\s*\nbody:\s*(?P<body>.*?)"
    r"(?=\nname:\s|\Z)", re.S)

def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d

def overlap_frac(a_from, a_to, b_from, b_to):
    lo, hi = max(a_from, b_from), min(a_to, b_to)
    if hi < lo or a_to < a_from:
        return 0.0
    return (hi - lo + 1) / (a_to - a_from + 1)

def op_of(tool_input, tool_name):
    if isinstance(tool_input, dict) and "op" in tool_input:
        return tool_input["op"]
    return tool_name.replace("mcp__prism__prism_", "").replace("mcp__prism__", "")


def scan_file(path, stats, is_bench):
    tool_use = {}
    tool_result_text = {}
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return
    for line in lines:
        try:
            j = json.loads(line)
        except Exception:
            continue
        typ = j.get("type")
        msg = j.get("message") or {}
        if typ == "assistant":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    tool_use[c["id"]] = (c.get("name", ""), c.get("input") or {})
        elif typ == "user":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tid = c.get("tool_use_id")
                    if tid:
                        tool_result_text[tid] = response_text(c.get("content"))

    if not tool_use or not any(PRISM_NAME_RE.match(n) for n, _ in tool_use.values()):
        return

    bucket = stats["bench"] if is_bench else stats["live"]

    # Single ordered pass: check each Read against ranges delivered so far
    # ONLY (a later delivery cannot justify an earlier read), then append
    # that tool's own deliveries. dict preserves insertion order from the
    # line-by-line scan, so iteration order is chronological.
    delivered = []  # (file, from, to, source_op)
    for tid, (name, tin) in tool_use.items():
        if name == "Read":
            ti = tin if isinstance(tin, dict) else {}
            f = ti.get("file_path", "")
            offset = _int(ti.get("offset"), 1)
            limit = _int(ti.get("limit"), 0) or None
            req_to = (offset + limit - 1) if limit else offset + 1999
            bucket["read_calls"] += 1
            best, best_src = 0.0, None
            for df, dfrom, dto, src in delivered:
                if not f.endswith(df) and not df.endswith(f):
                    continue
                frac = overlap_frac(offset, req_to, dfrom, dto)
                if frac > best:
                    best, best_src = frac, src
            if best >= 0.7:
                bucket["redundant"] += 1
                bucket["redundant_by_source"][best_src] += 1
            elif best >= 0.3:
                bucket["partial"] += 1
            continue
        if not PRISM_NAME_RE.match(name):
            continue
        op = op_of(tin, name)
        text = tool_result_text.get(tid, "")
        if op == "read":
            args = tin.get("args", tin) if isinstance(tin, dict) else {}
            if isinstance(args, dict):
                f, frm, to = args.get("file"), _int(args.get("from"), 1), args.get("to")
                if f and to:
                    delivered.append((f, frm, _int(to), "read"))
        elif op == "lookup" and text:
            for m in LOOKUP_BLOCK_RE.finditer(text):
                body_lines = m.group("body").count("\n") + 1
                start = int(m.group("line"))
                delivered.append((m.group("file"), start, start + body_lines - 1, "lookup"))
        elif op in ("search", "query") and text:
            for m in WINDOW_RE.finditer(text):
                delivered.append((m.group(1), int(m.group(2)), int(m.group(3)), op))
            for m in READ_HDR_RE.finditer(text):
                delivered.append((m.group(1), int(m.group(2)), int(m.group(3)), op))


def main():
    stats = {
        "live": {"read_calls": 0, "redundant": 0, "partial": 0, "redundant_by_source": defaultdict(int)},
        "bench": {"read_calls": 0, "redundant": 0, "partial": 0, "redundant_by_source": defaultdict(int)},
    }
    candidates = []
    for d in ROOT.iterdir():
        if not d.is_dir():
            continue
        is_bench = is_benchmark_dir(d.name)
        for f in d.glob("*.jsonl"):
            candidates.append((f, is_bench))
    print(f"scanning {len(candidates)} files...", file=sys.stderr)
    done = 0
    for f, is_bench in candidates:
        try:
            with open(f, "rb") as fh:
                if b"mcp__prism" not in fh.read():
                    continue
        except Exception:
            continue
        try:
            scan_file(f, stats, is_bench)
        except Exception as e:
            print(f"  !! {f.name}: {e!r}", file=sys.stderr)
        done += 1
        if done % 300 == 0:
            print(f"  ...{done}", file=sys.stderr)

    for label in ("live", "bench"):
        b = stats[label]
        rc = b["read_calls"]
        print(f"\n=== {label.upper()} ===")
        print(f"native Read calls: {rc}")
        if rc:
            print(f"  >=70% overlap an EARLIER prism delivery (any op): {b['redundant']} ({100*b['redundant']/rc:.1f}%)")
            print(f"  30-70% partial overlap: {b['partial']} ({100*b['partial']/rc:.1f}%)")
            print(f"  redundant reads by which op delivered the range first: {dict(b['redundant_by_source'])}")


if __name__ == "__main__":
    main()
