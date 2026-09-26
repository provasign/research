# Overnight run: native vs resident prism_init

Started 2026-09-24 00:22:24. 19 tasks, model=sonnet, arms=prism_body_baseline vs prism_body_exp.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-24 00:22:24] starting: 19 tasks, 0 already done

> [2026-09-24 00:22:24] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=658826 turns=14 wall_s=62.2
- prism : resolved=False tokens=526651 turns=12 wall_s=40.9 prism_calls=4
- token ratio (prism/native): 0.80x

> [2026-09-24 00:24:17]    native resolved=False tokens=658826 | prism resolved=False tokens=526651 prism_calls=4

> [2026-09-24 00:24:17] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=605762 turns=14 wall_s=63.6
- prism : resolved=False tokens=938489 turns=20 wall_s=76.3 prism_calls=3
- token ratio (prism/native): 1.55x

**FLAGGED** (token ratio 1.55x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=14 tokens=605762 wall_s=63.6 cost=$0.2356508
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 9}
- **prism**: resolved=False turns=20 tokens=938489 wall_s=76.3 cost=$0.33005300000000004
  - tools: {'mcp__prism__prism': 3, 'Edit': 2, 'Bash': 12, 'Read': 1, 'Grep': 1}

> [2026-09-24 00:29:12]    native resolved=False tokens=605762 | prism resolved=False tokens=938489 prism_calls=3 [FLAGGED]

> [2026-09-24 00:29:12] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=True tokens=1510188 turns=23 wall_s=159.3
- prism : resolved=False tokens=1246581 turns=20 wall_s=169.9 prism_calls=5
- token ratio (prism/native): 0.83x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=23 tokens=1510188 wall_s=159.3 cost=$0.601597
  - tools: {'mcp__prism__prism': 2, 'Bash': 10, 'Read': 3, 'ToolSearch': 1, 'Edit': 6}
- **prism**: resolved=False turns=20 tokens=1246581 wall_s=169.9 cost=$0.5088879999999999
  - tools: {'mcp__prism__prism': 4, 'mcp__prism__search': 1, 'Bash': 10, 'Read': 2, 'ToolSearch': 1, 'Edit': 1}

> [2026-09-24 00:36:42]    native resolved=True tokens=1510188 | prism resolved=False tokens=1246581 prism_calls=5 [FLAGGED]

> [2026-09-24 00:36:42] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=487673 turns=10 wall_s=56.1
- prism : resolved=False tokens=438738 turns=9 wall_s=55.8 prism_calls=3
- token ratio (prism/native): 0.90x

> [2026-09-24 00:40:14]    native resolved=False tokens=487673 | prism resolved=False tokens=438738 prism_calls=3

> [2026-09-24 00:40:14] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=784160 turns=15 wall_s=94.3
- prism : resolved=False tokens=1074306 turns=22 wall_s=90.5 prism_calls=6
- token ratio (prism/native): 1.37x

> [2026-09-24 00:46:27]    native resolved=False tokens=784160 | prism resolved=False tokens=1074306 prism_calls=6

> [2026-09-24 00:46:27] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=True tokens=618365 turns=15 wall_s=44.9
- prism : resolved=False tokens=753431 turns=18 wall_s=58.5 prism_calls=2
- token ratio (prism/native): 1.22x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=618365 wall_s=44.9 cost=$0.2238032
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Read': 2, 'Bash': 8}
- **prism**: resolved=False turns=18 tokens=753431 wall_s=58.5 cost=$0.2561668
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 13}

> [2026-09-24 00:50:47]    native resolved=True tokens=618365 | prism resolved=False tokens=753431 prism_calls=2 [FLAGGED]

> [2026-09-24 00:50:47] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=True tokens=2308438 turns=35 wall_s=301.3
- prism : resolved=False tokens=3550340 turns=45 wall_s=246.3 prism_calls=11
- token ratio (prism/native): 1.54x

**FLAGGED** (resolve mismatch, token ratio 1.54x outside [0.67, 1.5])

