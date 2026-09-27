"""Score and validate WIDE tasks: a mandated rename across a repository.

A wide task tells the agent to rename one identifier (a type, method or
field, named with its owner when the name is shared) everywhere it refers
to that symbol, tests included. Two oracles, both required:

  1. sites: in every code file, the number of `old` and `new` identifier
     tokens (comments stripped) must equal the gold tree's. A leftover `old`
     is a missed site; a renamed look-alike (same name, different symbol)
     shows up as `old` too low / `new` too high. Counts, not line numbers,
     so an equivalent edit that moves code still scores.
  2. green: the project builds and the tests that pass with the gold rename
     (and already existed at base) still pass -- the language's own scorer
     (java_eval / go_eval / js_eval / docker_eval) with no test_patch and no
     fail_to_pass, only pass_to_pass.

Task fields beyond the language scorer's: kind="wide", old, new,
gold_counts / base_counts {file: [old, new]} over every code file that
contains either name in the gold / base tree. The builder fills both, and
pass_to_pass.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_H = Path(__file__).resolve().parent.parent
for _d in (_H / "scoring", _H / "runners"):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

CODE_EXT = {".java", ".go", ".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".py", ".kt"}
SKIP_DIR = re.compile(r"(^|/)(node_modules|vendor|third_party|dist|build|target|\.git)(/|$)")
_C_COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_PY_COMMENTS = re.compile(r"#[^\n]*")


def _sh(*a, cwd=None, timeout=900, check=True) -> str:
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{a[:4]}: {r.stderr[-800:]}")
    return r.stdout


def _py_docstrings(text: str) -> list[tuple[int, int, int, int]]:
    """(start line, start col, end line, end col) of every docstring: the
    documentation twin of a C-family comment, so neither counts as a site."""
    import ast
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                d = body[0].value
                spans.append((d.lineno, d.col_offset, d.end_lineno, d.end_col_offset))
    return spans


def _strip_comments(path: str, text: str) -> str:
    if path.endswith(".py"):
        lines = text.split("\n")
        for l0, c0, l1, c1 in sorted(_py_docstrings(text), reverse=True):
            if l0 == l1:
                ln = lines[l0 - 1]
                lines[l0 - 1] = ln[:c0] + ln[c1:]
            else:
                lines[l0 - 1] = lines[l0 - 1][:c0]
                for i in range(l0, l1 - 1):
                    lines[i] = ""
                lines[l1 - 1] = lines[l1 - 1][c1:]
        return _PY_COMMENTS.sub("", "\n".join(lines))
    return _C_COMMENTS.sub("", text)


def token_counts(root: Path, old: str, new: str) -> dict[str, list[int]]:
    """{relative code file: [old count, new count]} for files with either."""
    ro, rn = re.compile(rf"\b{re.escape(old)}\b"), re.compile(rf"\b{re.escape(new)}\b")
    out = {}
    files = _sh("git", "-C", str(root), "ls-files", "-co", "--exclude-standard").splitlines()
    for rel in files:
        if Path(rel).suffix not in CODE_EXT or SKIP_DIR.search(rel):
            continue
        try:
            text = _strip_comments(rel, (root / rel).read_text(errors="ignore"))
        except OSError:
            continue
        o, n = len(ro.findall(text)), len(rn.findall(text))
        if o or n:
            out[rel] = [o, n]
    return out


def _checkout(repo: Path, base: str, patch: str) -> Path:
    wt = Path(tempfile.mkdtemp(prefix="wide-eval-"))
    _sh("git", "clone", "--local", "--no-checkout", "--quiet", str(repo), str(wt), timeout=900)
    _sh("git", "-C", str(wt), "checkout", "--detach", "-f", "-q", base, timeout=900)
    if patch.strip():
        p = wt / ".wide.patch"
        p.write_text(patch)
        r = subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn", str(p)],
                           capture_output=True, text=True)
        p.unlink()
        if r.returncode != 0:
            shutil.rmtree(wt, ignore_errors=True)
            raise RuntimeError(f"patch does not apply: {r.stderr[-400:]}")
    return wt


def site_check(repo: Path, task: dict, patch: str) -> dict:
    """Compare the patched tree's token counts with the gold tree's."""
    wt = _checkout(repo, task["base_commit"], patch)
    try:
        got = token_counts(wt, task["old"], task["new"])
    finally:
        shutil.rmtree(wt, ignore_errors=True)
    gold = task["gold_counts"]
    base = task.get("base_counts", {})
    missed, over, other = [], [], []
    for f in sorted(set(gold) | set(got)):
        want = gold.get(f, [0, 0])
        have = got.get(f, [0, 0])
        if have == want:
            continue
        entry = {"file": f, "want": want, "got": have}
        if have[0] > want[0]:
            missed.append(entry)       # old name left where gold renamed it
        elif have[0] < want[0] or have[1] > want[1]:
            over.append(entry)         # renamed a look-alike / invented uses
        else:
            other.append(entry)        # e.g. deleted uses of the new name
    gold_sites = sum(max(0, v[0] - gold.get(f, [0, 0])[0]) for f, v in base.items())
    missed_sites = sum(e["got"][0] - e["want"][0] for e in missed)
    return {"sites_ok": not (missed or over or other), "gold_sites": gold_sites,
            "missed_sites": missed_sites, "missed": missed[:20], "over": over[:20],
            "other": other[:20]}


def _lang_score(task: dict, patch: str) -> dict:
    """The language's own build+test scorer, pass_to_pass only."""
    import run_e2e  # the dispatch table and repo lookup live there
    t = dict(task, kind=None, test_patch="", fail_to_pass=[])
    if task["lang"] == "go":
        import go_eval
        return go_eval.score(go_eval.REPO_DIR[t["repo"]], t, patch)
    if task["lang"] in ("js", "ts"):
        mod = run_e2e._LANG_EVAL[task["lang"]]
        return mod.score(mod.REPO_DIR[t["repo"]], t["repo"], t, patch)
    if task["lang"] == "java":
        import java_eval
        return java_eval.score(java_eval.REPO_DIR[t["repo"]], t, patch)
    import docker_eval
    return docker_eval.score(t, patch)


def repo_dir(task: dict) -> Path:
    import run_e2e
    return run_e2e._repo_for(task)


def score(task: dict, agent_patch: str) -> dict:
    if not agent_patch.strip():
        return {"resolved": False, "empty_diff": True}
    try:
        sites = site_check(repo_dir(task), task, agent_patch)
    except RuntimeError as e:
        return {"resolved": False, "error": str(e)[:300]}
    green = _lang_score(task, agent_patch)
    return {"resolved": bool(sites["sites_ok"] and green.get("resolved")),
            "sites_ok": sites["sites_ok"], "green": green.get("resolved"),
            "sites": sites, "tests": {k: v for k, v in green.items() if k != "resolved"}}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("task_json")
    ap.add_argument("--score", help="agent diff to score")
    a = ap.parse_args()
    task = json.loads(Path(a.task_json).read_text())
    print(json.dumps(score(task, Path(a.score).read_text()), indent=2))
