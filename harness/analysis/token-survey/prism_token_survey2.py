#!/usr/bin/env python3
"""Follow-up pass: correlation of prism-call-count vs session tokens (LIVE
population, real n), byte concentration per op (is a few calls driving most
bytes?), a truer redundant-read estimate that also tracks search/query
delivered windows, and the biggest individual change_impact/search calls by
symbol/query so patterns are attributable, not just aggregate numbers.
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"

def is_benchmark_dir(dirname: str) -> bool:
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

def op_of(tool_input, tool_name):
    if isinstance(tool_input, dict) and "op" in tool_input:
        return tool_input["op"]
    return tool_name.replace("mcp__prism__prism_", "").replace("mcp__prism__", "")

def args_of(tool_input):
    if not isinstance(tool_input, dict):
        return {}
    a = tool_input.get("args", tool_input)
    return a if isinstance(a, dict) else {}

def query_label(op, args):
    if op in ("lookup", "change_impact"):
        n = args.get("name")
        if isinstance(n, list):
            n = ",".join(str(x if isinstance(x, str) else x.get("name", "?")) for x in n[:3])
        return str(n)[:60]
    if op in ("search", "query"):
        t = args.get("terms") or args.get("name")
        if isinstance(t, list):
            t = ",".join(str(x) for x in t[:3])
        return str(t)[:60]
    if op == "read":
        return str(args.get("file"))[:60]
    return ""


def scan_file(path, is_bench, live_pairs, byte_records, top_calls):
    tool_use = {}
    tool_result_len = {}
    tool_result_text = {}
    session_tokens = defaultdict(int)

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
            usage = msg.get("usage") or {}
            for k, uk in (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                          ("cache_write", "cache_creation_input_tokens"), ("output", "output_tokens")):
                session_tokens[k] += usage.get(uk, 0) or 0
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    tool_use[c["id"]] = (c.get("name", ""), c.get("input") or {})
        elif typ == "user":
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tid = c.get("tool_use_id")
                    if tid:
                        tool_result_len[tid] = content_len(c.get("content"))

    if not tool_use:
        return
    if not any(PRISM_NAME_RE.match(n) for n, _ in tool_use.values()):
        return

    n_prism = 0
    for tid, (name, tin) in tool_use.items():
        if not PRISM_NAME_RE.match(name):
            continue
        n_prism += 1
        op = op_of(tin, name)
        args = args_of(tin)
        plen = tool_result_len.get(tid, 0)
        byte_records[op].append(plen)
        top_calls.append((plen, op, query_label(op, args), path.parent.name[:40]))

    total_tok = sum(session_tokens.values())
    if not is_bench:
        live_pairs.append((n_prism, total_tok))


def main():
    live_pairs = []
    byte_records = defaultdict(list)
    top_calls = []

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
            scan_file(f, is_bench, live_pairs, byte_records, top_calls)
        except Exception as e:
            print(f"  !! {f.name}: {e!r}", file=sys.stderr)
        done += 1
        if done % 300 == 0:
            print(f"  ...{done}", file=sys.stderr)

    # 1. correlation calls vs tokens, LIVE only, excluding the monster outlier sessions (>1B tokens, clearly long-running loops not comparable)
    filtered = [(c, t) for c, t in live_pairs if t < 50_000_000]
    print(f"\nLIVE sessions used for correlation (excluding >50M-token monsters): {len(filtered)} / {len(live_pairs)}")
    if len(filtered) > 2:
        xs = [c for c, t in filtered]
        ys = [t for c, t in filtered]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
        sx, sy = statistics.pstdev(xs), statistics.pstdev(ys)
        r = cov / (sx * sy) if sx and sy else float("nan")
        print(f"corr(prism_calls, session_tokens) = {r:.3f}")
        # bucket
        buckets = defaultdict(list)
        for c, t in filtered:
            key = "0" if c == 0 else "1-2" if c <= 2 else "3-5" if c <= 5 else "6-10" if c <= 10 else "11+"
            buckets[key].append(t)
        for k in ("0", "1-2", "3-5", "6-10", "11+"):
            if k in buckets:
                v = buckets[k]
                print(f"  {k:5s} calls: n={len(v):4d} mean_tokens={sum(v)/len(v):>12,.0f} median={sorted(v)[len(v)//2]:>12,.0f}")

    # 2. byte concentration per op: what % of total bytes comes from the top 10% largest calls?
    print("\nByte concentration (top-10%-by-size share of total bytes), all ops, live+bench combined:")
    for op, vals in sorted(byte_records.items(), key=lambda kv: -sum(kv[1])):
        if len(vals) < 10:
            continue
        s = sorted(vals, reverse=True)
        top10 = s[:max(1, len(s)//10)]
        share = sum(top10) / sum(s) if sum(s) else 0
        print(f"  {op:15s} n={len(vals):5d} total_KB={sum(vals)/1024:9.0f} top10pct_share={share*100:5.1f}%  max={max(vals):8d}")

    # 3. biggest individual calls, with symbol/query label, so the tail is attributable
    print("\nTop 20 single largest prism tool_result payloads (op, bytes, label, session-dir):")
    for plen, op, label, dirn in sorted(top_calls, reverse=True)[:20]:
        print(f"  {plen:8d}B  {op:15s} {label!r:65s} [{dirn}]")


if __name__ == "__main__":
    main()
