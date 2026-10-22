# Overnight run: native vs resident prism_init

Started 2026-09-25 22:30:49. 50 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-25 22:30:49] starting: 50 tasks, 0 already done

> [2026-09-25 22:30:49] -- gin-gonic__gin__pr4695 (go) --

## gin-gonic__gin__pr4695 (go)

- native: resolved=True tokens=236241 turns=7 wall_s=37.7
- prism : resolved=True tokens=265078 turns=7 wall_s=28.6 prism_calls=2
- token ratio (prism/native): 1.12x

> [2026-09-25 22:32:22]    native resolved=True tokens=236241 | prism resolved=True tokens=265078 prism_calls=2

> [2026-09-25 22:32:22] -- gin-gonic__gin__pr4698 (go) --

## gin-gonic__gin__pr4698 (go)

- native: resolved=True tokens=217854 turns=6 wall_s=32.6
- prism : resolved=True tokens=228963 turns=6 wall_s=28.0 prism_calls=1
- token ratio (prism/native): 1.05x

> [2026-09-25 22:33:47]    native resolved=True tokens=217854 | prism resolved=True tokens=228963 prism_calls=1

> [2026-09-25 22:33:47] -- Textualize__rich__pr3882 (python) --

## Textualize__rich__pr3882 (python)

- native: resolved=True tokens=370218 turns=10 wall_s=35.4
- prism : resolved=True tokens=298307 turns=8 wall_s=32.3 prism_calls=1
- token ratio (prism/native): 0.81x

> [2026-09-25 22:35:09]    native resolved=True tokens=370218 | prism resolved=True tokens=298307 prism_calls=1

> [2026-09-25 22:35:09] -- psf__requests__pr7315 (python) --

## psf__requests__pr7315 (python)

- native: resolved=False tokens=1203286 turns=28 wall_s=257.9
- prism : resolved=False tokens=945708 turns=20 wall_s=156.5 prism_calls=4
- token ratio (prism/native): 0.79x

> [2026-09-25 22:42:23]    native resolved=False tokens=1203286 | prism resolved=False tokens=945708 prism_calls=4

> [2026-09-25 22:42:23] -- gin-gonic__gin__pr4472 (go) --

## gin-gonic__gin__pr4472 (go)

- native: resolved=True tokens=314648 turns=9 wall_s=32.9
- prism : resolved=True tokens=238276 turns=6 wall_s=19.5 prism_calls=2
- token ratio (prism/native): 0.76x

> [2026-09-25 22:43:40]    native resolved=True tokens=314648 | prism resolved=True tokens=238276 prism_calls=2

> [2026-09-25 22:43:40] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=572785 turns=15 wall_s=56.0
- prism : resolved=False tokens=596431 turns=14 wall_s=53.1 prism_calls=3
- token ratio (prism/native): 1.04x

> [2026-09-25 22:45:40]    native resolved=False tokens=572785 | prism resolved=False tokens=596431 prism_calls=3

> [2026-09-25 22:45:40] -- gin-gonic__gin__pr4819 (go) --

## gin-gonic__gin__pr4819 (go)

- native: resolved=True tokens=496964 turns=16 wall_s=73.7
- prism : resolved=True tokens=327550 turns=8 wall_s=36.3 prism_calls=1
- token ratio (prism/native): 0.66x

**FLAGGED** (token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=16 tokens=496964 wall_s=73.7 cost=$0.22479259999999998
  - tools: {'Grep': 4, 'Read': 1, 'Edit': 2, 'Bash': 8}
- **prism**: resolved=True turns=8 tokens=327550 wall_s=36.3 cost=$0.16256300000000004
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 4, 'Write': 1}

> [2026-09-25 22:48:06]    native resolved=True tokens=496964 | prism resolved=True tokens=327550 prism_calls=1 [FLAGGED]

> [2026-09-25 22:48:06] -- pallets__click__pr3466 (python) --

## pallets__click__pr3466 (python)

- native: resolved=True tokens=1190856 turns=27 wall_s=138.9
- prism : resolved=True tokens=1499762 turns=26 wall_s=174.2 prism_calls=3
- token ratio (prism/native): 1.26x

