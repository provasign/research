"""Balanced coding suite: eight validated tasks x four normal-product heads.

This is now a thin preset over `harness/bench.py`'s standard `run` command,
fixed to the `e2e` suite (see `harness/tasks/e2e/SUITE.json` for the task
list/categories/pilot set that used to be hardcoded here as
`TASK_SPECS`/`PILOT_TASKS`). All agent-invocation, event-parsing, audit, and
template/environment-prep logic now lives in `harness/lib/runner_core.py` --
this file does not duplicate it. Prefer `python3 harness/bench.py run
--suite e2e ...` directly for anything beyond this fixed preset (task
selection, agent/model overrides, a narrower arm set, etc.).
"""
from __future__ import annotations

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import argparse

import bench
from lib import runner_core as rc
from lib import suites
from lib.pricing import GPT55_PRICING, add_gpt55_cost  # noqa: F401 (re-exported for callers/tests)

# Re-exported for backward compatibility: these used to be duplicated here
# and are exercised directly by tests/test_coding_suite.py.
is_source_path = rc.is_source_path
template_content = rc.template_content
PRISM_TOOLS = rc.PRISM_TOOLS
SONNET_MODEL = bench.DEFAULT_MODELS["claude"]
GPT_MODEL = bench.DEFAULT_MODELS["codex"]
ARMS = bench.arms_for(["claude", "codex"], "both")
TASK_SPECS = {ref.id: ref.category for ref in suites.list_tasks("e2e")}
PILOT_TASKS = suites.pilot_task_ids("e2e")


def agent_path(cell: dict, rg: str | None) -> str:
    """Return an isolated PATH, exposing the Prism CLI only to Prism arms."""
    return rc.agent_path(cell.get("env_dir"), cell.get("prism_cli_dir"), rg)


def audit(rec: dict, calls: list[dict], arm: str) -> None:
    rc.audit_calls(rec, calls, arm)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--phase", choices=("pilot", "remaining", "full"), default="pilot")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--prism-binary", default=None,
                    help="path to the prism binary to use (default: $PRISM_BINARY, PATH, "
                         "or ~/bin/prism -- see lib.runner_core.resolve_prism_binary)")
    args = ap.parse_args()
    return bench.cmd_run(argparse.Namespace(
        suite="e2e", tasks=None, agents="claude,codex", models=None, prism="both",
        prism_binary=args.prism_binary,
        trials=1, phase=args.phase, concurrency=4, out=args.run_dir,
        preflight_only=args.preflight_only,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
