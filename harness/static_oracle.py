#!/usr/bin/env python3
"""Docker-free scoring for agent runs: classify a run against the gold patch
and the run's own transcript.

Why this is the PRIMARY instrument (2026-09-07)
-----------------------------------------------
The local harness had no correctness signal at all -- it was steered by
process proxies (tokens saved, turns, blocked searches) that a measured
do-nothing run maximized. The obvious fix, the SWE-bench test oracle, needs
a 2.3GB prebuilt image per instance because the historical dependency tree
cannot be reproduced on the host (measured: this machine's pytest cannot even
COLLECT these repos). But test execution answers only ONE question -- "is
this alternative-but-different fix actually correct?" -- and at a ~21% solve
rate that is the rare case.

Every other bucket of the failure taxonomy is decidable statically:

    narrated instead of acted   the patch is empty
    fabricated verification     the guard fired; it is in the log
    non-convergence             hit the turn cap
    shallow fix                 1 file / 30 bytes against gold's 17 / 33KB
    wrong location              agent's files disjoint from gold's
    genuinely too hard          the residue

This is the same shape as prism's own impact oracle, which establishes
prism's completeness claims with no container anywhere. Docker stays as a
CONFIRMATORY tier for the handful of runs this classifier calls `plausible`,
where "did the tests actually flip" is a real question rather than a
formality.

Deliberately NOT a correctness claim: `plausible` means "worth executing",
never "resolved". Only the test oracle can say resolved, and this module
never pretends otherwise.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/", re.M)
# Docs and tests are excluded from the location signal: an agent is told not
# to write tests, and gold patches routinely carry documentation the task
# never asked for. Counting either would blur the one thing this measures --
# did the agent edit the source that the real fix edited.
NON_SOURCE_RE = re.compile(
    r"(^|/)(tests?|testing|docs?|examples?)/|"
    r"(^|/)(test_[^/]+|[^/]+_test)\.(py|go|rb|ts|js)$|"
    r"\.(md|rst|txt|cfg|ini|toml|lock)$", re.I)


def patch_files(patch: str, source_only: bool = True) -> set[str]:
    files = set(DIFF_FILE_RE.findall(patch or ""))
    if source_only:
        files = {f for f in files if not NON_SOURCE_RE.search(f)}
    return files


# Signals read off mason's own transcript. These are harness OUTPUT, not
# model prose, so they are reliable in a way scraping the model's words
# never is.
LOG_SIGNALS = {
    "unverified": re.compile(r"UNVERIFIED|change is NOT verified", re.I),
    "hands_back": re.compile(r"hands commands back to the user", re.I),
    "fabrication": re.compile(r"claimed test success contradicts", re.I),
    "incomplete_diff": re.compile(r"diff is INCOMPLETE", re.I),
    "no_file_modified": re.compile(r"asked for a change but no file was modified", re.I),
    "turn_cap": re.compile(r"hit the \d+-turn budget", re.I),
    "obligation_unmet": re.compile(r"task obligation unmet", re.I),
}
USAGE_RE = re.compile(r"usage:\s*(\d+)\s*in\s*/\s*(\d+)\s*out")
TOOL_LINE_RE = re.compile(r"^  [·$✎]", re.M)


def classify(task: dict, agent_patch: str, log: str = "") -> dict:
    gold = task.get("patch", "")
    gold_src = patch_files(gold)
    agent_src = patch_files(agent_patch)
    hit = gold_src & agent_src
    coverage = len(hit) / len(gold_src) if gold_src else 0.0
    # Size ratio against gold is a crude proxy for substance, but it
    # separates a token edit from a real attempt, which is the distinction
    # that matters at this solve rate.
    size_ratio = (len(agent_patch or "") / len(gold)) if gold else 0.0

    flags = {k: bool(r.search(log)) for k, r in LOG_SIGNALS.items()} if log else {}

    if not (agent_patch or "").strip():
        bucket = "no_change"
    elif not agent_src:
        bucket = "non_source_only"
    elif not hit:
        bucket = "wrong_location"
    elif coverage < 0.5 or size_ratio < 0.2:
        bucket = "shallow"
    else:
        bucket = "plausible"

    m = USAGE_RE.search(log or "")
    return {
        "bucket": bucket,
        "needs_execution": bucket == "plausible",
        "gold_files": sorted(gold_src),
        "agent_files": sorted(agent_src),
        "files_hit": sorted(hit),
        "coverage": round(coverage, 3),
        "size_ratio": round(size_ratio, 4),
        "gold_bytes": len(gold),
        "agent_bytes": len(agent_patch or ""),
        "flags": flags,
        "tool_calls": len(TOOL_LINE_RE.findall(log or "")),
        "tokens_in": int(m.group(1)) if m else None,
        "tokens_out": int(m.group(2)) if m else None,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="instance_id")
    ap.add_argument("--patch", required=True, help="path to the agent diff")
    ap.add_argument("--log", help="path to the run transcript")
    a = ap.parse_args()
    import mason_oracle
    task = mason_oracle.load_task(a.task)
    log = Path(a.log).read_text(errors="ignore") if a.log else ""
    print(json.dumps(classify(task, Path(a.patch).read_text(), log), indent=2))


if __name__ == "__main__":
    main()
