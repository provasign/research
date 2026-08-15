"""Offline, zero-cost checks for swebench_ab.py's own mechanics — no API
calls. Run before spending any money on agent cells: python3 -m pytest
test_swebench_ab.py, or just: python3 test_swebench_ab.py

History: the 2026-08-11 grep-denial bug (prism arm silently kept full grep
access — --allowedTools omission is not a deny in headless mode; only
--disallowedTools is) was found live, by hand, after >$100 of cells had
already run under the broken assumption. That was fixed with a harness-side
--disallowedTools construction, verified here through 2026-08-14.

2026-08-14: superseded. v0.50.0 shipped prism's own PreToolUse hook as the
real deployment mechanism (explains the denial back to the model; a bare
--disallowedTools does not, and was measured live to change recovery
behavior). The harness now runs the REAL `prism init --deny-builtin-search`
inside the prism-arm worktree instead of simulating it — these checks were
rewritten to match. This file is still where this class of check belongs:
verified for free, before the first paid cell.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import swebench_ab as ab  # noqa: E402


def test_prism_arm_runs_real_init_and_never_disallows_search_tools():
    """The prism arm must invoke the real `prism init --deny-builtin-search`
    in the worktree (the actual shipped mechanism, v0.50.0+) rather than
    simulating denial via --disallowedTools. --allowedTools must include
    Grep/grep/rg unmodified for both arms now — the worktree's own
    .claude/settings.json (hook + deny, written by that init call) is what
    actually blocks them, not the harness's tool list."""
    calls = []
    init_calls = []

    def fake_run_agent(prompt, tools, workdir, model="", mcp="", disallowed=None):
        calls.append({"tools": tools, "disallowed": disallowed, "mcp": mcp})
        return {"tool_trace": [], "num_turns": 0, "total_cost_usd": 0,
                "usage": {}, "_wall_s": 0, "_timed_out": False}

    def fake_subprocess_run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "init":
            init_calls.append(cmd)
        return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()

    orig_run_agent, orig_subprocess_run = ab.run_agent, ab.subprocess.run
    orig_mark, orig_unmark = ab.mark_trusted, ab.unmark_trusted
    ab.run_agent = fake_run_agent
    ab.subprocess.run = fake_subprocess_run
    ab.mark_trusted = lambda path: None
    ab.unmark_trusted = lambda path: None
    try:
        import tempfile
        ab.WT_ROOT = Path(tempfile.mkdtemp())
        ab.ensure_repo = lambda repo: ab.WT_ROOT
        BASE = "deadbeef" * 5
        # rev-parse HEAD must echo the base commit or run_arm now refuses to
        # run (the 2026-08-15 wrong-code guard); everything else returns "".
        def fake_sh(*a, **k):
            out = BASE if ("rev-parse" in a and "HEAD" in a) else ""
            return type("R", (), {"stdout": out, "returncode": 0})()
        ab.sh = fake_sh
        task = {"instance_id": "x", "repo": "a/b", "base_commit": BASE,
                "problem_statement": "p"}
        ab.run_arm(task, "prism", "prism")
        ab.run_arm(task, "baseline", "prism")
    finally:
        ab.run_agent, ab.subprocess.run = orig_run_agent, orig_subprocess_run
        ab.mark_trusted, ab.unmark_trusted = orig_mark, orig_unmark

    prism_call, baseline_call = calls[0], calls[1]

    assert len(init_calls) == 1, (
        f"prism arm must run `prism init --deny-builtin-search` exactly once "
        f"in the worktree — the actual v0.50.0+ deployment mechanism, got {init_calls}")
    assert "--deny-builtin-search" in init_calls[0], (
        f"init call must pass --deny-builtin-search: {init_calls[0]}")

    for name in ("Grep", "Bash(grep:*)", "Bash(rg:*)"):
        assert name in prism_call["tools"], (
            f"prism arm's --allowedTools must include {name} unmodified now — "
            f"the worktree's own settings.json (hook + deny) does the blocking, "
            f"not the harness's tool list")
    assert prism_call["disallowed"] is None, (
        "prism arm must not pass --disallowedTools anymore — that was the "
        "pre-v0.50.0 simulation; the real init-generated hook/deny is what "
        "blocks grep now, and a harness-side --disallowedTools duplicate "
        "would mask a regression in the real mechanism")
    assert "mcp__prism" in prism_call["tools"]
    assert prism_call["mcp"].endswith(".mcp.json"), (
        f"prism arm must point --mcp-config at the worktree's own .mcp.json "
        f"(written by init), not a shared static file: {prism_call['mcp']}")

    assert baseline_call["disallowed"] is None
    assert "mcp__prism" not in baseline_call["tools"]
    assert baseline_call["mcp"] == ""

    print("OK: prism arm runs the real `prism init --deny-builtin-search` in the "
          "worktree, keeps Grep/grep/rg in --allowedTools, passes no "
          "--disallowedTools; baseline is unaffected")


if __name__ == "__main__":
    test_prism_arm_runs_real_init_and_never_disallows_search_tools()
