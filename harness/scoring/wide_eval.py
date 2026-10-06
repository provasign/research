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

Signature-change tasks (site_mode="files") replace oracle 1 with
file_site_check: every gold_files entry touched and no stale_patterns left.

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


def _strip_comments_and_strings(path: str, text: str) -> str:
    """Code with comments and string-literal text blanked. A name inside a
    string (a test title "Should return empty remote", an assertion message
    "all Route() calls ...") is prose, not a reference: agents that update it
    were scored as over-renaming (seeded32, 2026-10-05). Code inside f-string
    / template-literal braces is kept: f"{x.render()}" and `${x.push()}` are
    real call sites. Python docstrings are strings, so they go too."""
    ext = Path(path).suffix
    py = ext == ".py"
    out, i, n = [], 0, len(text)

    def keep_braced(j: int, close_at: str) -> int:
        """Copy an interpolation body {...} (nested braces) through, return index after it."""
        depth = 1
        out.append("{")
        j += 1
        while j < n and depth:
            ch = text[j]
            depth += ch == "{"
            depth -= ch == "}"
            out.append(ch if depth else "}")
            j += 1
        return j

    while i < n:
        c = text[i]
        # comments
        if py and c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if not py and text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if not py and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("\n" * text.count("\n", i, j))
            i = j
            continue
        # strings
        if py and c in "\"'":
            # prefix letters (f, r, b, rb, fr ...) were already emitted; detect f
            k = len(out) - 1
            prefix = ""
            while k >= 0 and out[k].isalpha() and len(prefix) < 3:
                prefix = out[k] + prefix
                k -= 1
            fstr = "f" in prefix.lower() and (k < 0 or not (out[k].isalnum() or out[k] == "_"))
            q = text[i:i + 3] if text[i:i + 3] in ("\"\"\"", "\'\'\'") else c
            j = i + len(q)
            out.append(" ")
            while j < n and not text.startswith(q, j):
                if text[j] == "\\":
                    j += 2
                    continue
                if fstr and text[j] == "{":
                    if text.startswith("{{", j):
                        j += 2
                        continue
                    j = keep_braced(j, "}")
                    continue
                if text[j] == "\n":
                    out.append("\n")
                j += 1
            i = j + len(q)
            out.append(" ")
            continue
        if not py and c in "\"'`":
            if c == "'" and ext in (".go", ".java", ".kt") :
                # rune / char literal: 'x', '\n'
                j = i + 1
                while j < n and text[j] != "'" and text[j] != "\n":
                    j += 2 if text[j] == "\\" else 1
                i = j + 1
                out.append(" ")
                continue
            q = '"""' if c == '"' and text.startswith('"""', i) and ext in (".java", ".kt") else c
            j = i + len(q)
            out.append(" ")
            while j < n and not text.startswith(q, j):
                if text[j] == "\\" and not (c == "`" and ext == ".go"):
                    j += 2
                    continue
                if c == "`" and ext != ".go" and text.startswith("${", j):
                    j = keep_braced(j + 1, "}")
                    continue
                if text[j] == "\n":
                    out.append("\n")
                    if q in ("\"", "'"):
                        break  # unterminated single-line string: stop at end of line
                j += 1
            i = j + len(q)
            out.append(" ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def token_counts(root: Path, old: str, new: str) -> dict[str, list[int]]:
    """{relative code file: [old count, new count]} for files with either."""
    ro, rn = re.compile(rf"\b{re.escape(old)}\b"), re.compile(rf"\b{re.escape(new)}\b")
    out = {}
    files = _sh("git", "-C", str(root), "ls-files", "-co", "--exclude-standard").splitlines()
    for rel in files:
        if Path(rel).suffix not in CODE_EXT or SKIP_DIR.search(rel):
            continue
        try:
            text = _strip_comments_and_strings(rel, (root / rel).read_text(errors="ignore"))
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


def stale_hits(root: Path, stale: dict) -> dict[str, list[str]]:
    """{file: [pattern, ...]} -> the patterns still matching in root's files."""
    hits = {}
    for f, pats in stale.items():
        p = root / f
        text = p.read_text(errors="replace") if p.exists() else ""
        left = [pat for pat in pats if re.search(pat, text, re.M)]
        if left:
            hits[f] = left
    return hits


def file_site_check(repo: Path, task: dict, patch: str) -> dict:
    """site_mode="files" (signature changes, where old/new token counts mean
    nothing): the patch must touch every gold file, and none of the task's
    stale_patterns (old call/override shapes, absent from the gold tree) may
    remain. Touching alone is not a fix; the stale patterns catch that."""
    touched = {l[6:] for l in patch.splitlines() if l.startswith("+++ b/")}
    missed = [f for f in task["gold_files"] if f not in touched]
    wt = _checkout(repo, task["base_commit"], patch)
    try:
        stale = stale_hits(wt, task.get("stale_patterns", {}))
    finally:
        shutil.rmtree(wt, ignore_errors=True)
    return {"sites_ok": not missed and not stale, "gold_files": len(task["gold_files"]),
            "missed_files": missed, "stale": stale}


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
        check = file_site_check if task.get("site_mode") == "files" else site_check
        sites = check(repo_dir(task), task, agent_patch)
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
