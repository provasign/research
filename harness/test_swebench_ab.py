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


def _run_arms(*arms):
    """Drive run_arm for the named arms with every side effect stubbed out."""
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
        for a in arms:
            ab.run_arm(task, a, "prism")
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
    calls, init_calls = _run_arms("prism", "baseline")
    prism_call, baseline_call = calls[0], calls[1]

    assert len(init_calls) == 1, (
        f"prism arm must run `prism init` exactly once in the worktree, "
        f"got {init_calls}")
    assert "--deny-builtin-search" not in init_calls[0], (
        f"init must NOT pass --deny-builtin-search — the denial arc was "
        f"reverted in v0.52.0 and this silently changes what is measured: "
        f"{init_calls[0]}")

    # grep must be REACHABLE -- the agent has to be free to choose it over
    # prism for the choice to mean anything. Expressed as "not denied" rather
    # than "matches a pattern", because Bash is now allowed broadly.
    assert "Bash" in prism_call["tools"] or "Bash(grep:*)" in prism_call["tools"], (
        f"prism arm cannot reach grep: {prism_call['tools']}")
    for pat in (prism_call["disallowed"] or []):
        assert "grep" not in pat and "rg" not in pat, (
            f"grep/rg must never be in the denylist: {pat}")

    assert "mcp__prism" in prism_call["tools"]
    assert prism_call["mcp"].endswith(".mcp.json"), (
        f"prism arm must point --mcp-config at the worktree's own .mcp.json "
        f"(written by init), not a shared static file: {prism_call['mcp']}")

    assert "mcp__prism" not in baseline_call["tools"]
    assert baseline_call["mcp"] == ""
    print("OK: prism arm runs plain `prism init`, keeps grep available, "
          "passes no --disallowedTools; baseline unaffected")


def test_boundary_is_denied_in_every_arm():
    """The contamination boundary must hold on BOTH arms, always.

    gh and curl are the routes to the gold fix an agent actually took: the
    beets-5890 cell ran `gh pr view 5890 --json title,body,files` twice and
    WebFetch'd the PR's files page. The instance_id leaks the PR number, so
    this is a live threat, not a hypothetical. Bash is now allowed broadly,
    which means the denylist is the ONLY thing standing between an agent and
    the answer -- if it regresses, cells silently become copying exercises.
    """
    calls, _ = _run_arms("prism", "baseline", "prism-cli")
    for c in calls:
        dis = c["disallowed"] or []
        for needed in ("Bash(gh:*)", "Bash(curl:*)", "Bash(wget:*)", "WebFetch", "WebSearch"):
            assert needed in dis, (
                f"{needed} missing from --disallowedTools: {dis}")


def test_broad_bash_is_allowed_so_the_toolchain_works():
    """Ordinary Python build/test idioms must not be refused.

    The old enumeration denied `uv` 93 times, `pip`, `pytest`, and 46
    `PYTHONPATH=... python3` invocations across one 38-task run -- none of
    them dangerous, all of them simply absent from the list. An env-var
    prefix cannot be expressed as a binary pattern at all, so enumeration
    could never have covered it. Verified live: under broad Bash,
    `PYTHONPATH=. python3`, `uv` and `pip` all run while gh and curl are
    refused.
    """
    calls, _ = _run_arms("prism", "baseline")
    for c in calls:
        assert "Bash" in c["tools"], (
            f"Bash must be allowed broadly; enumerating binaries measures the "
            f"allowlist instead of the agent: {c['tools']}")


def test_both_arms_get_identical_investigation_guidance():
    """Arm isolation: the only prompt difference may be the prism block."""
    calls, _ = _run_arms("prism", "baseline")
    for c in calls:
        assert ab.INVESTIGATION_GUIDANCE.strip() in c["prompt"], (
            "both arms must carry INVESTIGATION_GUIDANCE verbatim — an "
            "unmatched-steering comparison cannot isolate the tool effect")
    assert "prism" not in calls[1]["prompt"].lower(), (
        "baseline prompt mentions prism; the baseline arm must carry zero "
        "prism steering")


def test_prism_cli_arm_has_no_mcp_at_all():
    """The CLI arm's whole point is that MCP is ABSENT.

    Its hypothesis is about FIXED COST: an MCP arm pays tool schemas as fresh
    context whether or not a tool is called. If the arm quietly registers MCP
    -- an init call, an --mcp-config, an mcp__prism in the tool list -- it
    stops testing that and silently becomes a second copy of the MCP arm,
    which would look like a clean replication rather than a broken control.
    """
    calls, init_calls = _run_arms("prism-cli")
    c = calls[0]
    assert init_calls == [], (
        f"prism-cli must not run `prism init` — that writes .mcp.json and the "
        f"MCP-first steering block: {init_calls}")
    assert c["mcp"] == "", f"prism-cli must pass no --mcp-config, got {c['mcp']!r}"
    assert not any("mcp__prism" in t for t in c["tools"]), (
        f"prism-cli must not expose mcp__prism: {c['tools']}")
    assert any(t.startswith("Bash(prism") or "prism" in t for t in c["tools"]
               if t.startswith("Bash(")), (
        f"prism-cli must expose the prism BINARY as a shell command: {c['tools']}")
    assert "prism search" in c["prompt"], (
        "prism-cli must carry CLI-first steering (CLI_PRISM_STEERING)")
    assert "ToolSearch" not in c["prompt"], (
        "prism-cli steering must not tell the agent to ToolSearch for prism_* "
        "tools — in a CLI deployment they do not exist, and the instruction "
        "sends it hunting before it does any work")


def test_cli_and_mcp_steering_teach_the_same_routes():
    """Arm isolation again: the two prism arms must differ in SURFACE, not in
    what they teach. If one block mentions change-impact and the other does
    not, the comparison measures the prose."""
    cli = ab.CLI_PRISM_STEERING
    mcp = ab.real_prism_steering()
    for concept in ("search", "lookup", "read", "query", "change", "verify"):
        assert concept in cli.lower(), f"CLI steering omits {concept}"
        assert concept in mcp.lower(), f"MCP steering omits {concept}"


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
    test_prism_cli_arm_has_no_mcp_at_all()
    test_boundary_is_denied_in_every_arm()
    test_broad_bash_is_allowed_so_the_toolchain_works()
    test_cli_and_mcp_steering_teach_the_same_routes()
    test_both_arms_get_identical_investigation_guidance()
    test_tool_calls_capture_mcp_arguments()
    test_clip_keeps_lists_but_bounds_strings()
