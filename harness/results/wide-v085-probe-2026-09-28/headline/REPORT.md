# Overnight run: native vs resident prism_init

Started 2026-09-28 00:16:21. 1 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-28 00:16:21] starting: 1 tasks, 0 already done

> [2026-09-28 00:16:21] -- wide__hono__ConnInfo_remote (ts) --

## wide__hono__ConnInfo_remote (ts)

- native: resolved=True tokens=968690 turns=38 wall_s=141.9
- prism : resolved=False tokens=1279022 turns=64 wall_s=184.0 prism_calls=5
- token ratio (prism/native): 1.32x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=38 tokens=968690 wall_s=141.9 cost=$0.41789279999999995
  - tools: {'Grep': 6, 'Read': 10, 'Edit': 11, 'Bash': 10}
- **prism**: resolved=False turns=64 tokens=1279022 wall_s=184.0 cost=$0.7311249999999999
  - tools: {'mcp__prism__prism': 5, 'Read': 21, 'Edit': 30, 'Grep': 1, 'Bash': 6}

> [2026-09-28 00:23:43]    native resolved=True tokens=968690 | prism resolved=False tokens=1279022 prism_calls=5 [FLAGGED]


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 0/1
- native tokens total: 968690
- prism  tokens total: 1279022 (1.32x native)
- flagged cells: 1 (0 non-adoption, 1 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- wide__hono__ConnInfo_remote

Completed 2026-09-28 00:23:43

> [2026-09-28 00:23:43] DONE: 1/1 tasks, 1 flagged (0 non-adoption, 1 real)
