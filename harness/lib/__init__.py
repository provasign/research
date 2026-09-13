"""Standard runner library for the Prism benchmark harness.

This package is the ONE place "invoke claude/codex with optional Prism and
parse the result" lives. New runners should import from here (via
`harness/bench.py`) instead of writing a new one-off script or re-loading
`harness/results/*/run_readonly.py` with importlib.

Modules:
  - runner_core: agent invocation (claude/codex), event parsing, protocol
    audit, template/environment prep, cell execution.
  - scoring: dispatch to docker_eval (coding/patch tasks) or the site-list
    oracle (impact/localization tasks).
  - pricing: per-model cost tables, kept out of runner code.
  - suites: task-suite discovery under harness/tasks/<suite>/.
"""
