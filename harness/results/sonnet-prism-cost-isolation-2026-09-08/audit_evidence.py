"""Read-only audit of saved study cells; emits JSON to stdout, runs no agents."""
import collections
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent


def content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def audit(path):
    row = json.loads(path.read_text())
    events = []
    for line in path.with_name("stdout.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    calls, replies, rates = [], {}, []
    for event in events:
        if event.get("type") == "rate_limit_event":
            rates.append(event.get("rate_limit_info", {}))
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                calls.append(block)
            elif block.get("type") == "tool_result":
                replies[block.get("tool_use_id")] = content_text(block.get("content"))
    prism = []
    for call in calls:
        if not call["name"].startswith("mcp__prism"):
            continue
        result = replies.get(call["id"], "")
        try:
            obj = json.loads(result)
            fmt = "json"
        except (ValueError, TypeError):
            obj, fmt = None, "text"
        prism.append({"tool": call["name"], "input": call["input"],
                      "format": fmt, "bytes": len(result.encode()),
                      "keys": sorted(obj) if isinstance(obj, dict) else [],
                      "has_routing_note": "locator result" in result,
                      "cached_pointer": "[prism:cached]" in result})
    commands = [c["input"].get("command", "") for c in calls if c["name"] == "Bash"]
    tmp_paths = sorted(set(re.findall(r"/tmp/[\w./-]+", "\n".join(commands))))
    first_usage = next((e["message"].get("usage") for e in events
                        if e.get("type") == "assistant"), None)
    cmd = json.loads(path.with_name("command.json").read_text())
    return {"run": path.parents[2].name, "arm": row["arm"], "task": row["task"],
            "cost": row.get("cost_usd"), "valid": row.get("audited_valid"),
            "resolved": row.get("resolved"), "timed_out": row.get("timed_out"),
            "agent_error": row.get("agent_error"), "rates": rates,
            "turns": row.get("turns"), "usage": row.get("usage", {}).get("tokens"),
            "model_costs": {k: v.get("costUSD") for k, v in
                            row.get("usage", {}).get("model_usage", {}).items()},
            "first_usage": first_usage, "prism": prism,
            "native_reads": sum(c["name"] == "Read" for c in calls),
            "native_search_calls": sum(c["name"] in ("Grep", "Glob") for c in calls),
            "shell_discovery": sum(bool(re.search(r"\b(grep|rg|head|sed|cat)\b", c)) for c in commands),
            "tmp_paths": tmp_paths, "prompt_cost_steering": "Make the smallest robust change" in cmd[2],
            "external_package_commands": [c for c in commands if re.search(r"\bpip(?:3)?\s+(?:download|install)\b", c)],
            "rate_rejected": any(r.get("status") == "rejected" for r in rates),
            "test_names": row.get("score", {}),
            "evidence": str(path.relative_to(ROOT))}


def main():
    rows = [audit(p) for p in sorted(ROOT.glob("*/evidence/*/measurement.json"))]
    groups = {}
    for label in ("json", "compact"):
        selected = [r for r in rows if r["arm"] == "sonnet_prism" and
                    r["task"].startswith("pallets") and
                    (r["run"].startswith("s3-" + label) or r["run"] == "confirmation-" + label)]
        valid, deltas, natives = [], [], []
        for r in selected:
            native = next((n for n in rows if n["run"] == r["run"] and n["task"] == r["task"]
                           and n["arm"] == "sonnet_native"), None)
            if native and all(x["valid"] and x["resolved"] and x["cost"] is not None for x in (r, native)):
                valid.append(r)
                natives.append(native)
                deltas.append((r["cost"] / native["cost"] - 1) * 100)
        groups[label] = {"all_cells": len(selected), "valid_pairs": len(valid),
                         "median_native_cost": statistics.median(r["cost"] for r in natives),
                         "median_prism_cost": statistics.median(r["cost"] for r in valid),
                         "median_paired_delta_pct": statistics.median(deltas),
                         "prism_calls": dict(collections.Counter(c["tool"] for r in valid for c in r["prism"])),
                         "actual_formats": dict(collections.Counter(c["format"] for r in valid for c in r["prism"])),
                         "runs": [r["run"] for r in valid]}
    print(json.dumps({"format_groups": groups, "cells": rows}, indent=2))


if __name__ == "__main__":
    main()
