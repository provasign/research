# Overnight run: native vs resident prism_init

Started 2026-09-25 06:45:59. 1 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-25 06:45:59] starting: 1 tasks, 0 already done

> [2026-09-25 06:45:59] -- gin-gonic__gin__pr4698 (go) --

## gin-gonic__gin__pr4698 (go)

- native: resolved=True tokens=212079 turns=6 wall_s=21.5
- prism : resolved=False tokens=307888 turns=8 wall_s=19.5 prism_calls=4
- token ratio (prism/native): 1.45x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=6 tokens=212079 wall_s=21.5 cost=$0.11716780000000002
  - tools: {'Read': 2, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=False turns=8 tokens=307888 wall_s=19.5 cost=$0.14079239999999998
  - tools: {'mcp__prism__prism': 4, 'Edit': 1, 'Bash': 2}

> [2026-09-25 06:47:48]    native resolved=True tokens=212079 | prism resolved=False tokens=307888 prism_calls=4 [FLAGGED]


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 0/1
- native tokens total: 212079
- prism  tokens total: 307888 (1.45x native)
- flagged cells: 1 (0 non-adoption, 1 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- gin-gonic__gin__pr4698

Completed 2026-09-25 06:47:48

> [2026-09-25 06:47:48] DONE: 1/1 tasks, 1 flagged (0 non-adoption, 1 real)
