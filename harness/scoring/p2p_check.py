"""pass_to_pass check shared by the language scorers.

Strict by default: every pass_to_pass test must have PASSED. Seeded wide
tasks (wide_eval sets task["p2p_allow_renames"]) also accept a pass_to_pass
test that is MISSING because the agent renamed it along with the code under
test: 2026-10-10, both arms of deep__rich__loop_helpers_value_first renamed
test_loop_first -> test_iter_first together with loop_first -> iter_first and
were scored unresolved although every test passed. A missing test is
accepted only when its group (test file / class) has no failure and still
ran at least as many passing tests as pass_to_pass expects from it, so a
deleted test (count drops) or a failing one still fails.
"""


def group(name: str) -> str:
    for sep in ("::", " > "):
        if sep in name:
            return name.split(sep, 1)[0]
    return ""  # e.g. Go test names: the whole run is one group


def p2p_ok(res: dict, task: dict, ok=lambda r, n: r.get(n) == "PASSED") -> bool:
    p2p = task.get("pass_to_pass", []) or []
    if not task.get("p2p_allow_renames"):
        return all(ok(res, n) for n in p2p)
    missing = [n for n in p2p if n not in res]
    if any(not ok(res, n) for n in p2p if n in res):
        return False
    for g in {group(n) for n in missing}:
        in_group = [n for n in res if group(n) == g]
        if any(res[n] in ("FAILED", "ERROR") for n in in_group):
            return False
        expected = sum(1 for n in p2p if group(n) == g)
        if sum(1 for n in in_group if res[n] == "PASSED") < expected:
            return False
    return True
