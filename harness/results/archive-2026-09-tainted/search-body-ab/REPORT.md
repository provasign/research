# Overnight run: native vs resident prism_init

Started 2026-09-22 23:25:03. 50 tasks, model=sonnet, arms=prism_body_baseline vs prism_body_exp.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-22 23:25:03] starting: 50 tasks, 0 already done

> [2026-09-22 23:25:03] -- gin-gonic__gin__pr4695 (go) --

## gin-gonic__gin__pr4695 (go)

- native: resolved=True tokens=236259 turns=6 wall_s=15.7
- prism : resolved=True tokens=190389 turns=5 wall_s=11.6 prism_calls=2
- token ratio (prism/native): 0.81x

> [2026-09-22 23:26:50]    native resolved=True tokens=236259 | prism resolved=True tokens=190389 prism_calls=2

> [2026-09-22 23:26:50] -- gin-gonic__gin__pr4698 (go) --

## gin-gonic__gin__pr4698 (go)

- native: resolved=True tokens=222039 turns=6 wall_s=19.1
- prism : resolved=True tokens=222247 turns=6 wall_s=24.4 prism_calls=1
- token ratio (prism/native): 1.00x

> [2026-09-22 23:29:08]    native resolved=True tokens=222039 | prism resolved=True tokens=222247 prism_calls=1

> [2026-09-22 23:29:08] -- Textualize__rich__pr3882 (python) --

## Textualize__rich__pr3882 (python)

- native: resolved=True tokens=108415 turns=3 wall_s=5.5
- prism : resolved=True tokens=108307 turns=3 wall_s=8.1 prism_calls=1
- token ratio (prism/native): 1.00x

> [2026-09-22 23:29:47]    native resolved=True tokens=108415 | prism resolved=True tokens=108307 prism_calls=1

> [2026-09-22 23:29:47] -- psf__requests__pr7315 (python) --

## psf__requests__pr7315 (python)

- native: resolved=False tokens=980457 turns=21 wall_s=129.3
- prism : resolved=False tokens=1240536 turns=24 wall_s=148.8 prism_calls=6
- token ratio (prism/native): 1.27x

> [2026-09-22 23:35:13]    native resolved=False tokens=980457 | prism resolved=False tokens=1240536 prism_calls=6

> [2026-09-22 23:35:13] -- gin-gonic__gin__pr4472 (go) --

## gin-gonic__gin__pr4472 (go)

- native: resolved=True tokens=263895 turns=7 wall_s=13.7
- prism : resolved=True tokens=225737 turns=6 wall_s=20.9 prism_calls=3
- token ratio (prism/native): 0.86x

> [2026-09-22 23:36:58]    native resolved=True tokens=263895 | prism resolved=True tokens=225737 prism_calls=3

> [2026-09-22 23:36:58] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=538910 turns=14 wall_s=55.3
- prism : resolved=False tokens=533567 turns=12 wall_s=45.6 prism_calls=4
- token ratio (prism/native): 0.99x

> [2026-09-22 23:38:49]    native resolved=False tokens=538910 | prism resolved=False tokens=533567 prism_calls=4

> [2026-09-22 23:38:49] -- gin-gonic__gin__pr4819 (go) --

## gin-gonic__gin__pr4819 (go)

- native: resolved=True tokens=196429 turns=5 wall_s=19.3
- prism : resolved=True tokens=199474 turns=5 wall_s=13.5 prism_calls=1
- token ratio (prism/native): 1.02x

> [2026-09-22 23:42:30]    native resolved=True tokens=196429 | prism resolved=True tokens=199474 prism_calls=1

> [2026-09-22 23:42:30] -- pallets__click__pr3466 (python) --

## pallets__click__pr3466 (python)

- native: resolved=True tokens=1891215 turns=33 wall_s=202.1
- prism : resolved=True tokens=1170775 turns=24 wall_s=90.0 prism_calls=5
- token ratio (prism/native): 0.62x

