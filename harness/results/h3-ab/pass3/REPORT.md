# Overnight run: native vs resident prism_init

Started 2026-09-24 02:39:50. 19 tasks, model=sonnet, arms=prism_body_baseline vs prism_body_exp.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-24 02:39:50] starting: 19 tasks, 0 already done

> [2026-09-24 02:39:50] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=441084 turns=10 wall_s=33.0
- prism : resolved=False tokens=564686 turns=12 wall_s=43.9 prism_calls=2
- token ratio (prism/native): 1.28x

> [2026-09-24 02:41:17]    native resolved=False tokens=441084 | prism resolved=False tokens=564686 prism_calls=2

> [2026-09-24 02:41:17] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=515964 turns=12 wall_s=48.2
- prism : resolved=False tokens=941275 turns=19 wall_s=68.7 prism_calls=3
- token ratio (prism/native): 1.82x

**FLAGGED** (token ratio 1.82x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=12 tokens=515964 wall_s=48.2 cost=$0.21309020000000004
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 7}
- **prism**: resolved=False turns=19 tokens=941275 wall_s=68.7 cost=$0.3434870000000001
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Edit': 2, 'Bash': 12}

> [2026-09-24 02:45:50]    native resolved=False tokens=515964 | prism resolved=False tokens=941275 prism_calls=3 [FLAGGED]

> [2026-09-24 02:45:50] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=1714470 turns=27 wall_s=200.8
- prism : resolved=False tokens=2666029 turns=36 wall_s=281.3 prism_calls=7
- token ratio (prism/native): 1.56x

