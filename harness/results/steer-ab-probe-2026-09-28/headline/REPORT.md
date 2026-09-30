# Overnight run: native vs resident prism_init

Started 2026-09-28 16:37:56. 1 tasks, model=sonnet, arms=prism_body_baseline vs prism_body_exp.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-28 16:37:56] starting: 1 tasks, 0 already done

> [2026-09-28 16:37:56] -- wide__werkzeug__BaseConverter_to_url (python) --

## wide__werkzeug__BaseConverter_to_url (python)

- native: resolved=True tokens=760792 turns=27 wall_s=90.1
- prism : resolved=True tokens=218878 turns=8 wall_s=18.4 prism_calls=1
- token ratio (prism/native): 0.29x

**FLAGGED** (token ratio 0.29x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=27 tokens=760792 wall_s=90.1 cost=$0.4356140000000001
  - tools: {'mcp__prism__prism': 2, 'Read': 4, 'Edit': 12, 'Bash': 8}
- **prism**: resolved=True turns=8 tokens=218878 wall_s=18.4 cost=$0.174391
  - tools: {'mcp__prism__prism': 1, 'Bash': 6}

> [2026-09-28 16:40:17]    native resolved=True tokens=760792 | prism resolved=True tokens=218878 prism_calls=1 [FLAGGED]


# SUMMARY

1/1 tasks completed.

- native resolved: 1/1
- prism  resolved: 1/1
- native tokens total: 760792
- prism  tokens total: 218878 (0.29x native)
- flagged cells: 1 (0 non-adoption, 1 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- wide__werkzeug__BaseConverter_to_url

Completed 2026-09-28 16:40:17

> [2026-09-28 16:40:17] DONE: 1/1 tasks, 1 flagged (0 non-adoption, 1 real)
