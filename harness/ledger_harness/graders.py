"""Third-party graders for the ledger A/B. None of these run through Prism.

Four independent signals per snapshot:

  1. typecheck   — `tsc --noEmit`. This is the FREE oracle a typed language
                   gives the agent: on the compiler-caught turns it flags every
                   missed site, which is exactly why those turns are expected to
                   tie and why the silent turns exist.
  2. conformance — 341 hidden tests against the frozen contract, tagged by turn.
                   Parameterized PER IMPLEMENTATION, so the number of failures
                   in a turn's family IS the number of sites the agent missed.
  3. own_tests   — the agent's own suite (self-graded; reported, never headline).
  4. stats       — size, so "mid-size" is a measured claim.

The headline for this study is `silent_misses`: failures in t07/t08, where the
compiler and the agent's own tests are both silent and completeness can only be
established by analysis.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
CONFORMANCE = HERE / "conformance"

# Excluded from snapshots and from every size/grader walk.
TOOL_ARTIFACTS = {".grove", ".prism", "prism.yaml", ".git", "node_modules",
                  ".conformance", "dist", ".engine-b"}

SILENT_TURNS = {"t07_provider_audit", "t08_minor_units"}
COMPILER_TURNS = {"t06_trace_param", "t09_describe", "t10_rename_move"}

_TAG = re.compile(r"^\[(\w+)\]")


def _run(cmd, cwd=None, timeout=900, env=None, shell=False):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env=e, shell=shell)


def _ts_files(repo: Path) -> list[Path]:
    out = []
    for p in repo.rglob("*.ts"):
        rel = p.relative_to(repo).parts
        if any(part in TOOL_ARTIFACTS for part in rel):
            continue
        out.append(p)
    return sorted(out)


# ------------------------------------------------------------------ typecheck
def typecheck(repo: Path, timeout: int = 600) -> dict:
    """Run in the LIVE repo — it is the only copy with node_modules."""
    tsc = repo / "node_modules" / ".bin" / "tsc"
    if not tsc.exists():
        return {"ran": False, "reason": "no local tsc"}
    try:
        r = _run([str(tsc), "--noEmit"], cwd=str(repo), timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "timeout"}
    errs = [l for l in (r.stdout or "").splitlines() if ": error TS" in l]
    # rc != 0 with no parsed diagnostics means tsc itself failed to run (a
    # broken node_modules copy does this — cp -r dereferences the .bin symlinks).
    # That is a harness fault, NOT a type error, and must never be scored as one.
    if r.returncode != 0 and not errs:
        return {"ran": False, "reason": "tsc did not run",
                "detail": ((r.stderr or r.stdout) or "")[-300:]}
    return {"ran": True, "clean": r.returncode == 0, "error_count": len(errs),
            "errors": errs[:15]}


# ---------------------------------------------------------------- conformance
def _raw_run(snapshot: Path, timeout: int = 900) -> dict[str, bool]:
    """Copy the hidden suite in, run it, clean up. name -> passed."""
    dst = snapshot / ".conformance"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(CONFORMANCE, dst)
    xml = snapshot / ".conf.xml"
    results: dict[str, bool] = {}
    try:
        _run(["node", "--test", "--test-reporter=junit",
              f"--test-reporter-destination={xml}", ".conformance/*.test.ts"],
             cwd=str(snapshot), timeout=timeout)
        if xml.exists():
            try:
                root = ET.parse(xml).getroot()
                for tc in root.iter("testcase"):
                    bad = any(tc.find(t) is not None for t in ("failure", "error"))
                    results[tc.get("name", "?")] = not bad
            except ET.ParseError:
                pass
            xml.unlink()
    except subprocess.TimeoutExpired:
        pass
    finally:
        shutil.rmtree(dst, ignore_errors=True)
    return results


def conformance(snapshot: Path, timeout: int = 900) -> dict:
    """Score a snapshot. Must be called AFTER own_tests, so the agent's own
    `node --test` never picks up the oracle."""
    known = _inventory()
    results = _raw_run(snapshot, timeout)

    # Denominator is ALWAYS the full suite. A test whose module failed to load
    # did not pass, and is charged to its turn rather than dropped.
    per_turn: dict[str, dict[str, int]] = {t: {"pass": 0, "fail": 0}
                                           for t in set(known.values())}
    for name, turn in known.items():
        ok = results.get(name, False)
        per_turn[turn]["pass" if ok else "fail"] += 1
    passed = sum(1 for n in known if results.get(n, False))
    total_known = len(known)
    missing = sum(1 for n in known if n not in results)
    return {
        "total": total_known,
        "passed": passed,
        "score": round(passed / total_known, 4) if total_known else 0.0,
        "per_turn": per_turn,
        "never_ran": missing,
        "silent_misses": sum(per_turn.get(t, {}).get("fail", 0) for t in SILENT_TURNS),
        "compiler_misses": sum(per_turn.get(t, {}).get("fail", 0) for t in COMPILER_TURNS),
        "failed_tests": sorted(n for n in known if not results.get(n, False)),
    }


# The expected inventory CANNOT be read statically: the per-implementation
# families are generated in loops with template-literal names, so a regex over
# the source undercounts them badly (184 vs the real 341) and inflates every
# score. Derive it once by running the suite against the reference, which is
# green by construction, and cache the result.
INVENTORY = HERE / "inventory.json"
_EXPECTED: dict[str, str] | None = None


def _inventory() -> dict[str, str]:
    """test name -> turn id, for every test the suite contains."""
    global _EXPECTED
    if _EXPECTED is not None:
        return _EXPECTED
    if INVENTORY.exists():
        _EXPECTED = json.loads(INVENTORY.read_text())
        return _EXPECTED
    names = _raw_run(HERE / "reference")
    if not names:
        raise RuntimeError("could not build conformance inventory from reference")
    _EXPECTED = {n: (_TAG.match(n).group(1) if _TAG.match(n) else "untagged")
                 for n in names}
    INVENTORY.write_text(json.dumps(_EXPECTED, indent=1, sort_keys=True))
    return _EXPECTED


def _expected_per_turn() -> dict[str, int]:
    counts: dict[str, int] = {}
    for turn in _inventory().values():
        counts[turn] = counts.get(turn, 0) + 1
    return counts


def expected_total() -> int:
    return len(_inventory())


# ------------------------------------------------------------------ own tests
def own_tests(snapshot: Path, timeout: int = 600) -> dict:
    if not (snapshot / "test").exists():
        return {"ran": False, "reason": "no test/ directory"}
    if (snapshot / ".conformance").exists():
        return {"ran": False, "reason": "conformance present — ordering bug"}
    try:
        r = _run(["node", "--test", "test/**/*.test.ts"], cwd=str(snapshot),
                 timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "timeout"}
    out = (r.stdout or "") + (r.stderr or "")
    def pick(k):
        m = re.search(rf"^. {k} (\d+)$", out, re.M)
        return int(m.group(1)) if m else 0
    return {"ran": True, "green": r.returncode == 0, "tests": pick("tests"),
            "pass": pick("pass"), "fail": pick("fail")}


# ---------------------------------------------------------------------- stats
def repo_stats(repo: Path) -> dict:
    files = _ts_files(repo)
    src = [f for f in files if f.relative_to(repo).parts[0] == "src"]
    tst = [f for f in files if f.relative_to(repo).parts[0] == "test"]
    def loc(fs):
        return sum(len([l for l in f.read_text(errors="replace").splitlines()
                        if l.strip()]) for f in fs)
    return {"ts_files": len(files), "src_files": len(src), "test_files": len(tst),
            "src_loc": loc(src), "test_loc": loc(tst)}


def grade(live_repo: Path, snapshot: Path, turn_index: int) -> dict:
    tc = typecheck(live_repo)          # live repo: only copy with node_modules
    ot = own_tests(snapshot)           # BEFORE the oracle is copied in
    cf = conformance(snapshot)         # copies .conformance, then removes it
    return {
        "typecheck": tc,
        "own_tests": ot,
        "conformance": cf,
        "stats": repo_stats(snapshot),
        "silent_misses": cf.get("silent_misses", 0),
        "compiler_misses": cf.get("compiler_misses", 0),
    }


if __name__ == "__main__":
    live = Path(sys.argv[1]).resolve()
    snap = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else live
    print(json.dumps(grade(live, snap, 13), indent=2)[:4000])
