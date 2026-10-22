# Overnight run: native vs resident prism_init

Started 2026-09-27 14:18:47. 1 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-27 14:18:47] starting: 1 tasks, 0 already done

> [2026-09-27 14:18:47] -- wide__gin__Binding_Name (go) --

## wide__gin__Binding_Name (go)

- native: resolved=True tokens=1313270 turns=41 wall_s=143.5
- prism : resolved=True tokens=1759629 turns=36 wall_s=121.7 prism_calls=7
- token ratio (prism/native): 1.34x

> [2026-09-27 14:23:36]    native resolved=True tokens=1313270 | prism resolved=True tokens=1759629 prism_calls=7


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 1/1
- native tokens total: 1313270
- prism  tokens total: 1759629 (1.34x native)
- flagged cells: 0 (0 non-adoption, 0 real prism signal)

Completed 2026-09-27 14:23:36

> [2026-09-27 14:23:36] DONE: 1/1 tasks, 0 flagged (0 non-adoption, 0 real)
