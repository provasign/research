# Overnight run: native vs resident prism_init

Started 2026-09-27 18:36:30. 24 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-27 18:36:30] starting: 24 tasks, 0 already done

> [2026-09-27 18:36:30] -- wide__chi__Routes_Match (go) --

## wide__chi__Routes_Match (go)

- native: resolved=True tokens=409959 turns=27 wall_s=73.9
- prism : resolved=True tokens=479146 turns=19 wall_s=97.2 prism_calls=9
- token ratio (prism/native): 1.17x

> [2026-09-27 18:40:24]    native resolved=True tokens=409959 | prism resolved=True tokens=479146 prism_calls=9

> [2026-09-27 18:40:24] -- wide__click__Command_invoke (python) --

## wide__click__Command_invoke (python)

- native: resolved=True tokens=1532334 turns=33 wall_s=116.8
- prism : resolved=True tokens=906480 turns=30 wall_s=94.0 prism_calls=7
- token ratio (prism/native): 0.59x

**FLAGGED** (token ratio 0.59x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=33 tokens=1532334 wall_s=116.8 cost=$0.5408987999999999
  - tools: {'Grep': 8, 'Read': 5, 'Edit': 9, 'Bash': 10}
- **prism**: resolved=True turns=30 tokens=906480 wall_s=94.0 cost=$0.4035786
  - tools: {'mcp__prism__prism': 7, 'Read': 6, 'Grep': 2, 'Edit': 9, 'Bash': 5}

> [2026-09-27 18:44:23]    native resolved=True tokens=1532334 | prism resolved=True tokens=906480 prism_calls=7 [FLAGGED]

> [2026-09-27 18:44:23] -- wide__werkzeug__HTTPException_get_headers (python) --

## wide__werkzeug__HTTPException_get_headers (python)

- native: resolved=True tokens=613058 turns=18 wall_s=179.9
- prism : resolved=True tokens=2143772 turns=38 wall_s=369.8 prism_calls=3
- token ratio (prism/native): 3.50x

**FLAGGED** (token ratio 3.50x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=18 tokens=613058 wall_s=179.9 cost=$0.227827
  - tools: {'Grep': 3, 'Bash': 13, 'ScheduleWakeup': 1}
- **prism**: resolved=True turns=38 tokens=2143772 wall_s=369.8 cost=$0.666515
  - tools: {'mcp__prism__prism': 3, 'Read': 4, 'Bash': 24, 'ScheduleWakeup': 6}

> [2026-09-27 18:54:01]    native resolved=True tokens=613058 | prism resolved=True tokens=2143772 prism_calls=3 [FLAGGED]

> [2026-09-27 18:54:01] -- wide__click__ClickException_format_message (python) --

## wide__click__ClickException_format_message (python)

- native: resolved=True tokens=342981 turns=10 wall_s=74.8
- prism : resolved=True tokens=486805 turns=22 wall_s=80.4 prism_calls=5
- token ratio (prism/native): 1.42x

> [2026-09-27 18:57:05]    native resolved=True tokens=342981 | prism resolved=True tokens=486805 prism_calls=5

> [2026-09-27 18:57:05] -- wide__rich__Highlighter_highlight (python) --

## wide__rich__Highlighter_highlight (python)

- native: resolved=True tokens=1429607 turns=40 wall_s=117.9
- prism : resolved=True tokens=1195061 turns=22 wall_s=110.3 prism_calls=3
- token ratio (prism/native): 0.84x

> [2026-09-27 19:01:09]    native resolved=True tokens=1429607 | prism resolved=True tokens=1195061 prism_calls=3

> [2026-09-27 19:01:09] -- wide__werkzeug__BaseConverter_to_url (python) --
