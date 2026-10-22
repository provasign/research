# Overnight run: native vs resident prism_init

Started 2026-09-25 21:54:05. 1 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-25 21:54:05] starting: 1 tasks, 0 already done

> [2026-09-25 21:54:05] -- apache__commons-lang__pr1713 (java) --

## apache__commons-lang__pr1713 (java)

- native: resolved=True tokens=681406 turns=18 wall_s=87.8
- prism : resolved=True tokens=274193 turns=7 wall_s=45.7 prism_calls=1
- token ratio (prism/native): 0.40x

**FLAGGED** (token ratio 0.40x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=18 tokens=681406 wall_s=87.8 cost=$0.263294
  - tools: {'Grep': 5, 'Read': 4, 'Edit': 2, 'Bash': 6}
- **prism**: resolved=True turns=7 tokens=274193 wall_s=45.7 cost=$0.2352264
  - tools: {'mcp__prism__prism': 1, 'Edit': 2, 'Bash': 3}

> [2026-09-25 21:57:01]    native resolved=True tokens=681406 | prism resolved=True tokens=274193 prism_calls=1 [FLAGGED]


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 1/1
- native tokens total: 681406
- prism  tokens total: 274193 (0.40x native)
- flagged cells: 1 (0 non-adoption, 1 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- apache__commons-lang__pr1713

Completed 2026-09-25 21:57:01

> [2026-09-25 21:57:01] DONE: 1/1 tasks, 1 flagged (0 non-adoption, 1 real)