**Attribution: prism WAS called (11x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=35 tokens=2308438 wall_s=301.3 cost=$0.8609080000000003
  - tools: {'mcp__prism__prism': 11, 'Bash': 18, 'Grep': 1, 'Read': 2, 'Edit': 2}
- **prism**: resolved=False turns=45 tokens=3550340 wall_s=246.3 cost=$1.1960552000000002
  - tools: {'mcp__prism__prism': 11, 'Grep': 4, 'Read': 5, 'Bash': 19, 'Edit': 5}

> [2026-09-24 01:01:58]    native resolved=True tokens=2308438 | prism resolved=False tokens=3550340 prism_calls=11 [FLAGGED]

> [2026-09-24 01:01:58] -- gin-gonic__gin__pr4535 (go) --

## gin-gonic__gin__pr4535 (go)

- native: resolved=False tokens=191737 turns=5 wall_s=18.4
- prism : resolved=False tokens=449465 turns=11 wall_s=36.3 prism_calls=2
- token ratio (prism/native): 2.34x

**FLAGGED** (token ratio 2.34x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=5 tokens=191737 wall_s=18.4 cost=$0.09113960000000002
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=False turns=11 tokens=449465 wall_s=36.3 cost=$0.1790264
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 7}

> [2026-09-24 01:04:04]    native resolved=False tokens=191737 | prism resolved=False tokens=449465 prism_calls=2 [FLAGGED]

> [2026-09-24 01:04:04] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=True tokens=926977 turns=18 wall_s=94.1
- prism : resolved=True tokens=1326186 turns=26 wall_s=130.4 prism_calls=7
- token ratio (prism/native): 1.43x

> [2026-09-24 01:10:25]    native resolved=True tokens=926977 | prism resolved=True tokens=1326186 prism_calls=7

> [2026-09-24 01:10:25] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=838844 turns=17 wall_s=326.5
- prism : resolved=False tokens=59238 turns=1 wall_s=793.6 prism_calls=4
- token ratio (prism/native): 0.07x

**FLAGGED** (token ratio 0.07x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=17 tokens=838844 wall_s=326.5 cost=$0.3782424
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Edit': 2, 'Bash': 10}
- **prism**: resolved=False turns=1 tokens=59238 wall_s=793.6 cost=$0.33409300000000003
  - tools: {'mcp__prism__prism': 4, 'Edit': 2, 'Bash': 6, 'ToolSearch': 1, 'Monitor': 1}

> [2026-09-24 01:29:59]    native resolved=False tokens=838844 | prism resolved=False tokens=59238 prism_calls=4 [FLAGGED]

> [2026-09-24 01:29:59] -- pallets__click__pr3504 (python) --

## pallets__click__pr3504 (python)

- native: resolved=False tokens=646011 turns=14 wall_s=63.3
- prism : resolved=False tokens=485905 turns=11 wall_s=50.3 prism_calls=2
- token ratio (prism/native): 0.75x

> [2026-09-24 01:31:54]    native resolved=False tokens=646011 | prism resolved=False tokens=485905 prism_calls=2

> [2026-09-24 01:31:54] -- FasterXML__jackson-databind__pr6061 (java) --

## FasterXML__jackson-databind__pr6061 (java)

- native: resolved=False tokens=1205973 turns=27 wall_s=106.6
- prism : resolved=True tokens=2574038 turns=51 wall_s=276.7 prism_calls=2
- token ratio (prism/native): 2.13x

**FLAGGED** (resolve mismatch, token ratio 2.13x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=27 tokens=1205973 wall_s=106.6 cost=$0.4081202
  - tools: {'Bash': 19, 'ToolSearch': 1, 'mcp__prism__prism': 4, 'Grep': 1, 'Edit': 1}
- **prism**: resolved=True turns=51 tokens=2574038 wall_s=276.7 cost=$0.8053779999999999
  - tools: {'Bash': 34, 'Read': 4, 'Edit': 6, 'Write': 2, 'mcp__prism__prism': 2, 'Grep': 2}

> [2026-09-24 01:40:22]    native resolved=False tokens=1205973 | prism resolved=True tokens=2574038 prism_calls=2 [FLAGGED]

> [2026-09-24 01:40:22] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=382013 turns=9 wall_s=51.3
- prism : resolved=False tokens=592788 turns=12 wall_s=406.5 prism_calls=4
- token ratio (prism/native): 1.55x

**FLAGGED** (token ratio 1.55x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=9 tokens=382013 wall_s=51.3 cost=$0.1917694
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 4}
- **prism**: resolved=False turns=12 tokens=592788 wall_s=406.5 cost=$0.29824900000000004
  - tools: {'mcp__prism__prism': 4, 'Glob': 1, 'Edit': 1, 'Bash': 5}

> [2026-09-24 01:48:52]    native resolved=False tokens=382013 | prism resolved=False tokens=592788 prism_calls=4 [FLAGGED]

> [2026-09-24 01:48:52] -- FasterXML__jackson-databind__pr6044 (java) --

## FasterXML__jackson-databind__pr6044 (java)

- native: resolved=False tokens=1504409 turns=25 wall_s=168.3
- prism : resolved=False tokens=857202 turns=18 wall_s=157.8 prism_calls=2
- token ratio (prism/native): 0.57x

**FLAGGED** (token ratio 0.57x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=25 tokens=1504409 wall_s=168.3 cost=$0.5865956
  - tools: {'mcp__prism__prism': 3, 'Bash': 13, 'mcp__prism__query': 1, 'ToolSearch': 1, 'Read': 2, 'Edit': 3, 'Write': 1}
- **prism**: resolved=False turns=18 tokens=857202 wall_s=157.8 cost=$0.33283979999999996
  - tools: {'mcp__prism__prism': 2, 'Bash': 15}

> [2026-09-24 01:55:58]    native resolved=False tokens=1504409 | prism resolved=False tokens=857202 prism_calls=2 [FLAGGED]

> [2026-09-24 01:55:58] -- FasterXML__jackson-databind__pr6018 (java) --

## FasterXML__jackson-databind__pr6018 (java)

- native: resolved=False tokens=1147349 turns=19 wall_s=105.8
- prism : resolved=False tokens=1948671 turns=31 wall_s=191.9 prism_calls=5
- token ratio (prism/native): 1.70x

**FLAGGED** (token ratio 1.70x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=19 tokens=1147349 wall_s=105.8 cost=$0.4700774
  - tools: {'mcp__prism__prism': 4, 'Read': 4, 'Bash': 7, 'Grep': 1, 'Edit': 2}
- **prism**: resolved=False turns=31 tokens=1948671 wall_s=191.9 cost=$0.6837448
  - tools: {'mcp__prism__prism': 5, 'Read': 3, 'Bash': 19, 'Edit': 2, 'Write': 1}

> [2026-09-24 02:03:01]    native resolved=False tokens=1147349 | prism resolved=False tokens=1948671 prism_calls=5 [FLAGGED]

> [2026-09-24 02:03:01] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=693937 turns=14 wall_s=75.4
- prism : resolved=False tokens=908700 turns=17 wall_s=119.4 prism_calls=5
- token ratio (prism/native): 1.31x

> [2026-09-24 02:08:53]    native resolved=False tokens=693937 | prism resolved=False tokens=908700 prism_calls=5

> [2026-09-24 02:08:53] -- pallets__click__pr3473 (python) --

## pallets__click__pr3473 (python)

- native: resolved=False tokens=1065489 turns=21 wall_s=96.9
- prism : resolved=False tokens=991554 turns=21 wall_s=96.9 prism_calls=3
- token ratio (prism/native): 0.93x

> [2026-09-24 02:14:43]    native resolved=False tokens=1065489 | prism resolved=False tokens=991554 prism_calls=3

> [2026-09-24 02:14:43] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=True tokens=1878834 turns=32 wall_s=184.7
- prism : resolved=True tokens=2012553 turns=32 wall_s=173.1 prism_calls=6
- token ratio (prism/native): 1.07x

> [2026-09-24 02:20:51]    native resolved=True tokens=1878834 | prism resolved=True tokens=2012553 prism_calls=6

> [2026-09-24 02:20:51] -- FasterXML__jackson-databind__pr6076 (java) --

## FasterXML__jackson-databind__pr6076 (java)

- native: resolved=False tokens=3131843 turns=38 wall_s=565.3
- prism : resolved=False tokens=3966917 turns=46 wall_s=472.1 prism_calls=4
- token ratio (prism/native): 1.27x

> [2026-09-24 02:39:50]    native resolved=False tokens=3131843 | prism resolved=False tokens=3966917 prism_calls=4


# SUMMARY

19/19 tasks completed.

- native resolved: 5/19
- prism  resolved: 3/19
- native tokens total: 20586828
- prism  tokens total: 24701753 (1.20x native)
- flagged cells: 10 (0 non-adoption, 10 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- pallets__click__pr3471
- FasterXML__jackson-databind__pr6030
- pallets__click__pr3434
- FasterXML__jackson-databind__pr6019
- gin-gonic__gin__pr4535
- apache__commons-lang__pr1703
- FasterXML__jackson-databind__pr6061
- apache__commons-lang__pr1655
- FasterXML__jackson-databind__pr6044
- FasterXML__jackson-databind__pr6018

Completed 2026-09-24 02:39:50

> [2026-09-24 02:39:50] DONE: 19/19 tasks, 10 flagged (0 non-adoption, 10 real)
