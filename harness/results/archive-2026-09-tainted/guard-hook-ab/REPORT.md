# Overnight run: native vs resident prism_init

Started 2026-09-22 18:34:52. 13 tasks, model=sonnet, arms=prism_init_no_guard vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-22 18:34:52] starting: 13 tasks, 0 already done

> [2026-09-22 18:34:52] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=399185 turns=10 wall_s=30.2
- prism : resolved=False tokens=436863 turns=10 wall_s=43.8 prism_calls=4
- token ratio (prism/native): 1.09x

> [2026-09-22 18:36:17]    native resolved=False tokens=399185 | prism resolved=False tokens=436863 prism_calls=4

> [2026-09-22 18:36:17] -- gin-gonic__gin__pr4819 (go) --

## gin-gonic__gin__pr4819 (go)

- native: resolved=True tokens=196313 turns=5 wall_s=14.9
- prism : resolved=True tokens=155285 turns=4 wall_s=9.5 prism_calls=1
- token ratio (prism/native): 0.79x

> [2026-09-22 18:39:46]    native resolved=True tokens=196313 | prism resolved=True tokens=155285 prism_calls=1

> [2026-09-22 18:39:46] -- FasterXML__jackson-databind__pr6102 (java) --

## FasterXML__jackson-databind__pr6102 (java)

- native: resolved=True tokens=126747 turns=3 wall_s=11.6
- prism : resolved=True tokens=169900 turns=4 wall_s=16.3 prism_calls=1
- token ratio (prism/native): 1.34x

> [2026-09-22 18:42:15]    native resolved=True tokens=126747 | prism resolved=True tokens=169900 prism_calls=1

> [2026-09-22 18:42:15] -- FasterXML__jackson-databind__pr6105 (java) --

## FasterXML__jackson-databind__pr6105 (java)

- native: resolved=True tokens=494098 turns=11 wall_s=35.3
- prism : resolved=True tokens=577249 turns=13 wall_s=38.4 prism_calls=0
- token ratio (prism/native): 1.17x

> [2026-09-22 18:48:40]    native resolved=True tokens=494098 | prism resolved=True tokens=577249 prism_calls=0

> [2026-09-22 18:48:40] -- expressjs__express__pr7459 (js) --

## expressjs__express__pr7459 (js)

- native: resolved=True tokens=326672 turns=8 wall_s=43.5
- prism : resolved=True tokens=277411 turns=7 wall_s=24.6 prism_calls=1
- token ratio (prism/native): 0.85x

> [2026-09-22 18:50:10]    native resolved=True tokens=326672 | prism resolved=True tokens=277411 prism_calls=1

> [2026-09-22 18:50:10] -- pallets__click__pr3534 (python) --

## pallets__click__pr3534 (python)

- native: resolved=True tokens=528986 turns=12 wall_s=47.9
- prism : resolved=True tokens=1187514 turns=24 wall_s=84.3 prism_calls=3
- token ratio (prism/native): 2.24x

**FLAGGED** (token ratio 2.24x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=528986 wall_s=47.9 cost=$0.23729499999999998
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Grep': 1, 'Bash': 6}
- **prism**: resolved=True turns=24 tokens=1187514 wall_s=84.3 cost=$0.39955579999999996
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 19}

> [2026-09-22 18:55:22]    native resolved=True tokens=528986 | prism resolved=True tokens=1187514 prism_calls=3 [FLAGGED]

> [2026-09-22 18:55:22] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=486951 turns=11 wall_s=55.8
- prism : resolved=False tokens=476223 turns=12 wall_s=78.7 prism_calls=4
- token ratio (prism/native): 0.98x

> [2026-09-22 19:00:51]    native resolved=False tokens=486951 | prism resolved=False tokens=476223 prism_calls=4

> [2026-09-22 19:00:51] -- gin-gonic__gin__pr4702 (go) --

## gin-gonic__gin__pr4702 (go)

