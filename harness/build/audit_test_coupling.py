#!/usr/bin/env python3
"""Flag tasks whose hidden tests depend on names only the gold fix invents.

A hidden test that calls a function, class or constant the gold patch
introduces -- one that exists nowhere at the base commit and that the issue
never names -- can only pass if the agent guesses that exact name. Found
2026-09-30: werkzeug pr3038 (DuplicateRuleError) and rich pr3938
(split_lines_terminator) were failed by every arm in every run; urllib3
pr5020's test module imports two gold-only private helpers, so the whole
module fails to load and 394 tests score as failed for any other fix.

For each task:
  - names defined on '+' lines of the gold patch (functions, methods,
    classes, types, exception classes, module constants)
  - kept if absent from the base tree (git grep at base_commit) and not in
    the issue text
  - flagged if the test patch's added lines use them; IMPORT marks a
    module-level import, which breaks every test in that file

Severity: UNWINNABLE when any fail-to-pass test needs a gold-only name
(resolution requires all of them); TESTS-IMPORT-GOLD-ONLY when a test file
imports one at module level (breaks that file for any other fix, e.g. a
fan-out task's green check); USED-NOT-IN-F2P otherwise.

Usage: python3 build/audit_test_coupling.py [tasks/e2e ...] [--json out.json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HERE / "runners"), str(HERE / "scoring")]

DEF_PATTERNS = [
    re.compile(r"^\+\s*(?:async\s+)?def\s+(\w+)"),                      # python
    re.compile(r"^\+\s*class\s+(\w+)"),                                 # python/java/ts
    re.compile(r"^\+\s*func\s+(?:\([^)]*\)\s*)?(\w+)"),                  # go
    re.compile(r"^\+\s*type\s+(\w+)\s"),                                # go
    re.compile(r"^\+\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)"),  # js/ts
    re.compile(r"^\+\s*export\s+(?:const|let|class|interface|type|enum)\s+(\w+)"),     # ts
    re.compile(r"^\+\s*(?:public|protected|private|static|final|abstract|synchronized|\s)+"
               r"[\w<>\[\],.? ]+?\s+(\w+)\s*\("),                        # java methods
    re.compile(r"^\+\s*(?:public|protected|private|static|final|\s)*(?:class|interface|enum|record)\s+(\w+)"),
    re.compile(r"^\+([A-Z][A-Z0-9_]{3,})\s*="),                          # module constants
]
KEYWORDS = {"if", "for", "while", "return", "switch", "catch", "new", "super", "this", "main", "init", "test", "setUp"}


def gold_defined(patch: str) -> set[str]:
    names = set()
    for line in patch.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for rx in DEF_PATTERNS:
            m = rx.match(line)
            if m and len(m.group(1)) > 3 and m.group(1) not in KEYWORDS:
                names.add(m.group(1))
    return names


def exists_at_base(repo: Path, base: str, name: str) -> bool:
    r = subprocess.run(["git", "-C", str(repo), "grep", "-q", "-w", name, base, "--"],
                       capture_output=True)
    return r.returncode == 0


def test_files(test_patch: str) -> dict[str, str]:
    """Added lines per test file in the test patch."""
    files, cur = {}, None
    for line in test_patch.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            files[cur] = ""
        elif cur and line.startswith("+") and not line.startswith("+++"):
            files[cur] += line[1:] + "\n"
    return files


def module_level_imports(src: str) -> set[str]:
    """Names imported at module level, including parenthesized multi-line
    Python imports, Java/Go single imports and JS/TS named imports."""
    names: set[str] = set()
    for m in re.finditer(r"^from\s+\S+\s+import\s*\((.*?)\)", src, re.S | re.M):
        names |= set(re.findall(r"\w+", m.group(1)))
    for m in re.finditer(r"^(?:from\s+\S+\s+)?import\s+([^\n(]+)$", src, re.M):
        names |= set(re.findall(r"\w+", m.group(1)))
    for m in re.finditer(r"^import\s*\{(.*?)\}\s*from", src, re.S | re.M):
        names |= set(re.findall(r"\w+", m.group(1)))
    # A name added inside an existing import block: the diff carries only
    # "    _normalize_header_value," while "from x import (" is context.
    names |= set(re.findall(r"^\s+(\w+),?\s*(?:#.*)?$", src, re.M))
    return names


def audit(task: dict) -> dict | None:
    import run_e2e
    repo = run_e2e._repo_for(task)
    issue = task.get("problem_statement", "")
    candidates = [n for n in gold_defined(task.get("patch", ""))
                  if n not in issue and not exists_at_base(repo, task["base_commit"], n)]
    if not candidates:
        return None
    files = test_files(task.get("test_patch", ""))
    hits = {}
    for f, added in files.items():
        for n in candidates:
            if re.search(r"\b" + re.escape(n) + r"\b", added):
                imported = n in module_level_imports(added)
                hits.setdefault(f, []).append((n, imported))
    if not hits:
        return None
    f2p = task.get("fail_to_pass") or []
    poisoned_files = {f for f, ns in hits.items() if any(imp for _, imp in ns)}

    def affected(test_id: str) -> bool:
        file = test_id.split("::")[0]
        if any(file.endswith(pf) or pf.endswith(file) for pf in poisoned_files):
            return True
        name = test_id.split("::")[-1].split("[")[0].split(".")[-1]
        for f, ns in hits.items():
            body = files[f]
            m = re.search(r"(def|func|void|test\(|it\()\s*['\"]?" + re.escape(name) + r"\b(.*?)(?=\n\s*(def |func |@Test|public void |test\(|it\()|\Z)", body, re.S)
            if m and any(re.search(r"\b" + re.escape(n) + r"\b", m.group(2)) for n, _ in ns):
                return True
        return False

    hit_f2p = [t for t in f2p if affected(t)]
    # Resolution needs every fail-to-pass test green, so one test that needs a
    # gold-only name makes the task unwinnable for any other fix.
    severity = "UNWINNABLE" if hit_f2p else "TESTS-IMPORT-GOLD-ONLY" if poisoned_files else "USED-NOT-IN-F2P"
    return {"task": task["instance_id"], "severity": severity,
            "gold_only_names_in_tests": sorted({n for ns in hits.values() for n, _ in ns}),
            "module_level_import_in": sorted(poisoned_files),
            "f2p_affected": len(hit_f2p), "f2p_total": len(f2p)}


def main(argv: list[str]) -> int:
    out = None
    if "--json" in argv:
        out = argv[argv.index("--json") + 1]
        argv = [a for a in argv if a not in ("--json", out)]
    dirs = argv or [str(HERE / "tasks" / "e2e")]
    results = []
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            task = json.loads(p.read_text())
            if not isinstance(task, dict) or not task.get("patch") or not task.get("test_patch"):
                continue
            try:
                r = audit(task)
            except Exception as e:  # noqa: BLE001
                print(f"  {p.stem}: audit error {type(e).__name__}: {e}")
                continue
            if r:
                results.append(r)
                print(f"{r['severity']:16} {r['task']:48} f2p {r['f2p_affected']}/{r['f2p_total']}  "
                      f"names {r['gold_only_names_in_tests']}  import-level {r['module_level_import_in'] or '-'}")
    print(f"\n{len(results)} task(s) flagged")
    if out:
        Path(out).write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
