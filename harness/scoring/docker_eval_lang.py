"""Language runners for docker_eval's fail->pass scoring, beyond the
original Python/pytest path. Same contract as PytestRun: an `outcomes`
dict of test-id -> PASSED/FAILED/ERROR, and `collection_failed` for "the
build or test harness itself did not come up" (distinct from "a test
failed").

Added 2026-09-13 to extend the e2e benchmark past Python/Java into Go,
Rust, and TypeScript/JavaScript via Multi-SWE-bench (ByteDance-Seed)
instances. Each runner mirrors docker_eval._pytest_in_docker: run the
project's own test command inside its language's official image, over
the same throwaway worktree docker_eval._worktree already builds.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

GO_IMAGE = "golang:1.23"
RUST_IMAGE = "rust:1.81"
NODE_IMAGE = "node:20"


@dataclass(frozen=True)
class LangRun:
    outcomes: dict[str, str]
    collection_failed: bool = False


def _sh(*a, cwd=None, timeout=900):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _parse_go_json(out: str) -> LangRun:
    """Each line of `go test -json` output is one event; the last Action
    per Test wins (subtests re-report their parent as it completes)."""
    outcomes: dict[str, str] = {}
    saw_any = False
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        test = ev.get("Test")
        action = ev.get("Action")
        if not test or action not in ("pass", "fail", "skip"):
            continue
        saw_any = True
        outcomes[test] = {"pass": "PASSED", "fail": "FAILED", "skip": "SKIPPED"}[action]
    if not saw_any:
        return LangRun({}, collection_failed=True)
    return LangRun(outcomes)


def go_test_in_docker(worktree: Path) -> LangRun:
    """`go test -json ./...` inside the official golang image."""
    cmd = "export GOFLAGS=-mod=mod GOPROXY=https://proxy.golang.org,direct; " \
          "cd /w && go test -json ./... 2>&1"
    r = _sh("docker", "run", "--rm", "-v", f"{worktree}:/w", "-w", "/w",
            GO_IMAGE, "bash", "-c", cmd, timeout=900)
    return _parse_go_json(r.stdout)


_CARGO_LINE = re.compile(r"^test (\S+) \.\.\. (ok|FAILED|ignored)$", re.M)
_CARGO_BUILD_FAIL = re.compile(r"^error(\[E\d+\])?:|^error: could not compile", re.M)


def _parse_cargo_output(out: str) -> LangRun:
    """cargo's default text format: `test NAME ... ok|FAILED|ignored` per
    line. No JSON formatter exists on stable, so this greps text the way
    pytest text mode already does for Python."""
    outcomes = {m.group(1): {"ok": "PASSED", "FAILED": "FAILED", "ignored": "SKIPPED"}[m.group(2)]
                for m in _CARGO_LINE.finditer(out)}
    if not outcomes and _CARGO_BUILD_FAIL.search(out):
        return LangRun({}, collection_failed=True)
    return LangRun(outcomes)


def cargo_test_in_docker(worktree: Path) -> LangRun:
    """`cargo test --no-fail-fast` inside the official rust image."""
    # --locked when the repo committed a Cargo.lock: without it, cargo
    # resolves fresh against crates.io and can pull a dependency version
    # newer than the pinned toolchain supports (clap-rs/clap#3225: a fresh
    # hashbrown 0.17 needs edition2024, unsupported on rust:1.81 -- a build
    # failure with nothing to do with the task).
    locked = "--locked " if (worktree / "Cargo.lock").exists() else ""
    cmd = f"cd /w && cargo test {locked}--no-fail-fast -- --test-threads=1 2>&1"
    r = _sh("docker", "run", "--rm", "-v", f"{worktree}:/w", "-w", "/w",
            RUST_IMAGE, "bash", "-c", cmd, timeout=1800)
    return _parse_cargo_output(r.stdout)


_JEST_CONFIG_NAMES = ("jest.config.mjs", "jest.config.js", "jest.config.cjs", "jest.config.ts")


def _nearest_jest_config(worktree: Path, test_file: str) -> str | None:
    """Walk up from a changed test file to the nearest jest.config.*, the
    way jest itself resolves per-directory configs. Hardcoding one config
    path (e.g. the current main branch's tests/unit/jest.config.mjs) breaks
    the moment an instance's base_commit predates that layout -- caught on
    darkreader#7241, whose base commit still used per-directory configs
    under tests/<area>/jest.config.js, not the later tests/unit/ layout."""
    d = (worktree / test_file).parent
    while True:
        for name in _JEST_CONFIG_NAMES:
            if (d / name).exists():
                return str((d / name).relative_to(worktree))
        if d == worktree or d.parent == d:
            return None
        d = d.parent


def _changed_test_files(test_patch: str) -> list[str]:
    return [line.split(" b/", 1)[1] for line in test_patch.splitlines()
            if line.startswith("diff --git") and " b/" in line]


def _parse_jest_report(report: dict) -> dict[str, str]:
    """One jest --json report -> {test_id: outcome}. jest runs inside the
    container where the worktree is mounted at /w, so its own absolute
    paths are "/w/...", not the host worktree path -- matching
    Multi-SWE-bench's own id shape ("tests/x/y.ts:Test title") needs the
    container-side prefix stripped, not the host one."""
    outcomes: dict[str, str] = {}
    for suite in report.get("testResults", []):
        rel = suite.get("name", "")
        if rel.startswith("/w/"):
            rel = rel[len("/w/"):]
        for a in suite.get("assertionResults", []):
            status = {"passed": "PASSED", "failed": "FAILED",
                      "pending": "SKIPPED", "skipped": "SKIPPED"}.get(a.get("status"), "ERROR")
            title = a.get("title", "")
            outcomes[f"{rel}:{title}"] = status
            outcomes.setdefault(rel, status)  # file-level id, for suite-shaped ids
    return outcomes


def npm_test_in_docker(worktree: Path, test_patch: str = "") -> LangRun:
    """`npm ci` then jest with --json to a file (jest's stdout --json can be
    interleaved with console output from the tests themselves, so a file
    is the only reliable channel). Config is resolved per changed test file
    (see _nearest_jest_config) rather than assumed, and jest runs once per
    distinct config found -- most instances touch one config; a few touch
    more, and their reports are merged."""
    test_files = _changed_test_files(test_patch)
    configs = sorted({c for c in (_nearest_jest_config(worktree, f) for f in test_files) if c} or {None})
    outcomes: dict[str, str] = {}
    any_report = False
    for i, config in enumerate(configs):
        jest_cfg = f"--config={config}" if config else ""
        out_file = f"/tmp/jest-{i}.json"
        cmd = ("cd /w && npm ci --no-audit --no-fund 2>&1 | tail -5; "
               f"npx jest {jest_cfg} --json --outputFile={out_file} --testTimeout=30000 "
               f"2>&1 | tail -20; echo ---RESULT---; cat {out_file} 2>/dev/null || echo '{{}}'")
        r = _sh("docker", "run", "--rm", "-v", f"{worktree}:/w", "-w", "/w",
                NODE_IMAGE, "bash", "-c", cmd, timeout=1200)
        out = r.stdout
        if "---RESULT---" not in out:
            continue
        tail = out.split("---RESULT---", 1)[1].strip()
        try:
            report = json.loads(tail)
        except json.JSONDecodeError:
            continue
        if not report.get("testResults"):
            continue
        any_report = True
        outcomes.update(_parse_jest_report(report))
    if not any_report:
        return LangRun({}, collection_failed=True)
    return LangRun(outcomes)


RUNNERS = {"go": go_test_in_docker, "rust": cargo_test_in_docker,
           "ts": npm_test_in_docker, "js": npm_test_in_docker}

# go/rust runners take (worktree); npm_test_in_docker also wants the task's
# test_patch to resolve the right jest config -- flagged here so the
# dispatcher in docker_eval.py knows to pass it.
NEEDS_TEST_PATCH = {"ts", "js"}
