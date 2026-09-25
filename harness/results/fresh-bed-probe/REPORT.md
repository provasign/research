# Overnight run: native vs resident prism_init

Started 2026-09-25 06:33:26. 1 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-25 06:33:26] starting: 1 tasks, 0 already done

> [2026-09-25 06:33:26] -- FasterXML__jackson-databind__pr6105 (java) --

## FasterXML__jackson-databind__pr6105 (java)

- native: resolved=True tokens=916243 turns=19 wall_s=208.6
- prism : resolved=True tokens=491027 turns=11 wall_s=78.8 prism_calls=3
- token ratio (prism/native): 0.54x

**FLAGGED** (token ratio 0.54x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=19 tokens=916243 wall_s=208.6 cost=$0.37895080000000003
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 2, 'Bash': 12}
- **prism**: resolved=True turns=11 tokens=491027 wall_s=78.8 cost=$0.3094998
  - tools: {'mcp__prism__prism': 3, 'Bash': 5, 'Edit': 2}

> [2026-09-25 06:45:54]    native resolved=True tokens=916243 | prism resolved=True tokens=491027 prism_calls=3 [FLAGGED]


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 1/1
- native tokens total: 916243
- prism  tokens total: 491027 (0.54x native)
- flagged cells: 1 (0 non-adoption, 1 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- FasterXML__jackson-databind__pr6105

Completed 2026-09-25 06:45:54

> [2026-09-25 06:45:54] DONE: 1/1 tasks, 1 flagged (0 non-adoption, 1 real)
