#!/usr/bin/env python3
"""Build one WIDE task (scoring/wide_eval.py) from a spec and a gold patch.

spec JSON: instance_id, repo (the language scorer's repo key), lang,
base_commit, old, new, instruction (the agent's prompt body), gold_patch
(path to a unified diff made by a type-aware refactoring tool), source
("pr:<sha>" or "seeded"), optional notes.

Steps:
  1. base/gold token counts over every code file (wide_eval.token_counts);
     the base must differ from gold, or there is nothing to do.
  2. test selection: test files/classes/functions that mention `old` at base;
  3. run them with the gold patch; pass_to_pass = the ones that pass (minus
     tests whose own name contains `old`, which the rename may change).
Writes tasks/e2e/<instance_id>.json with kind="wide".

usage: build_wide.py <spec.json> [--dry-run]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

H = Path(__file__).resolve().parent.parent
for d in (H / "scoring", H / "runners"):
    sys.path.insert(0, str(d))
import wide_eval  # noqa: E402

TEST_PATH = {
    "python": re.compile(r"(^|/)tests?/.*\.py$|(^|/)test_[^/]*\.py$|_test\.py$"),
    "java": re.compile(r"(^|/)src/test/java/.*\.java$"),
    "go": re.compile(r"_test\.go$"),
    "ts": re.compile(r"\.(test|spec)\.(ts|tsx|js|mjs)$|(^|/)(test|tests|__tests__)/"),
}


def _tests_mentioning(counts: dict, lang: str) -> list[str]:
    return sorted(f for f, (o, _) in counts.items() if o and TEST_PATH[lang].search(f))


def _java_class(path: str) -> str:
    return path.split("src/test/java/", 1)[1][:-5].replace("/", ".")


def _go_test_funcs(repo: Path, base: str, files: list[str]) -> list[str]:
    """Every Test* function in the packages (directories) of these files."""
    dirs = sorted({str(Path(f).parent) for f in files})
    funcs = []
    for d in dirs:
        listing = wide_eval._sh("git", "-C", str(repo), "ls-tree", "--name-only", base, d + "/")
        for f in listing.splitlines():
            if f.endswith("_test.go"):
                src = wide_eval._sh("git", "-C", str(repo), "show", f"{base}:{f}")
                funcs += re.findall(r"^func (Test\w+)\(", src, re.M)
    return sorted(set(funcs))


def run_gold_tests(task: dict, gold: str, repo: Path) -> dict:
    lang = task["lang"]
    if lang == "java":
        import java_eval
        # the same JDK java_eval.score picks for this commit's era
        img = java_eval.image_for(java_eval.commit_date(repo, task["base_commit"]))
        return java_eval._run_tests(repo, task["base_commit"], [gold], task["test_classes"], image=img)
    if lang == "go":
        import go_eval
        return go_eval._run_tests(repo, task["base_commit"], [gold], task["test_functions"])
    if lang == "ts":
        import js_eval
        return js_eval._run_tests(repo, task["repo"], task["base_commit"], [gold])
    import docker_eval
    r, wt = docker_eval._worktree(task, [gold])
    try:
        return docker_eval._run_tests_in_docker(task, wt).outcomes
    finally:
        docker_eval._cleanup(r, wt)


def build(spec: dict, dry: bool = False) -> dict:
    gold = Path(spec["gold_patch"]).read_text()
    task = {k: v for k, v in spec.items() if k != "gold_patch"}
    task.update(kind="wide", patch=gold, test_patch="", fail_to_pass=[],
                problem_statement=spec["instruction"], prompt_source="wide-mandate")
    repo = wide_eval.repo_dir(task)
    if task.get("site_mode") == "files":
        return _build_files_mode(task, gold, repo, dry)
    base_wt = wide_eval._checkout(repo, task["base_commit"], "")
    gold_wt = wide_eval._checkout(repo, task["base_commit"], gold)
    try:
        task["base_counts"] = wide_eval.token_counts(base_wt, task["old"], task["new"])
        task["gold_counts"] = wide_eval.token_counts(gold_wt, task["old"], task["new"])
    finally:
        shutil.rmtree(base_wt, ignore_errors=True)
        shutil.rmtree(gold_wt, ignore_errors=True)
    if task["base_counts"] == task["gold_counts"]:
        raise SystemExit("gold does not change any old/new token count")
    tests = _tests_mentioning(task["base_counts"], task["lang"])
    task["test_modules"] = []  # the agent edits tests too; nothing is excluded from its diff
    task["wide_test_files"] = tests
    if task["lang"] == "java":
        task["test_classes"] = [_java_class(f) for f in tests]
    elif task["lang"] == "go":
        task["test_functions"] = _go_test_funcs(repo, task["base_commit"], tests)
    elif task["lang"] == "python":
        task["test_modules"] = tests  # pytest selection; see note below
    res = run_gold_tests(task, gold, repo)
    passed = sorted(n for n, s in res.items() if s == "PASSED"
                    and not re.search(rf"\b{re.escape(task['old'])}\b", n))
    task["pass_to_pass"] = passed
    task["gold_test_outcomes"] = {"run": len(res), "passed": len(passed),
                                  "failed": sorted(n for n, s in res.items() if s != "PASSED")[:30]}
    task["gold_sites"] = sum(max(0, v[0] - task["gold_counts"].get(f, [0, 0])[0])
                             for f, v in task["base_counts"].items())
    if not dry:
        (H / "tasks/e2e" / f"{task['instance_id']}.json").write_text(json.dumps(task, indent=1))
    return task


def _build_files_mode(task: dict, gold: str, repo: Path, dry: bool) -> dict:
    """Signature-change task from a real commit (spec adds site_mode="files",
    gold_files, stale_patterns, and for go/java/python the test selection:
    test_functions / test_classes / test_modules). Every stale pattern must
    match at base and be gone at gold, or the oracle could not tell them apart."""
    gold_touched = {l[6:] for l in gold.splitlines() if l.startswith("+++ b/")}
    if not set(task["gold_files"]) <= gold_touched:
        raise SystemExit(f"gold_files not in gold patch: {sorted(set(task['gold_files']) - gold_touched)}")
    base_wt = wide_eval._checkout(repo, task["base_commit"], "")
    gold_wt = wide_eval._checkout(repo, task["base_commit"], gold)
    try:
        at_base = wide_eval.stale_hits(base_wt, task["stale_patterns"])
        at_gold = wide_eval.stale_hits(gold_wt, task["stale_patterns"])
    finally:
        shutil.rmtree(base_wt, ignore_errors=True)
        shutil.rmtree(gold_wt, ignore_errors=True)
    absent = {f: [p for p in ps if p not in at_base.get(f, [])] for f, ps in task["stale_patterns"].items()}
    if any(absent.values()) or at_gold:
        raise SystemExit(f"stale patterns must match at base and not at gold: absent at base {absent}, left at gold {at_gold}")
    task.setdefault("test_modules", [])
    res = run_gold_tests(task, gold, repo)
    # the agent's checkout has only the base tests: require those passing both sides
    at_base = run_gold_tests(task, "", repo)
    task["pass_to_pass"] = sorted(n for n, s in res.items() if s == "PASSED" and at_base.get(n) == "PASSED")
    task["gold_test_outcomes"] = {"run": len(res), "passed": len(task["pass_to_pass"]),
                                  "new_or_failing_at_base": sum(1 for n, s in res.items() if s == "PASSED" and at_base.get(n) != "PASSED"),
                                  "failed": sorted(n for n, s in res.items() if s != "PASSED")[:30]}
    if not task["pass_to_pass"]:
        raise SystemExit("no test passes with gold: the green layer would be empty")
    # a gold test file with no passing test means it never ran (collection
    # error, missing deps): the green layer would not guard this change
    # (python: only files pytest collects; tests/typing/*.py-style fixtures are type-check only)
    collected = (lambda f: re.search(r"(^|/)(test_[^/]*|[^/]*_test)\.py$", f)) if task["lang"] == "python" \
        else TEST_PATH[task["lang"]].search
    silent = [f for f in task["gold_files"] if collected(f)
              and not any(n.startswith(f) for n in task["pass_to_pass"])]
    if silent:
        raise SystemExit(f"gold test files with no passing tests (did they run?): {silent}")
    task["gold_sites"] = len(task["gold_files"])
    # the scorer is stricter than the outcome table (a collection error anywhere
    # fails green): refuse a task its own gold cannot resolve
    gold_score = wide_eval.score(task, gold)
    if not gold_score.get("resolved"):
        raise SystemExit(f"gold does not resolve under the scorer: {json.dumps(gold_score)[:600]}")
    if not dry:
        (H / "tasks/e2e" / f"{task['instance_id']}.json").write_text(json.dumps(task, indent=1))
    return task


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    t = build(spec, dry="--dry-run" in sys.argv)
    print(json.dumps({k: t.get(k) for k in ("instance_id", "gold_sites", "wide_test_files",
                                            "gold_test_outcomes")}, indent=1))