- native: resolved=True tokens=185049 turns=5 wall_s=12.3
- prism : resolved=True tokens=185055 turns=5 wall_s=13.1 prism_calls=1
- token ratio (prism/native): 1.00x

> [2026-09-22 19:02:26]    native resolved=True tokens=185049 | prism resolved=True tokens=185055 prism_calls=1

> [2026-09-22 19:02:26] -- FasterXML__jackson-databind__pr6099 (java) --

## FasterXML__jackson-databind__pr6099 (java)

- native: resolved=True tokens=696924 turns=16 wall_s=85.8
- prism : resolved=True tokens=516090 turns=13 wall_s=61.8 prism_calls=4
- token ratio (prism/native): 0.74x

> [2026-09-22 19:06:18]    native resolved=True tokens=696924 | prism resolved=True tokens=516090 prism_calls=4

> [2026-09-22 19:06:18] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=True tokens=2031804 turns=33 wall_s=215.2
- prism : resolved=True tokens=1305764 turns=25 wall_s=127.2 prism_calls=5
- token ratio (prism/native): 0.64x

**FLAGGED** (token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=33 tokens=2031804 wall_s=215.2 cost=$0.7357347999999999
  - tools: {'mcp__prism__prism': 4, 'Bash': 21, 'Read': 4, 'Edit': 2, 'Write': 1}
- **prism**: resolved=True turns=25 tokens=1305764 wall_s=127.2 cost=$0.47413619999999995
  - tools: {'mcp__prism__prism': 5, 'Grep': 5, 'Bash': 7, 'Read': 2, 'Edit': 5}

> [2026-09-22 19:14:50]    native resolved=True tokens=2031804 | prism resolved=True tokens=1305764 prism_calls=5 [FLAGGED]

> [2026-09-22 19:14:50] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=1166688 turns=22 wall_s=142.4
- prism : resolved=False tokens=1171947 turns=23 wall_s=117.9 prism_calls=3
- token ratio (prism/native): 1.00x

> [2026-09-22 19:22:05]    native resolved=False tokens=1166688 | prism resolved=False tokens=1171947 prism_calls=3

> [2026-09-22 19:22:05] -- akheron__jansson__pr741 (c) --

## akheron__jansson__pr741 (c)

- native: resolved=True tokens=1752002 turns=31 wall_s=147.1
- prism : resolved=True tokens=1528316 turns=32 wall_s=123.8 prism_calls=7
- token ratio (prism/native): 0.87x

> [2026-09-22 19:26:46]    native resolved=True tokens=1752002 | prism resolved=True tokens=1528316 prism_calls=7

> [2026-09-22 19:26:46] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=True tokens=2046381 turns=38 wall_s=159.4
- prism : resolved=True tokens=1306467 turns=25 wall_s=91.0 prism_calls=5
- token ratio (prism/native): 0.64x

**FLAGGED** (token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=38 tokens=2046381 wall_s=159.4 cost=$0.6549098000000001
  - tools: {'mcp__prism__prism': 5, 'Grep': 7, 'Read': 1, 'Edit': 14, 'Bash': 10}
- **prism**: resolved=True turns=25 tokens=1306467 wall_s=91.0 cost=$0.4729744000000001
  - tools: {'mcp__prism__prism': 5, 'Grep': 1, 'Bash': 4, 'Read': 2, 'Edit': 12}

> [2026-09-22 19:31:07]    native resolved=True tokens=2046381 | prism resolved=True tokens=1306467 prism_calls=5 [FLAGGED]


# SUMMARY

13/13 tasks completed.

- native resolved: 10/13
- prism  resolved: 10/13
- native tokens total: 10437800
- prism  tokens total: 9294084 (0.89x native)
- flagged cells: 3 (0 non-adoption, 3 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- pallets__click__pr3534
- pallets__click__pr3653
- akheron__jansson__pr731

Completed 2026-09-22 19:31:07

> [2026-09-22 19:31:07] DONE: 13/13 tasks, 3 flagged (0 non-adoption, 3 real)
