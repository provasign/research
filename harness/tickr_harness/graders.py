"""Third-party graders for the tickr A/B. None of these run through Prism.

Four independent correctness signals per repository snapshot:

  1. conformance  — a hidden pytest suite written against the frozen contract,
                    which the agents never see. Per-test results are mapped to
                    the turn whose contract they check, giving a per-turn
                    correctness curve.
  2. stale_sites  — a pure `ast` walk counting call sites left on a superseded
                    signature or name after the refactor turns. This is the
                    completeness measure, and it is computed by the standard
                    library, not by the tool under test.
  3. import_health— every module in the package imports cleanly.
  4. own_tests    — the agent's own suite passes (self-graded; reported, but
                    never the headline).
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
CONFORMANCE = HERE / "conformance"

# Artefacts the context tools drop into the repo. Excluded from every grader and
# from every line/file count, so no arm is credited or penalised for its index.
TOOL_ARTIFACTS = {".grove", ".prism", "prism.yaml", ".engine-b", ".git",
                  "__pycache__", ".pytest_cache", ".venv", "node_modules"}


def _py_files(repo: Path) -> list[Path]:
    out = []
    for p in repo.rglob("*.py"):
        if any(part in TOOL_ARTIFACTS for part in p.relative_to(repo).parts):
            continue
        out.append(p)
    return sorted(out)


def _run(cmd, cwd=None, timeout=600, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env=e)


# --------------------------------------------------------------- 1. conformance
_MARKER_RE = re.compile(r'turn\(\s*["\']([a-z0-9_]+)["\']\s*\)')


def conformance_markers() -> dict[str, str]:
    """test_name -> turn id, read straight off the @pytest.mark.turn decorators."""
    out: dict[str, str] = {}
    for f in sorted(CONFORMANCE.glob("test_*.py")):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            for dec in node.decorator_list:
                m = _MARKER_RE.search(ast.unparse(dec))
                if m:
                    out[node.name] = m.group(1)
    return out


def conformance(repo: Path, timeout: int = 900) -> dict:
    """Run the hidden suite against `repo`. Returns per-test pass/fail."""
    xml = repo.parent / f".conf-{repo.name}.xml"
    if xml.exists():
        xml.unlink()
    # --continue-on-collection-errors matters: an early snapshot has no
    # tickr.alerting and no clear_traces, so whole test MODULES fail to import.
    # Without the flag pytest aborts and emits six error stubs, the denominator
    # collapses to six, and the score is both meaningless and unfair. With it,
    # every module that CAN import still runs.
    r = _run([sys.executable, "-m", "pytest", str(CONFORMANCE), "-q",
              "--tb=no", "-p", "no:cacheprovider", "--import-mode=importlib",
              "--continue-on-collection-errors", f"--junitxml={xml}"],
             cwd=str(repo), timeout=timeout,
             env={"PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"})
    results: dict[str, bool] = {}
    parse_error = ""
    if xml.exists():
        # A truncated/empty JUnit file means pytest itself died (it did once, when
        # the seeded package shadowed a stdlib module). Never let that raise out
        # of a grader and kill a multi-hour run — record it and score it as zero.
        try:
            root = ET.parse(xml).getroot()
            for tc in root.iter("testcase"):
                bad = any(tc.find(t) is not None for t in ("failure", "error"))
                results[tc.get("name", "?")] = not bad
        except ET.ParseError as e:
            parse_error = f"junit xml unparseable ({e}); pytest rc={r.returncode}"
        xml.unlink()

    # The denominator is ALWAYS the full suite. A test whose module could not
    # import did not pass, and must not be silently dropped from the score.
    markers = conformance_markers()
    known = set(markers)
    ran = set(results)
    passed_names = {n for n, ok in results.items() if ok and n in known}
    per_turn: dict[str, dict[str, int]] = {}
    for name, turn in markers.items():
        d = per_turn.setdefault(turn, {"pass": 0, "fail": 0})
        d["pass" if name in passed_names else "fail"] += 1
    total = len(known)
    passed = len(passed_names)
    return {
        "total": total,
        "passed": passed,
        "score": round(passed / total, 4) if total else 0.0,
        "per_turn": per_turn,
        "collected_n": len(known & ran),
        "uncollected_n": len(known - ran),
        "parse_error": parse_error,
        "stderr_tail": (parse_error + " | " + r.stderr[-400:]) if not passed else "",
        "failed_tests": sorted(known - passed_names),
    }


# --------------------------------------------------------------- 2. stale sites
# Minimum POSITIONAL arg count each indicator call must have. Pre-t4 the first
# parameter (series_id) does not exist yet, so both shapes are recorded and the
# runner reads the one that applies to the snapshot's turn.
ARITY_PRE_T4 = {"sma": 2, "ema": 2, "volatility": 2, "rsi": 1, "macd": 1}
ARITY_POST_T4 = {"sma": 3, "ema": 3, "volatility": 3, "rsi": 2, "macd": 2}

# Names that must have disappeared after t5_rename_move.
RENAMED_AWAY = {"run_once", "evaluate"}


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def stale_sites(repo: Path) -> dict:
    """Call sites left behind by the refactors, found with the stdlib `ast`."""
    pre, post, renamed, alerts_refs = [], [], [], []
    syntax_errors = []
    for f in _py_files(repo):
        try:
            tree = ast.parse(f.read_text(errors="replace"))
        except SyntaxError as e:
            syntax_errors.append(f"{f.relative_to(repo)}:{e.lineno}")
            continue
        rel = str(f.relative_to(repo))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name in ARITY_POST_T4:
                    if any(isinstance(a, ast.Starred) for a in node.args):
                        continue  # *args — cannot judge statically, skip
                    kw = {k.arg for k in node.keywords if k.arg}
                    n = len(node.args) + (1 if "series_id" in kw else 0)
                    site = f"{rel}:{node.lineno} {name}/{len(node.args)}"
                    if n < ARITY_POST_T4[name]:
                        post.append(site)
                    if len(node.args) + len(kw) < ARITY_PRE_T4[name]:
                        pre.append(site)
            if isinstance(node, ast.Attribute) and node.attr in RENAMED_AWAY:
                renamed.append(f"{rel}:{node.lineno} .{node.attr}")
            if isinstance(node, ast.FunctionDef) and node.name in RENAMED_AWAY:
                renamed.append(f"{rel}:{node.lineno} def {node.name}")
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tickr.alerts"):
                alerts_refs.append(f"{rel}:{node.lineno} from {node.module}")
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("tickr.alerts"):
                        alerts_refs.append(f"{rel}:{node.lineno} import {a.name}")
    return {
        "stale_indicator_calls_post_t4": sorted(post),
        "stale_indicator_calls_pre_t4": sorted(pre),
        "stale_renamed_refs": sorted(renamed),
        "stale_alerts_module_refs": sorted(alerts_refs),
        "alerts_py_still_exists": (repo / "tickr" / "alerts.py").exists(),
        "syntax_errors": syntax_errors,
    }


# --------------------------------------------------------------- 3. imports
def import_health(repo: Path) -> dict:
    pkg = repo / "tickr"
    mods = sorted(p.stem for p in pkg.glob("*.py")) if pkg.is_dir() else []
    mods = [m for m in mods if m != "__init__"]
    bad = {}
    for m in mods:
        r = _run([sys.executable, "-c", f"import tickr.{m}"], cwd=str(repo),
                 timeout=60, env={"PYTHONPATH": str(repo),
                                  "PYTHONDONTWRITEBYTECODE": "1"})
        if r.returncode != 0:
            bad[m] = r.stderr.strip().splitlines()[-1][:200] if r.stderr else "?"
    return {"modules": mods, "failed": bad,
            "ok": len(mods) > 0 and not bad}


# --------------------------------------------------------------- 4. own tests
_PYTEST_TAIL = re.compile(r"(\d+) (passed|failed|error)")


def own_tests(repo: Path, timeout: int = 600) -> dict:
    if not (repo / "tests").exists():
        return {"ran": False, "reason": "no tests/ directory"}
    try:
        r = _run([sys.executable, "-m", "pytest", "tests", "-q", "--tb=no",
                  "-p", "no:cacheprovider"], cwd=str(repo), timeout=timeout,
                 env={"PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"})
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "timeout"}
    tail = (r.stdout or "")[-800:]
    counts = {k: 0 for k in ("passed", "failed", "error")}
    for n, k in _PYTEST_TAIL.findall(tail):
        counts[k] = int(n)
    return {"ran": True, "rc": r.returncode, "green": r.returncode == 0,
            **counts, "tail": tail.strip().splitlines()[-1:] }


# --------------------------------------------------------------- 5. size
def repo_stats(repo: Path) -> dict:
    files = _py_files(repo)
    src = [f for f in files if f.relative_to(repo).parts[0] == "tickr"]
    tst = [f for f in files if f.relative_to(repo).parts[0] == "tests"]
    def loc(fs):
        return sum(len([l for l in f.read_text(errors="replace").splitlines()
                        if l.strip()]) for f in fs)
    return {"py_files": len(files), "src_files": len(src), "test_files": len(tst),
            "src_loc": loc(src), "test_loc": loc(tst)}


def grade(repo: Path, turn_index: int) -> dict:
    """Every signal for one snapshot. turn_index is 1-based."""
    out = {
        "imports": import_health(repo),
        "own_tests": own_tests(repo),
        "stale": stale_sites(repo),
        "stats": repo_stats(repo),
        "conformance": conformance(repo),
    }
    # The completeness headline for this snapshot: which staleness rule applies.
    s = out["stale"]
    key = "stale_indicator_calls_post_t4" if turn_index >= 4 else "stale_indicator_calls_pre_t4"
    broken = len(s[key])
    if turn_index >= 5:
        broken += len(s["stale_renamed_refs"]) + len(s["stale_alerts_module_refs"])
        broken += 1 if s["alerts_py_still_exists"] else 0
    out["broken_sites"] = broken
    return out


if __name__ == "__main__":
    repo = Path(sys.argv[1]).resolve()
    ti = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    print(json.dumps(grade(repo, ti), indent=2))