> [2026-09-25 22:53:53]    native resolved=True tokens=1190856 | prism resolved=True tokens=1499762 prism_calls=3

> [2026-09-25 22:53:53] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=1197004 turns=28 wall_s=93.0
- prism : resolved=False tokens=812898 turns=18 wall_s=85.2 prism_calls=2
- token ratio (prism/native): 0.68x

> [2026-09-25 22:57:22]    native resolved=False tokens=1197004 | prism resolved=False tokens=812898 prism_calls=2

> [2026-09-25 22:57:22] -- FasterXML__jackson-databind__pr6012 (java) --

## FasterXML__jackson-databind__pr6012 (java)

- native: resolved=True tokens=318998 turns=9 wall_s=55.0
- prism : resolved=False tokens=0 turns=1 wall_s=71.9 prism_calls=0

**FLAGGED** (resolve mismatch)

**Attribution: NON-ADOPTION.** Prism was never called (0 mcp__prism__prism calls) in this cell -- this result is not attributable to prism's engine or context quality, only to the agent not reaching for the tool.

- **native**: resolved=True turns=9 tokens=318998 wall_s=55.0 cost=$0.1554026
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 1, 'Bash': 2, 'ToolSearch': 1}
- **prism**: resolved=False turns=1 tokens=0 wall_s=71.9 cost=$0
  - tools: {}

> [2026-09-26 01:47:16]    native resolved=True tokens=318998 | prism resolved=False tokens=0 prism_calls=0 [FLAGGED]

> [2026-09-26 01:47:16] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=132387 turns=4 wall_s=49.8
- prism : resolved=True tokens=147985 turns=4 wall_s=18.9 prism_calls=1
- token ratio (prism/native): 1.12x

> [2026-09-26 02:23:44]    native resolved=True tokens=132387 | prism resolved=True tokens=147985 prism_calls=1

> [2026-09-26 02:23:44] -- FasterXML__jackson-databind__pr6030 (java) --

> [2026-09-26 02:24:53] starting: 50 tasks, 9 already done

> [2026-09-26 02:24:53] -- FasterXML__jackson-databind__pr6012 (java) --

## FasterXML__jackson-databind__pr6012 (java)

- native: resolved=True tokens=410140 turns=11 wall_s=77.2
- prism : resolved=True tokens=159948 turns=4 wall_s=25.5 prism_calls=1
- token ratio (prism/native): 0.39x

**FLAGGED** (token ratio 0.39x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=410140 wall_s=77.2 cost=$0.19518399999999997
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=4 tokens=159948 wall_s=25.5 cost=$0.114299
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 1}

> [2026-09-26 02:27:59]    native resolved=True tokens=410140 | prism resolved=True tokens=159948 prism_calls=1 [FLAGGED]

> [2026-09-26 02:27:59] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=132657 turns=4 wall_s=18.5
- prism : resolved=True tokens=263244 turns=7 wall_s=40.2 prism_calls=3
- token ratio (prism/native): 1.98x

**FLAGGED** (token ratio 1.98x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=4 tokens=132657 wall_s=18.5 cost=$0.08382119999999998
  - tools: {'Grep': 1, 'Edit': 1, 'Bash': 1}
- **prism**: resolved=True turns=7 tokens=263244 wall_s=40.2 cost=$0.1314526
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Edit': 1, 'Bash': 1}

> [2026-09-26 02:29:35]    native resolved=True tokens=132657 | prism resolved=True tokens=263244 prism_calls=3 [FLAGGED]

> [2026-09-26 02:29:35] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=363177 turns=10 wall_s=49.2
- prism : resolved=False tokens=414093 turns=9 wall_s=56.3 prism_calls=4
- token ratio (prism/native): 1.14x

> [2026-09-26 02:32:47]    native resolved=False tokens=363177 | prism resolved=False tokens=414093 prism_calls=4

> [2026-09-26 02:32:47] -- FasterXML__jackson-databind__pr6102 (java) --
