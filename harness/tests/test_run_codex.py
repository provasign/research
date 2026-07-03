"""Unit tests for Codex JSONL event parsing.

Run: cd research/harness && python -m pytest tests/test_run_codex.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_codex import _lead_bin, _parse_events  # noqa: E402


def _jsonl(*events):
    return "\n".join(json.dumps(e) for e in events)


def test_parse_events_detects_prism_command_and_usage():
    ev = _parse_events(_jsonl(
        {
            "type": "event_msg",
            "payload": {
                "type": "exec_command_begin",
                "cmd": "prism query settable bean property",
            },
        },
        {
            "type": "result",
            "payload": {
                "usage": {
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "cached_input_tokens": 100,
                },
                "total_cost_usd": 0.42,
                "duration_ms": 12345,
                "num_turns": 4,
            },
        },
    ))

    assert ev["graph_used"]
    assert ev["tools_used"] == ["prism"]
    assert ev["tool_cmds"] == ["prism query settable bean property"]
    assert ev["usage"]["input_tokens"] == 1200
    assert ev["usage"]["output_tokens"] == 300
    assert ev["usage"]["total_tokens"] == 1500
    assert ev["usage"]["cached_input_tokens"] == 100
    assert ev["total_cost_usd"] == 0.42
    assert ev["duration_ms"] == 12345
    assert ev["num_turns"] == 4


def test_parse_events_normalizes_usage_aliases():
    ev = _parse_events(_jsonl({
        "type": "response.completed",
        "response": {
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            },
            "cost_usd": "0.01",
            "turn_count": 2,
        },
    }))

    assert ev["usage"]["input_tokens"] == 10
    assert ev["usage"]["output_tokens"] == 5
    assert ev["usage"]["total_tokens"] == 15
    assert ev["total_cost_usd"] == 0.01
    assert ev["num_turns"] == 2


def test_parse_events_keeps_largest_repeated_usage_snapshot():
    ev = _parse_events(_jsonl(
        {"usage": {"input_tokens": 10, "output_tokens": 1}},
        {"usage": {"input_tokens": 20, "output_tokens": 3}},
        {"usage": {"input_tokens": 15, "output_tokens": 2}},
    ))

    assert ev["usage"]["input_tokens"] == 20
    assert ev["usage"]["output_tokens"] == 3


def test_parse_events_captures_codex_errors():
    ev = _parse_events(_jsonl(
        {"type": "error", "message": "bad model"},
        {"type": "turn.failed", "error": {"message": "turn failed"}},
    ))

    assert ev["errors"] == ["bad model", "turn failed"]


def test_lead_bin_unwraps_shell_commands():
    assert _lead_bin("/bin/zsh -lc 'HOME=/tmp /Users/me/bin/prism query x'") == "prism"
    assert _lead_bin('/bin/zsh -lc "rg pattern src"') == "rg"
    assert _lead_bin('/bin/zsh -lc "rg unterminated') == "zsh"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