**FLAGGED** (token ratio 0.62x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=33 tokens=1891215 wall_s=202.1 cost=$0.7059755999999998
  - tools: {'mcp__prism__prism': 3, 'Grep': 4, 'Read': 4, 'Bash': 18, 'ToolSearch': 1, 'WebSearch': 1, 'Edit': 1}
- **prism**: resolved=True turns=24 tokens=1170775 wall_s=90.0 cost=$0.5739425
  - tools: {'mcp__prism__prism': 5, 'Read': 1, 'Grep': 2, 'Agent': 1, 'Bash': 12, 'ScheduleWakeup': 1, 'Edit': 1}

> [2026-09-22 23:50:03]    native resolved=True tokens=1891215 | prism resolved=True tokens=1170775 prism_calls=5 [FLAGGED]

> [2026-09-22 23:50:03] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=True tokens=479443 turns=11 wall_s=52.6
- prism : resolved=False tokens=939292 turns=23 wall_s=69.9 prism_calls=1
- token ratio (prism/native): 1.96x

**FLAGGED** (resolve mismatch, token ratio 1.96x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=479443 wall_s=52.6 cost=$0.19962240000000003
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 8}
- **prism**: resolved=False turns=23 tokens=939292 wall_s=69.9 cost=$0.29231120000000005
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Edit': 1, 'Bash': 19}

> [2026-09-22 23:54:46]    native resolved=True tokens=479443 | prism resolved=False tokens=939292 prism_calls=1 [FLAGGED]

> [2026-09-22 23:54:46] -- FasterXML__jackson-databind__pr6012 (java) --

## FasterXML__jackson-databind__pr6012 (java)

- native: resolved=True tokens=353866 turns=9 wall_s=81.4
- prism : resolved=True tokens=355521 turns=10 wall_s=36.1 prism_calls=2
- token ratio (prism/native): 1.00x

> [2026-09-22 23:58:41]    native resolved=True tokens=353866 | prism resolved=True tokens=355521 prism_calls=2

> [2026-09-22 23:58:41] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=111373 turns=3 wall_s=6.9
- prism : resolved=True tokens=111367 turns=3 wall_s=7.6 prism_calls=1
- token ratio (prism/native): 1.00x

> [2026-09-22 23:59:46]    native resolved=True tokens=111373 | prism resolved=True tokens=111367 prism_calls=1

> [2026-09-22 23:59:46] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=948796 turns=19 wall_s=88.2
- prism : resolved=False tokens=1665189 turns=29 wall_s=130.5 prism_calls=6
- token ratio (prism/native): 1.76x

**FLAGGED** (token ratio 1.76x outside [0.67, 1.5])

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=19 tokens=948796 wall_s=88.2 cost=$0.3584266
  - tools: {'mcp__prism__prism': 4, 'mcp__prism__search': 1, 'Bash': 7, 'Read': 3, 'ToolSearch': 1, 'Grep': 1, 'Edit': 1}
- **prism**: resolved=False turns=29 tokens=1665189 wall_s=130.5 cost=$0.5781488000000001
  - tools: {'mcp__prism__prism': 5, 'mcp__prism__read': 1, 'Read': 3, 'Bash': 16, 'Glob': 1, 'ToolSearch': 1, 'Edit': 1}

> [2026-09-23 00:05:36]    native resolved=False tokens=948796 | prism resolved=False tokens=1665189 prism_calls=6 [FLAGGED]

> [2026-09-23 00:05:36] -- FasterXML__jackson-databind__pr6102 (java) --

## FasterXML__jackson-databind__pr6102 (java)

- native: resolved=True tokens=256491 turns=6 wall_s=22.4
- prism : resolved=True tokens=430008 turns=10 wall_s=36.6 prism_calls=1
- token ratio (prism/native): 1.68x

**FLAGGED** (token ratio 1.68x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=6 tokens=256491 wall_s=22.4 cost=$0.126563
  - tools: {'mcp__prism__prism': 1, 'Edit': 2, 'Bash': 2}
- **prism**: resolved=True turns=10 tokens=430008 wall_s=36.6 cost=$0.1683028
  - tools: {'mcp__prism__prism': 1, 'Bash': 5, 'Read': 1, 'Edit': 2}

> [2026-09-23 00:08:40]    native resolved=True tokens=256491 | prism resolved=True tokens=430008 prism_calls=1 [FLAGGED]

> [2026-09-23 00:08:40] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=409593 turns=9 wall_s=52.5
- prism : resolved=False tokens=488662 turns=10 wall_s=47.0 prism_calls=3
- token ratio (prism/native): 1.19x

> [2026-09-23 00:11:58]    native resolved=False tokens=409593 | prism resolved=False tokens=488662 prism_calls=3

> [2026-09-23 00:11:58] -- FasterXML__jackson-databind__pr6105 (java) --

## FasterXML__jackson-databind__pr6105 (java)

- native: resolved=True tokens=392442 turns=9 wall_s=27.2
- prism : resolved=True tokens=434765 turns=10 wall_s=26.3 prism_calls=0
- token ratio (prism/native): 1.11x

> [2026-09-23 00:18:01]    native resolved=True tokens=392442 | prism resolved=True tokens=434765 prism_calls=0

> [2026-09-23 00:18:01] -- expressjs__express__pr7459 (js) --

## expressjs__express__pr7459 (js)

- native: resolved=True tokens=316894 turns=8 wall_s=38.2
- prism : resolved=True tokens=295656 turns=7 wall_s=20.6 prism_calls=1
- token ratio (prism/native): 0.93x

> [2026-09-23 00:19:19]    native resolved=True tokens=316894 | prism resolved=True tokens=295656 prism_calls=1

> [2026-09-23 00:19:19] -- pallets__click__pr3534 (python) --

## pallets__click__pr3534 (python)

- native: resolved=True tokens=578874 turns=13 wall_s=53.9
- prism : resolved=True tokens=492440 turns=12 wall_s=28.2 prism_calls=4
- token ratio (prism/native): 0.85x

> [2026-09-23 00:23:19]    native resolved=True tokens=578874 | prism resolved=True tokens=492440 prism_calls=4

> [2026-09-23 00:23:19] -- FasterXML__jackson-databind__pr6056 (java) --

## FasterXML__jackson-databind__pr6056 (java)

- native: resolved=True tokens=917346 turns=16 wall_s=83.3
- prism : resolved=True tokens=1181673 turns=18 wall_s=109.6 prism_calls=4
- token ratio (prism/native): 1.29x

> [2026-09-23 00:27:54]    native resolved=True tokens=917346 | prism resolved=True tokens=1181673 prism_calls=4

> [2026-09-23 00:27:54] -- apache__commons-lang__pr1670 (java) --

## apache__commons-lang__pr1670 (java)

- native: resolved=True tokens=1908970 turns=34 wall_s=401.4
- prism : resolved=True tokens=439979 turns=10 wall_s=48.8 prism_calls=2
- token ratio (prism/native): 0.23x

**FLAGGED** (token ratio 0.23x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=34 tokens=1908970 wall_s=401.4 cost=$0.7705028
  - tools: {'mcp__prism__prism': 9, 'Read': 5, 'Edit': 7, 'Bash': 12}
- **prism**: resolved=True turns=10 tokens=439979 wall_s=48.8 cost=$0.20515199999999997
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 6}

> [2026-09-23 00:36:18]    native resolved=True tokens=1908970 | prism resolved=True tokens=439979 prism_calls=2 [FLAGGED]

> [2026-09-23 00:36:18] -- FasterXML__jackson-databind__pr6039 (java) --

## FasterXML__jackson-databind__pr6039 (java)

- native: resolved=True tokens=3416360 turns=47 wall_s=767.0
- prism : resolved=True tokens=608213 turns=12 wall_s=60.9 prism_calls=2
- token ratio (prism/native): 0.18x

**FLAGGED** (token ratio 0.18x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=47 tokens=3416360 wall_s=767.0 cost=$1.1698380000000002
  - tools: {'mcp__prism__prism': 6, 'Bash': 27, 'Glob': 1, 'ToolSearch': 1, 'Read': 5, 'Grep': 2, 'Edit': 2, 'Write': 1, 'ScheduleWakeup': 1}
- **prism**: resolved=True turns=12 tokens=608213 wall_s=60.9 cost=$0.2802706
  - tools: {'mcp__prism__prism': 2, 'Bash': 6, 'Read': 2, 'Edit': 1}

> [2026-09-23 00:51:29]    native resolved=True tokens=3416360 | prism resolved=True tokens=608213 prism_calls=2 [FLAGGED]

> [2026-09-23 00:51:29] -- apache__commons-lang__pr1699 (java) --

## apache__commons-lang__pr1699 (java)

- native: resolved=True tokens=343293 turns=8 wall_s=29.3
- prism : resolved=True tokens=110501 turns=4 wall_s=11.0 prism_calls=1
- token ratio (prism/native): 0.32x

**FLAGGED** (token ratio 0.32x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=8 tokens=343293 wall_s=29.3 cost=$0.15357339999999997
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 3}
- **prism**: resolved=True turns=4 tokens=110501 wall_s=11.0 cost=$0.0652066
  - tools: {'mcp__prism__prism': 1, 'Edit': 2}

> [2026-09-23 00:53:00]    native resolved=True tokens=343293 | prism resolved=True tokens=110501 prism_calls=1 [FLAGGED]

> [2026-09-23 00:53:00] -- FasterXML__jackson-databind__pr6042 (java) --

## FasterXML__jackson-databind__pr6042 (java)

- native: resolved=True tokens=890158 turns=21 wall_s=105.6
- prism : resolved=True tokens=456274 turns=11 wall_s=46.1 prism_calls=1
- token ratio (prism/native): 0.51x

**FLAGGED** (token ratio 0.51x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=21 tokens=890158 wall_s=105.6 cost=$0.31512840000000003
  - tools: {'mcp__prism__prism': 2, 'Bash': 16, 'ToolSearch': 1, 'Edit': 1}
- **prism**: resolved=True turns=11 tokens=456274 wall_s=46.1 cost=$0.17970980000000003
  - tools: {'Bash': 7, 'mcp__prism__prism': 1, 'Read': 1, 'Edit': 1}

> [2026-09-23 00:57:30]    native resolved=True tokens=890158 | prism resolved=True tokens=456274 prism_calls=1 [FLAGGED]

> [2026-09-23 00:57:30] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=529720 turns=12 wall_s=46.0
- prism : resolved=False tokens=711131 turns=16 wall_s=69.7 prism_calls=6
- token ratio (prism/native): 1.34x

> [2026-09-23 01:02:32]    native resolved=False tokens=529720 | prism resolved=False tokens=711131 prism_calls=6

> [2026-09-23 01:02:32] -- gin-gonic__gin__pr4702 (go) --

## gin-gonic__gin__pr4702 (go)

- native: resolved=True tokens=184422 turns=5 wall_s=12.1
- prism : resolved=True tokens=183950 turns=5 wall_s=9.5 prism_calls=1
- token ratio (prism/native): 1.00x

> [2026-09-23 01:04:04]    native resolved=True tokens=184422 | prism resolved=True tokens=183950 prism_calls=1

> [2026-09-23 01:04:04] -- FasterXML__jackson-databind__pr6047 (java) --

## FasterXML__jackson-databind__pr6047 (java)

- native: resolved=True tokens=273493 turns=7 wall_s=57.9
- prism : resolved=True tokens=292704 turns=7 wall_s=19.2 prism_calls=2
- token ratio (prism/native): 1.07x

> [2026-09-23 01:07:24]    native resolved=True tokens=273493 | prism resolved=True tokens=292704 prism_calls=2

> [2026-09-23 01:07:24] -- pallets__click__pr3482 (python) --

## pallets__click__pr3482 (python)

- native: resolved=True tokens=1001158 turns=20 wall_s=122.4
- prism : resolved=True tokens=661024 turns=15 wall_s=86.5 prism_calls=4
- token ratio (prism/native): 0.66x

**FLAGGED** (token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=20 tokens=1001158 wall_s=122.4 cost=$0.3976219999999999
  - tools: {'mcp__prism__prism': 5, 'Read': 3, 'Grep': 1, 'Edit': 1, 'Bash': 9}
- **prism**: resolved=True turns=15 tokens=661024 wall_s=86.5 cost=$0.2637932
  - tools: {'mcp__prism__prism': 4, 'Read': 1, 'Edit': 1, 'Bash': 8}

> [2026-09-23 01:13:30]    native resolved=True tokens=1001158 | prism resolved=True tokens=661024 prism_calls=4 [FLAGGED]

> [2026-09-23 01:13:30] -- pallets__click__pr3493 (python) --

## pallets__click__pr3493 (python)

- native: resolved=True tokens=300231 turns=8 wall_s=31.5
- prism : resolved=True tokens=520312 turns=13 wall_s=48.5 prism_calls=2
- token ratio (prism/native): 1.73x

**FLAGGED** (token ratio 1.73x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=8 tokens=300231 wall_s=31.5 cost=$0.11746700000000002
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=13 tokens=520312 wall_s=48.5 cost=$0.1917516
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 9}

> [2026-09-23 01:17:26]    native resolved=True tokens=300231 | prism resolved=True tokens=520312 prism_calls=2 [FLAGGED]

> [2026-09-23 01:17:26] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=False tokens=314800 turns=8 wall_s=20.7
- prism : resolved=False tokens=434946 turns=11 wall_s=28.3 prism_calls=2
- token ratio (prism/native): 1.38x

> [2026-09-23 01:20:54]    native resolved=False tokens=314800 | prism resolved=False tokens=434946 prism_calls=2

> [2026-09-23 01:20:54] -- apache__commons-lang__pr1720 (java) --

## apache__commons-lang__pr1720 (java)

- native: resolved=True tokens=492928 turns=12 wall_s=67.8
- prism : resolved=True tokens=326646 turns=8 wall_s=54.9 prism_calls=3
- token ratio (prism/native): 0.66x

**FLAGGED** (token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=492928 wall_s=67.8 cost=$0.18696100000000004
  - tools: {'mcp__prism__prism': 4, 'Edit': 1, 'Bash': 6}
- **prism**: resolved=True turns=8 tokens=326646 wall_s=54.9 cost=$0.14417380000000002
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 3}

> [2026-09-23 01:23:54]    native resolved=True tokens=492928 | prism resolved=True tokens=326646 prism_calls=3 [FLAGGED]

> [2026-09-23 01:23:54] -- apache__commons-lang__pr1713 (java) --

## apache__commons-lang__pr1713 (java)

- native: resolved=True tokens=510593 turns=12 wall_s=72.2
- prism : resolved=True tokens=323563 turns=8 wall_s=36.7 prism_calls=2
- token ratio (prism/native): 0.63x

**FLAGGED** (token ratio 0.63x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=510593 wall_s=72.2 cost=$0.22990780000000002
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 7}
- **prism**: resolved=True turns=8 tokens=323563 wall_s=36.7 cost=$0.1491592
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 3}

> [2026-09-23 01:26:34]    native resolved=True tokens=510593 | prism resolved=True tokens=323563 prism_calls=2 [FLAGGED]

> [2026-09-23 01:26:34] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=False tokens=1857605 turns=27 wall_s=220.3
- prism : resolved=True tokens=2512097 turns=34 wall_s=428.1 prism_calls=8
- token ratio (prism/native): 1.35x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (8x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=27 tokens=1857605 wall_s=220.3 cost=$0.7395454
  - tools: {'mcp__prism__prism': 5, 'Read': 8, 'Grep': 6, 'Edit': 1, 'Bash': 6}
- **prism**: resolved=True turns=34 tokens=2512097 wall_s=428.1 cost=$0.988253
  - tools: {'mcp__prism__prism': 8, 'Bash': 19, 'Read': 3, 'Edit': 2, 'Write': 1}

> [2026-09-23 01:39:31]    native resolved=False tokens=1857605 | prism resolved=True tokens=2512097 prism_calls=8 [FLAGGED]

> [2026-09-23 01:39:31] -- FasterXML__jackson-databind__pr6099 (java) --

## FasterXML__jackson-databind__pr6099 (java)

- native: resolved=True tokens=705595 turns=17 wall_s=90.8
- prism : resolved=True tokens=267490 turns=7 wall_s=45.6 prism_calls=3
- token ratio (prism/native): 0.38x

**FLAGGED** (token ratio 0.38x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=17 tokens=705595 wall_s=90.8 cost=$0.2483156
  - tools: {'mcp__prism__prism': 5, 'Edit': 2, 'Bash': 8, 'Grep': 1}
- **prism**: resolved=True turns=7 tokens=267490 wall_s=45.6 cost=$0.117045
  - tools: {'mcp__prism__prism': 3, 'Edit': 2, 'Bash': 1}

> [2026-09-23 01:43:11]    native resolved=True tokens=705595 | prism resolved=True tokens=267490 prism_calls=3 [FLAGGED]

> [2026-09-23 01:43:11] -- gin-gonic__gin__pr4535 (go) --

## gin-gonic__gin__pr4535 (go)

- native: resolved=False tokens=113137 turns=3 wall_s=6.1
- prism : resolved=False tokens=151915 turns=4 wall_s=8.4 prism_calls=1
- token ratio (prism/native): 1.34x

> [2026-09-23 01:44:36]    native resolved=False tokens=113137 | prism resolved=False tokens=151915 prism_calls=1

> [2026-09-23 01:44:36] -- apache__commons-lang__pr1733 (java) --

## apache__commons-lang__pr1733 (java)

- native: resolved=True tokens=361508 turns=9 wall_s=43.9
- prism : resolved=True tokens=413208 turns=10 wall_s=32.5 prism_calls=3
- token ratio (prism/native): 1.14x

> [2026-09-23 01:46:44]    native resolved=True tokens=361508 | prism resolved=True tokens=413208 prism_calls=3

> [2026-09-23 01:46:44] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=False tokens=1349654 turns=27 wall_s=106.7
- prism : resolved=False tokens=1272625 turns=22 wall_s=84.2 prism_calls=4
- token ratio (prism/native): 0.94x

> [2026-09-23 01:52:35]    native resolved=False tokens=1349654 | prism resolved=False tokens=1272625 prism_calls=4

> [2026-09-23 01:52:35] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=453915 turns=11 wall_s=189.6
- prism : resolved=False tokens=413849 turns=9 wall_s=206.6 prism_calls=1
- token ratio (prism/native): 0.91x

> [2026-09-23 02:00:01]    native resolved=False tokens=453915 | prism resolved=False tokens=413849 prism_calls=1

> [2026-09-23 02:00:01] -- pallets__click__pr3504 (python) --

## pallets__click__pr3504 (python)

- native: resolved=False tokens=453909 turns=10 wall_s=51.1
- prism : resolved=False tokens=1237760 turns=24 wall_s=127.3 prism_calls=1
- token ratio (prism/native): 2.73x

**FLAGGED** (token ratio 2.73x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=10 tokens=453909 wall_s=51.1 cost=$0.1978042
  - tools: {'mcp__prism__prism': 2, 'Bash': 7}
- **prism**: resolved=False turns=24 tokens=1237760 wall_s=127.3 cost=$0.44695759999999995
  - tools: {'mcp__prism__prism': 1, 'Read': 4, 'Bash': 18}

> [2026-09-23 02:03:02]    native resolved=False tokens=453909 | prism resolved=False tokens=1237760 prism_calls=1 [FLAGGED]

> [2026-09-23 02:03:02] -- FasterXML__jackson-databind__pr6061 (java) --

## FasterXML__jackson-databind__pr6061 (java)

- native: resolved=False tokens=983939 turns=22 wall_s=98.0
- prism : resolved=True tokens=563246 turns=13 wall_s=59.3 prism_calls=2
- token ratio (prism/native): 0.57x

**FLAGGED** (resolve mismatch, token ratio 0.57x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=22 tokens=983939 wall_s=98.0 cost=$0.37922039999999996
  - tools: {'Bash': 10, 'mcp__prism__prism': 2, 'Grep': 3, 'ToolSearch': 1, 'WebSearch': 1, 'Read': 3, 'Edit': 1}
- **prism**: resolved=True turns=13 tokens=563246 wall_s=59.3 cost=$0.22563860000000002
  - tools: {'Bash': 6, 'mcp__prism__prism': 2, 'Read': 1, 'Edit': 3}

> [2026-09-23 02:07:44]    native resolved=False tokens=983939 | prism resolved=True tokens=563246 prism_calls=2 [FLAGGED]

> [2026-09-23 02:07:44] -- apache__commons-lang__pr1591 (java) --

## apache__commons-lang__pr1591 (java)

- native: resolved=True tokens=517514 turns=12 wall_s=70.4
- prism : resolved=True tokens=515276 turns=11 wall_s=402.0 prism_calls=3
- token ratio (prism/native): 1.00x

> [2026-09-23 02:16:30]    native resolved=True tokens=517514 | prism resolved=True tokens=515276 prism_calls=3

> [2026-09-23 02:16:30] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=563322 turns=12 wall_s=407.8
- prism : resolved=False tokens=416749 turns=10 wall_s=176.0 prism_calls=4
- token ratio (prism/native): 0.74x

> [2026-09-23 02:27:06]    native resolved=False tokens=563322 | prism resolved=False tokens=416749 prism_calls=4

> [2026-09-23 02:27:06] -- apache__commons-lang__pr1709 (java) --

## apache__commons-lang__pr1709 (java)

- native: resolved=True tokens=564512 turns=13 wall_s=197.2
- prism : resolved=True tokens=405267 turns=11 wall_s=34.2 prism_calls=4
- token ratio (prism/native): 0.72x

> [2026-09-23 02:31:48]    native resolved=True tokens=564512 | prism resolved=True tokens=405267 prism_calls=4

> [2026-09-23 02:31:48] -- FasterXML__jackson-databind__pr6044 (java) --

## FasterXML__jackson-databind__pr6044 (java)

- native: resolved=False tokens=816105 turns=15 wall_s=127.1
- prism : resolved=False tokens=935038 turns=17 wall_s=137.6 prism_calls=4
- token ratio (prism/native): 1.15x

> [2026-09-23 02:37:52]    native resolved=False tokens=816105 | prism resolved=False tokens=935038 prism_calls=4

> [2026-09-23 02:37:52] -- apache__commons-lang__pr1750 (java) --

## apache__commons-lang__pr1750 (java)

- native: resolved=True tokens=349535 turns=9 wall_s=32.6
- prism : resolved=True tokens=561084 turns=13 wall_s=57.7 prism_calls=1
- token ratio (prism/native): 1.61x

**FLAGGED** (token ratio 1.61x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=9 tokens=349535 wall_s=32.6 cost=$0.13840000000000002
  - tools: {'mcp__prism__prism': 2, 'Bash': 6}
- **prism**: resolved=True turns=13 tokens=561084 wall_s=57.7 cost=$0.2117892
  - tools: {'mcp__prism__prism': 1, 'Bash': 9, 'Read': 1, 'Edit': 1}

> [2026-09-23 02:40:14]    native resolved=True tokens=349535 | prism resolved=True tokens=561084 prism_calls=1 [FLAGGED]

> [2026-09-23 02:40:14] -- FasterXML__jackson-databind__pr6018 (java) --

## FasterXML__jackson-databind__pr6018 (java)

- native: resolved=False tokens=927585 turns=17 wall_s=83.6
- prism : resolved=False tokens=821018 turns=16 wall_s=86.6 prism_calls=2
- token ratio (prism/native): 0.89x

> [2026-09-23 02:45:08]    native resolved=False tokens=927585 | prism resolved=False tokens=821018 prism_calls=2

> [2026-09-23 02:45:08] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=1036989 turns=20 wall_s=97.0
- prism : resolved=False tokens=1204015 turns=23 wall_s=83.9 prism_calls=5
- token ratio (prism/native): 1.16x

> [2026-09-23 02:50:46]    native resolved=False tokens=1036989 | prism resolved=False tokens=1204015 prism_calls=5

> [2026-09-23 02:50:46] -- akheron__jansson__pr741 (c) --

## akheron__jansson__pr741 (c)

- native: resolved=True tokens=2028976 turns=36 wall_s=135.1
- prism : resolved=True tokens=1564393 turns=29 wall_s=112.5 prism_calls=2
- token ratio (prism/native): 0.77x

> [2026-09-23 02:55:03]    native resolved=True tokens=2028976 | prism resolved=True tokens=1564393 prism_calls=2

> [2026-09-23 02:55:03] -- pallets__click__pr3473 (python) --

## pallets__click__pr3473 (python)

- native: resolved=False tokens=1489668 turns=25 wall_s=104.7
- prism : resolved=False tokens=992573 turns=19 wall_s=71.3 prism_calls=5
- token ratio (prism/native): 0.67x

**FLAGGED** (token ratio 0.67x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=25 tokens=1489668 wall_s=104.7 cost=$0.545123
  - tools: {'mcp__prism__prism': 6, 'Grep': 3, 'Bash': 9, 'Read': 3, 'Edit': 3}
- **prism**: resolved=False turns=19 tokens=992573 wall_s=71.3 cost=$0.39885879999999996
  - tools: {'mcp__prism__prism': 5, 'Grep': 3, 'Read': 1, 'Bash': 8, 'Edit': 1}

> [2026-09-23 03:00:36]    native resolved=False tokens=1489668 | prism resolved=False tokens=992573 prism_calls=5 [FLAGGED]

> [2026-09-23 03:00:36] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=False tokens=1351844 turns=26 wall_s=101.1
- prism : resolved=True tokens=1968654 turns=37 wall_s=135.6 prism_calls=3
- token ratio (prism/native): 1.46x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=26 tokens=1351844 wall_s=101.1 cost=$0.472146
  - tools: {'mcp__prism__prism': 4, 'Edit': 11, 'Bash': 10}
- **prism**: resolved=True turns=37 tokens=1968654 wall_s=135.6 cost=$0.650646
  - tools: {'mcp__prism__prism': 3, 'Grep': 7, 'Read': 4, 'Edit': 12, 'Bash': 10}

> [2026-09-23 03:04:42]    native resolved=False tokens=1351844 | prism resolved=True tokens=1968654 prism_calls=3 [FLAGGED]

> [2026-09-23 03:04:42] -- FasterXML__jackson-databind__pr6008 (java) --

## FasterXML__jackson-databind__pr6008 (java)

- native: resolved=True tokens=1472859 turns=21 wall_s=216.0
- prism : resolved=True tokens=2311631 turns=32 wall_s=249.1 prism_calls=13
- token ratio (prism/native): 1.57x

**FLAGGED** (token ratio 1.57x outside [0.67, 1.5])

**Attribution: prism WAS called (13x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=21 tokens=1472859 wall_s=216.0 cost=$0.7145900000000001
  - tools: {'mcp__prism__prism': 4, 'Read': 8, 'Grep': 2, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=32 tokens=2311631 wall_s=249.1 cost=$0.945473
  - tools: {'mcp__prism__prism': 13, 'Bash': 13, 'Grep': 2, 'Read': 2, 'Edit': 1}

> [2026-09-23 03:14:29]    native resolved=True tokens=1472859 | prism resolved=True tokens=2311631 prism_calls=13 [FLAGGED]

> [2026-09-23 03:14:29] -- FasterXML__jackson-databind__pr6076 (java) --

## FasterXML__jackson-databind__pr6076 (java)

- native: resolved=False tokens=1285026 turns=19 wall_s=187.8
- prism : resolved=False tokens=4082092 turns=47 wall_s=391.6 prism_calls=2
- token ratio (prism/native): 3.18x

**FLAGGED** (token ratio 3.18x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=19 tokens=1285026 wall_s=187.8 cost=$0.6040234
  - tools: {'mcp__prism__prism': 4, 'Read': 3, 'Bash': 7, 'Grep': 1, 'Edit': 3}
- **prism**: resolved=False turns=47 tokens=4082092 wall_s=391.6 cost=$1.5102096000000005
  - tools: {'mcp__prism__prism': 2, 'Bash': 23, 'Read': 11, 'Grep': 3, 'Write': 2, 'Edit': 4, 'ScheduleWakeup': 1}

> [2026-09-23 03:25:50]    native resolved=False tokens=1285026 | prism resolved=False tokens=4082092 prism_calls=2 [FLAGGED]


# SUMMARY

50/50 tasks completed.

- native resolved: 31/50
- prism  resolved: 33/50
- native tokens total: 38052060
- prism  tokens total: 37964828 (1.00x native)
- flagged cells: 21 (0 non-adoption, 21 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- pallets__click__pr3466
- pallets__click__pr3471
- FasterXML__jackson-databind__pr6030
- FasterXML__jackson-databind__pr6102
- apache__commons-lang__pr1670
- FasterXML__jackson-databind__pr6039
- apache__commons-lang__pr1699
- FasterXML__jackson-databind__pr6042
- pallets__click__pr3482
- pallets__click__pr3493
- apache__commons-lang__pr1720
- apache__commons-lang__pr1713
- FasterXML__jackson-databind__pr6019
- FasterXML__jackson-databind__pr6099
- pallets__click__pr3504
- FasterXML__jackson-databind__pr6061
- apache__commons-lang__pr1750
- pallets__click__pr3473
- akheron__jansson__pr731
- FasterXML__jackson-databind__pr6008
- FasterXML__jackson-databind__pr6076

Completed 2026-09-23 03:25:50

> [2026-09-23 03:25:50] DONE: 50/50 tasks, 21 flagged (0 non-adoption, 21 real)
