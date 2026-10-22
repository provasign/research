# Overnight run: native vs resident prism_init

Started 2026-09-28 17:00:03. 1 tasks, model=claude-sonnet-5-5, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-28 17:00:03] starting: 1 tasks, 0 already done

> [2026-09-28 17:00:03] -- wide__chi__Routes_Match (go) --

## wide__chi__Routes_Match (go)

- native: resolved=True tokens=84722 turns=4 wall_s=67.3
- prism : resolved=True tokens=102733 turns=5 wall_s=42.7 prism_calls=2
- token ratio (prism/native): 1.21x

> [2026-09-28 17:02:56]    native resolved=True tokens=84722 | prism resolved=True tokens=102733 prism_calls=2


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 1/1
- native tokens total: 84722
- prism  tokens total: 102733 (1.21x native)
- flagged cells: 0 (0 non-adoption, 0 real prism signal)

Completed 2026-09-28 17:02:56

> [2026-09-28 17:02:56] DONE: 1/1 tasks, 0 flagged (0 non-adoption, 0 real)
