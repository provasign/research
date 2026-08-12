"""Offline, zero-cost checks for swebench_ab.py's own mechanics — no API
calls. Run before spending any money on agent cells: python3 -m pytest
test_swebench_ab.py, or just: python3 test_swebench_ab.py

Exists because the 2026-08-11 grep-denial bug (prism arm silently kept full
grep access — --allowedTools omission is not a deny in headless mode; only
--disallowedTools is) was found live, by hand, after >$100 of cells had
already run under the broken assumption. This file is where that kind of
check belongs: verified for free, before the first paid cell.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import swebench_ab as ab  # noqa: E402


def test_prism_arm_passes_disallowed_search_tools():
    """The prism arm must pass Grep/Bash(grep:*)/Bash(rg:*) to --disallowedTools
    (the mechanism verified to actually deny), not just omit them from
    --allowedTools (verified to NOT deny — grep ran successfully with
    permission_denials:[] when merely absent from the allow list)."""
    calls = []

    def fake_run_agent(prompt, tools, workdir, model="", mcp="", disallowed=None):
        calls.append({"tools": tools, "disallowed": disallowed})
        return {"tool_trace": [], "num_turns": 0, "total_cost_usd": 0,
                "usage": {}, "_wall_s": 0, "_timed_out": False}

    orig = ab.run_agent
    ab.run_agent = fake_run_agent
    try:
        import tempfile
        ab.WT_ROOT = Path(tempfile.mkdtemp())
        ab.ensure_repo = lambda repo: ab.WT_ROOT
        ab.sh = lambda *a, **k: type("R", (), {"stdout": "", "returncode": 0})()
        task = {"instance_id": "x", "repo": "a/b", "base_commit": "HEAD",
                "problem_statement": "p"}
        ab.run_arm(task, "prism", "prism")
        ab.run_arm(task, "baseline", "prism")
    finally:
        ab.run_agent = orig

    prism_call = calls[0]
    baseline_call = calls[1]
    for name in ("Grep", "Bash(grep:*)", "Bash(rg:*)"):
        assert name in prism_call["disallowed"], (
            f"prism arm must --disallowedTools {name} (allowlist omission alone "
            f"does not deny it in headless mode — verified live 2026-08-11)")
        assert name not in prism_call["tools"], (
            f"prism arm's --allowedTools must not also list {name}")
    assert baseline_call["disallowed"] is None, (
        "baseline arm must pass no --disallowedTools — it keeps full grep access")
    print("OK: prism arm disallows search tools via --disallowedTools; "
          "baseline is unrestricted")


if __name__ == "__main__":
    test_prism_arm_passes_disallowed_search_tools()
