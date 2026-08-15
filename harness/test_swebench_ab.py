"""Offline, zero-cost checks for swebench_ab.py's own mechanics — no API
calls. Run before spending any money on agent cells: python3 -m pytest
test_swebench_ab.py, or just: python3 test_swebench_ab.py

History: the 2026-08-11 grep-denial bug (prism arm silently kept full grep
access — --allowedTools omission is not a deny in headless mode; only
--disallowedTools is) was found live, by hand, after >$100 of cells had
already run under the broken assumption. That was fixed with a harness-side
--disallowedTools construction, verified here through 2026-08-14.

2026-08-14: superseded. v0.50.0 shipped prism's own PreToolUse hook as the
real deployment mechanism, so the harness ran the REAL `prism init
--deny-builtin-search` inside the prism-arm worktree instead of simulating
denial.

2026-08-15: superseded AGAIN, in the other direction. v0.52.0 reverted the
whole denial arc — no hook ships, and `prism init` writes no deny rules. The
harness kept passing --deny-builtin-search for three prism releases after
that, so every prism-arm cell ran with grep/rg blocked: a configuration no
user gets, which makes "the agent used prism" unfalsifiable. Found in the
v054-smoke traces (4 denied greps in the prism arm, 0 in baseline). The
contract is now the inverse of what this file asserted a day earlier, which
is exactly why it is asserted rather than remembered.

This file is still where this class of check belongs: verified for free,
before the first paid cell.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import swebench_ab as ab  # noqa: E402


def _run_both_arms():
    """Drive run_arm for both arms with every side effect stubbed out."""
    calls, init_calls = [], []

    def fake_run_agent(prompt, tools, workdir, model="", mcp="", disallowed=None):
        calls.append({"tools": tools, "disallowed": disallowed, "mcp": mcp,
                      "prompt": prompt})
        return {"tool_trace": [], "num_turns": 0, "total_cost_usd": 0,
                "usage": {}, "_wall_s": 0, "_timed_out": False}

    def fake_subprocess_run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "init":
            init_calls.append(cmd)
        return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()

    orig = (ab.run_agent, ab.subprocess.run, ab.mark_trusted, ab.unmark_trusted, ab.sh)
    ab.run_agent = fake_run_agent
    ab.subprocess.run = fake_subprocess_run
    ab.mark_trusted = lambda path: None
    ab.unmark_trusted = lambda path: None
    try:
        import tempfile
        ab.WT_ROOT = Path(tempfile.mkdtemp())
        ab.ensure_repo = lambda repo: ab.WT_ROOT
        BASE = "deadbeef" * 5
        # rev-parse HEAD must echo the base commit or run_arm refuses to run
        # (the 2026-08-15 wrong-code guard); everything else returns "".
        def fake_sh(*a, **k):
            out = BASE if ("rev-parse" in a and "HEAD" in a) else ""
            return type("R", (), {"stdout": out, "returncode": 0})()
        ab.sh = fake_sh
        task = {"instance_id": "x", "repo": "a/b", "base_commit": BASE,
                "problem_statement": "p"}
        ab.run_arm(task, "prism", "prism")
        ab.run_arm(task, "baseline", "prism")
    finally:
        (ab.run_agent, ab.subprocess.run, ab.mark_trusted,
         ab.unmark_trusted, ab.sh) = orig
    return calls, init_calls


def test_prism_arm_runs_plain_init_and_never_denies_search():
    """The prism arm must run `prism init` with NO flags.

    --deny-builtin-search writes permissions.deny [Grep, Bash(grep:*),
    Bash(rg:*)] into the worktree. Nothing in the shipped product does that
    since v0.52.0, and an arm that cannot grep is not the arm we ship: it
    turns "did the agent choose prism?" into "the agent had no alternative",
    which reads as adoption in every downstream metric.
    """
    calls, init_calls = _run_both_arms()
    prism_call, baseline_call = calls[0], calls[1]

    assert len(init_calls) == 1, (
        f"prism arm must run `prism init` exactly once in the worktree, "
        f"got {init_calls}")
    assert "--deny-builtin-search" not in init_calls[0], (
        f"init must NOT pass --deny-builtin-search — the denial arc was "
        f"reverted in v0.52.0 and this silently changes what is measured: "
        f"{init_calls[0]}")

    for name in ("Grep", "Bash(grep:*)", "Bash(rg:*)"):
        assert name in prism_call["tools"], (
            f"prism arm's --allowedTools must include {name}: the agent has to "
            f"be free to choose grep over prism for the choice to mean anything")
    assert prism_call["disallowed"] is None, (
        "prism arm must not pass --disallowedTools — that was the pre-v0.50.0 "
        "simulation of a mechanism that no longer exists")

    assert "mcp__prism" in prism_call["tools"]
    assert prism_call["mcp"].endswith(".mcp.json"), (
        f"prism arm must point --mcp-config at the worktree's own .mcp.json "
        f"(written by init), not a shared static file: {prism_call['mcp']}")

    assert baseline_call["disallowed"] is None
    assert "mcp__prism" not in baseline_call["tools"]
    assert baseline_call["mcp"] == ""
    print("OK: prism arm runs plain `prism init`, keeps grep available, "
          "passes no --disallowedTools; baseline unaffected")


def test_both_arms_get_identical_investigation_guidance():
    """Arm isolation: the only prompt difference may be the prism block."""
    calls, _ = _run_both_arms()
    for c in calls:
        assert ab.INVESTIGATION_GUIDANCE.strip() in c["prompt"], (
            "both arms must carry INVESTIGATION_GUIDANCE verbatim — an "
            "unmatched-steering comparison cannot isolate the tool effect")
    assert "prism" not in calls[1]["prompt"].lower(), (
        "baseline prompt mentions prism; the baseline arm must carry zero "
        "prism steering")


def test_tool_calls_capture_mcp_arguments():
    """parse_stream must keep MCP tool ARGUMENTS, not just names.

    Recording only the name cannot answer "did the agent batch its search
    terms?" — the question a tool-surface change lives or dies on. The
    v054-smoke run could not be interpreted for exactly this reason.
    """
    ev = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__prism__prism_search",
         "input": {"query": ["Alpha", "Beta"], "scope": "text"}}]}}
    env = ab.parse_stream(json.dumps(ev))
    assert env["tool_trace"] == ["mcp__prism__prism_search"], env["tool_trace"]
    call = env["tool_calls"][0]
    assert call["name"] == "mcp__prism__prism_search"
    assert call["input"]["query"] == ["Alpha", "Beta"], (
        f"a batched multi-term query must survive into the record as a list: {call}")
    assert call["input"]["scope"] == "text"


def test_clip_keeps_lists_but_bounds_strings():
    assert ab._clip(["a", "b"]) == ["a", "b"]
    long = "x" * 5000
    assert len(ab._clip(long)) < 400 and ab._clip(long).startswith("xxx")


if __name__ == "__main__":
    test_prism_arm_runs_plain_init_and_never_denies_search()
    test_both_arms_get_identical_investigation_guidance()
    test_tool_calls_capture_mcp_arguments()
    test_clip_keeps_lists_but_bounds_strings()