**FLAGGED** (token ratio 1.56x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=27 tokens=1714470 wall_s=200.8 cost=$0.6215145999999999
  - tools: {'mcp__prism__prism': 4, 'Read': 3, 'Bash': 16, 'Grep': 2, 'Edit': 1}
- **prism**: resolved=False turns=36 tokens=2666029 wall_s=281.3 cost=$0.9529848
  - tools: {'mcp__prism__prism': 7, 'Bash': 22, 'Read': 4, 'Edit': 2}

> [2026-09-24 02:55:55]    native resolved=False tokens=1714470 | prism resolved=False tokens=2666029 prism_calls=7 [FLAGGED]

> [2026-09-24 02:55:55] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=405948 turns=10 wall_s=36.2
- prism : resolved=False tokens=560347 turns=11 wall_s=56.3 prism_calls=5
- token ratio (prism/native): 1.38x

> [2026-09-24 02:59:05]    native resolved=False tokens=405948 | prism resolved=False tokens=560347 prism_calls=5

> [2026-09-24 02:59:05] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=826399 turns=17 wall_s=93.5
- prism : resolved=False tokens=993760 turns=20 wall_s=92.9 prism_calls=5
- token ratio (prism/native): 1.20x

> [2026-09-24 03:05:19]    native resolved=False tokens=826399 | prism resolved=False tokens=993760 prism_calls=5

> [2026-09-24 03:05:19] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=False tokens=390120 turns=10 wall_s=41.7
- prism : resolved=False tokens=605146 turns=15 wall_s=65.9 prism_calls=4
- token ratio (prism/native): 1.55x

**FLAGGED** (token ratio 1.55x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=10 tokens=390120 wall_s=41.7 cost=$0.15187360000000003
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 6}
- **prism**: resolved=False turns=15 tokens=605146 wall_s=65.9 cost=$0.2154218
  - tools: {'mcp__prism__prism': 4, 'Read': 2, 'Edit': 1, 'Bash': 6, 'Grep': 1}

> [2026-09-24 03:09:44]    native resolved=False tokens=390120 | prism resolved=False tokens=605146 prism_calls=4 [FLAGGED]

> [2026-09-24 03:09:44] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=False tokens=2930557 turns=39 wall_s=381.1
- prism : resolved=True tokens=4463949 turns=50 wall_s=334.5 prism_calls=12
- token ratio (prism/native): 1.52x

**FLAGGED** (resolve mismatch, token ratio 1.52x outside [0.67, 1.5])

**Attribution: prism WAS called (12x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=39 tokens=2930557 wall_s=381.1 cost=$1.0775446
  - tools: {'mcp__prism__prism': 6, 'Bash': 21, 'Read': 6, 'Grep': 2, 'Edit': 3}
- **prism**: resolved=True turns=50 tokens=4463949 wall_s=334.5 cost=$1.4910302
  - tools: {'mcp__prism__prism': 12, 'Grep': 6, 'Bash': 25, 'Read': 2, 'ToolSearch': 1, 'Edit': 2, 'Write': 1}

> [2026-09-24 03:23:46]    native resolved=False tokens=2930557 | prism resolved=True tokens=4463949 prism_calls=12 [FLAGGED]

> [2026-09-24 03:23:46] -- gin-gonic__gin__pr4535 (go) --

## gin-gonic__gin__pr4535 (go)

- native: resolved=False tokens=152217 turns=4 wall_s=16.3
- prism : resolved=False tokens=572539 turns=13 wall_s=50.4 prism_calls=3
- token ratio (prism/native): 3.76x

**FLAGGED** (token ratio 3.76x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=4 tokens=152217 wall_s=16.3 cost=$0.0800962
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 1}
- **prism**: resolved=False turns=13 tokens=572539 wall_s=50.4 cost=$0.23164839999999998
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 8}

> [2026-09-24 03:26:04]    native resolved=False tokens=152217 | prism resolved=False tokens=572539 prism_calls=3 [FLAGGED]

> [2026-09-24 03:26:04] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=False tokens=1077567 turns=20 wall_s=98.1
- prism : resolved=False tokens=1910348 turns=36 wall_s=130.5 prism_calls=4
- token ratio (prism/native): 1.77x

**FLAGGED** (token ratio 1.77x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=20 tokens=1077567 wall_s=98.1 cost=$0.40044760000000007
  - tools: {'mcp__prism__prism': 4, 'Read': 1, 'Bash': 11, 'Edit': 2, 'Write': 1}
- **prism**: resolved=False turns=36 tokens=1910348 wall_s=130.5 cost=$0.6222062
  - tools: {'mcp__prism__prism': 4, 'Bash': 20, 'Grep': 5, 'Read': 4, 'Edit': 2}

> [2026-09-24 03:32:32]    native resolved=False tokens=1077567 | prism resolved=False tokens=1910348 prism_calls=4 [FLAGGED]

> [2026-09-24 03:32:32] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=365363 turns=9 wall_s=193.5
- prism : resolved=False tokens=563661 turns=13 wall_s=86.4 prism_calls=3
- token ratio (prism/native): 1.54x

**FLAGGED** (token ratio 1.54x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=9 tokens=365363 wall_s=193.5 cost=$0.18955860000000002
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 4}
- **prism**: resolved=False turns=13 tokens=563661 wall_s=86.4 cost=$0.24344300000000005
  - tools: {'mcp__prism__prism': 3, 'Grep': 2, 'Read': 1, 'Edit': 1, 'Bash': 5}

> [2026-09-24 03:38:03]    native resolved=False tokens=365363 | prism resolved=False tokens=563661 prism_calls=3 [FLAGGED]

> [2026-09-24 03:38:03] -- pallets__click__pr3504 (python) --

## pallets__click__pr3504 (python)

- native: resolved=False tokens=1194746 turns=23 wall_s=138.8
- prism : resolved=False tokens=1075554 turns=20 wall_s=191.5 prism_calls=4
- token ratio (prism/native): 0.90x

> [2026-09-24 03:46:12]    native resolved=False tokens=1194746 | prism resolved=False tokens=1075554 prism_calls=4

> [2026-09-24 03:46:12] -- FasterXML__jackson-databind__pr6061 (java) --

> [2026-09-24 03:50:16] RATE LIMIT on FasterXML__jackson-databind__pr6061/prism_body_exp: sleeping 1800s (hint: 'noring 1 permissions.allow entry from .claude/settings.json: this workspace has not been trusted. run claude code interactively here once and accept t'), then retrying the same cell

## FasterXML__jackson-databind__pr6061 (java)

- native: resolved=False tokens=1404753 turns=28 wall_s=135.7
- prism : resolved=False tokens=756952 turns=15 wall_s=162.5 prism_calls=4
- token ratio (prism/native): 0.54x

**FLAGGED** (token ratio 0.54x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=28 tokens=1404753 wall_s=135.7 cost=$0.4774474
  - tools: {'Bash': 18, 'mcp__prism__prism': 3, 'ToolSearch': 1, 'Grep': 2, 'Read': 2, 'Edit': 1}
- **prism**: resolved=False turns=15 tokens=756952 wall_s=162.5 cost=$0.31950660000000003
  - tools: {'mcp__prism__prism': 4, 'ToolSearch': 1, 'Bash': 6, 'Read': 1, 'Edit': 1, 'Write': 1}

> [2026-09-24 04:24:00]    native resolved=False tokens=1404753 | prism resolved=False tokens=756952 prism_calls=4 [FLAGGED]

> [2026-09-24 04:24:00] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=302318 turns=7 wall_s=338.5
- prism : resolved=False tokens=336015 turns=8 wall_s=57.6 prism_calls=3
- token ratio (prism/native): 1.11x

> [2026-09-24 04:31:28]    native resolved=False tokens=302318 | prism resolved=False tokens=336015 prism_calls=3

> [2026-09-24 04:31:28] -- FasterXML__jackson-databind__pr6044 (java) --

## FasterXML__jackson-databind__pr6044 (java)

- native: resolved=False tokens=2267564 turns=30 wall_s=271.0
- prism : resolved=False tokens=1803829 turns=25 wall_s=309.9 prism_calls=6
- token ratio (prism/native): 0.80x

> [2026-09-24 04:42:52]    native resolved=False tokens=2267564 | prism resolved=False tokens=1803829 prism_calls=6

> [2026-09-24 04:42:52] -- FasterXML__jackson-databind__pr6018 (java) --

## FasterXML__jackson-databind__pr6018 (java)

- native: resolved=False tokens=1811783 turns=28 wall_s=181.7
- prism : resolved=False tokens=3416380 turns=44 wall_s=364.9 prism_calls=17
- token ratio (prism/native): 1.89x

**FLAGGED** (token ratio 1.89x outside [0.67, 1.5])

**Attribution: prism WAS called (17x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=28 tokens=1811783 wall_s=181.7 cost=$0.6896706000000001
  - tools: {'mcp__prism__prism': 4, 'Read': 4, 'Bash': 17, 'Edit': 2}
- **prism**: resolved=False turns=44 tokens=3416380 wall_s=364.9 cost=$1.2203532000000001
  - tools: {'mcp__prism__prism': 17, 'Bash': 19, 'Grep': 3, 'Read': 1, 'Edit': 3}

> [2026-09-24 04:54:04]    native resolved=False tokens=1811783 | prism resolved=False tokens=3416380 prism_calls=17 [FLAGGED]

> [2026-09-24 04:54:04] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=1058135 turns=20 wall_s=113.2
- prism : resolved=False tokens=1205919 turns=23 wall_s=133.6 prism_calls=6
- token ratio (prism/native): 1.14x

> [2026-09-24 05:00:48]    native resolved=False tokens=1058135 | prism resolved=False tokens=1205919 prism_calls=6

> [2026-09-24 05:00:48] -- pallets__click__pr3473 (python) --

## pallets__click__pr3473 (python)

- native: resolved=False tokens=1468529 turns=27 wall_s=109.7
- prism : resolved=False tokens=1629454 turns=24 wall_s=135.1 prism_calls=6
- token ratio (prism/native): 1.11x

> [2026-09-24 05:07:29]    native resolved=False tokens=1468529 | prism resolved=False tokens=1629454 prism_calls=6

> [2026-09-24 05:07:29] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=True tokens=3533842 turns=52 wall_s=377.0
- prism : resolved=False tokens=1280778 turns=26 wall_s=103.0 prism_calls=3
- token ratio (prism/native): 0.36x

**FLAGGED** (resolve mismatch, token ratio 0.36x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=52 tokens=3533842 wall_s=377.0 cost=$1.1590702000000002
  - tools: {'mcp__prism__prism': 3, 'Read': 5, 'Edit': 15, 'Bash': 28}
- **prism**: resolved=False turns=26 tokens=1280778 wall_s=103.0 cost=$0.4293798000000001
  - tools: {'mcp__prism__prism': 3, 'Grep': 3, 'Edit': 11, 'Bash': 8}

> [2026-09-24 05:15:41]    native resolved=True tokens=3533842 | prism resolved=False tokens=1280778 prism_calls=3 [FLAGGED]

> [2026-09-24 05:15:41] -- FasterXML__jackson-databind__pr6076 (java) --

## FasterXML__jackson-databind__pr6076 (java)

- native: resolved=False tokens=1415301 turns=19 wall_s=223.8
- prism : resolved=False tokens=2924434 turns=38 wall_s=356.3 prism_calls=4
- token ratio (prism/native): 2.07x

**FLAGGED** (token ratio 2.07x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=19 tokens=1415301 wall_s=223.8 cost=$0.7145021999999999
  - tools: {'mcp__prism__prism': 3, 'Read': 5, 'Bash': 7, 'Edit': 3}
- **prism**: resolved=False turns=38 tokens=2924434 wall_s=356.3 cost=$1.0601701999999997
  - tools: {'mcp__prism__prism': 4, 'Grep': 3, 'Read': 7, 'Edit': 5, 'Bash': 18}

> [2026-09-24 05:26:59]    native resolved=False tokens=1415301 | prism resolved=False tokens=2924434 prism_calls=4 [FLAGGED]


# SUMMARY

19/19 tasks completed.

- native resolved: 1/19
- prism  resolved: 1/19
- native tokens total: 23276660
- prism  tokens total: 28271055 (1.21x native)
- flagged cells: 11 (0 non-adoption, 11 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- pallets__click__pr3471
- FasterXML__jackson-databind__pr6030
- pallets__click__pr3434
- FasterXML__jackson-databind__pr6019
- gin-gonic__gin__pr4535
- pallets__click__pr3653
- apache__commons-lang__pr1703
- FasterXML__jackson-databind__pr6061
- FasterXML__jackson-databind__pr6018
- akheron__jansson__pr731
- FasterXML__jackson-databind__pr6076

Completed 2026-09-24 05:26:59

> [2026-09-24 05:26:59] DONE: 19/19 tasks, 11 flagged (0 non-adoption, 11 real)
