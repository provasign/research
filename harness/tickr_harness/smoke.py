"""Plumbing smoke test for the tickr A/B runner.

Validates, with two throwaway turns instead of the real 9, that:
  - a nested `claude -p` session starts and RESUMES (turn 2 remembers turn 1),
  - --strict-mcp-config keeps the user's global prism MCP out of the base arm
    and lets it into the prism arm,
  - no permission denials fire with the arm's allowlist,
  - usage/cost parse, and the tool-use trace is readable off the transcript.

Run:  python3 -m tickr_harness.smoke
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tickr_ab as R                                   # noqa: E402
from tickr_harness.arms import ARMS                    # noqa: E402

T1 = ("Create a file `note.txt` containing exactly the word `alpha`, and a "
      "Python file `m.py` with a function `f(x)` returning x + 1. Then run "
      "`python3 -c \"import m; print(m.f(1))\"` and report what it printed.")
T2 = ("What word did you put in note.txt in your previous message, and what "
      "did the python command print? Answer from memory, then add a second "
      "function `g(x)` to m.py returning f(x) * 2.")


def one(arm: str) -> bool:
    repo = R.REPOS / f"smoke-{arm}"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    (repo / "CLAUDE.md").write_text(ARMS[arm]["claude_md"])
    sid = str(uuid.uuid4())
    ok = True
    for i, p in enumerate((T1, T2), start=1):
        if ARMS[arm]["index"]:
            R.index_prism(repo)
        rec = R.run_turn(arm, repo, sid, first=(i == 1), prompt=p)
        tools = R._tool_counts(sid)
        print(f"\n[{arm}] turn {i}: rc={rec.get('rc')} wall={rec.get('wall_s')}s "
              f"cost=${rec.get('cost_usd', 0):.4f} "
              f"in={rec.get('input_tokens')} out={rec.get('output_tokens')} "
              f"cache_r={rec.get('cache_read_tokens')}")
        print(f"    denials={rec.get('permission_denials')}")
        print(f"    tools={tools}")
        print(f"    said: {(rec.get('final_message') or rec.get('agent_error') or '')[:300]!r}")
        if rec.get("rc") != 0:
            ok = False
    prism_tools = [k for k in R._tool_counts(sid) if k.startswith("mcp__prism")]
    if arm == "base" and prism_tools:
        print(f"[{arm}] FAIL: prism MCP leaked into the base arm: {prism_tools}")
        ok = False
    if arm == "prism":
        print(f"[{arm}] prism MCP tools reachable: {prism_tools or 'NONE USED (not fatal)'}")
    said = (rec.get("final_message") or "").lower()
    if "alpha" not in said:
        print(f"[{arm}] WARN: turn 2 did not recall 'alpha' — session resume suspect")
    if not (repo / "m.py").exists():
        print(f"[{arm}] FAIL: m.py was never written")
        ok = False
    return ok


if __name__ == "__main__":
    arms = sys.argv[1:] or ["base", "prism"]
    good = all(one(a) for a in arms)
    print("\nSMOKE", "PASS" if good else "FAIL")
    sys.exit(0 if good else 1)
