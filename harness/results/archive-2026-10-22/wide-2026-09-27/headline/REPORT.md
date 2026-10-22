# Overnight run: native vs resident prism_init

Started 2026-09-27 17:36:12. 32 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-27 17:36:12] starting: 32 tasks, 0 already done

> [2026-09-27 17:36:12] -- wide__chi__Routes_Match (go) --

## wide__chi__Routes_Match (go)

- native: resolved=True tokens=575483 turns=16 wall_s=73.1
- prism : resolved=True tokens=488723 turns=24 wall_s=77.1 prism_calls=8
- token ratio (prism/native): 0.85x

> [2026-09-27 17:39:45]    native resolved=True tokens=575483 | prism resolved=True tokens=488723 prism_calls=8

> [2026-09-27 17:39:45] -- wide__click__Command_invoke (python) --

## wide__click__Command_invoke (python)

- native: resolved=True tokens=768525 turns=29 wall_s=126.0
- prism : resolved=True tokens=1554660 turns=27 wall_s=112.5 prism_calls=6
- token ratio (prism/native): 2.02x

**FLAGGED** (token ratio 2.02x outside [0.67, 1.5])

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=29 tokens=768525 wall_s=126.0 cost=$0.3310992
  - tools: {'Bash': 13, 'Read': 7, 'Edit': 8}
- **prism**: resolved=True turns=27 tokens=1554660 wall_s=112.5 cost=$0.6074034
  - tools: {'mcp__prism__prism': 6, 'Read': 3, 'Edit': 9, 'Bash': 5, 'Grep': 3}

> [2026-09-27 17:44:12]    native resolved=True tokens=768525 | prism resolved=True tokens=1554660 prism_calls=6 [FLAGGED]

> [2026-09-27 17:44:12] -- wide__h3__EventStream_push (ts) --
