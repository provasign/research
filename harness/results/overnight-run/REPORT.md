# Overnight run: native vs resident prism_init

Started 2026-09-20 21:34:49. 50 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-20 21:34:49] starting: 50 tasks, 0 already done

> [2026-09-20 21:34:49] -- gin-gonic__gin__pr4695 (go) --

## gin-gonic__gin__pr4695 (go)

- native: resolved=True tokens=133382 turns=4 wall_s=12.9
- prism : resolved=True tokens=227842 turns=6 wall_s=26.6 prism_calls=2
- token ratio (prism/native): 1.71x

**FLAGGED** (token ratio 1.71x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=4 tokens=133382 wall_s=12.9 cost=$0.0632444
  - tools: {'Grep': 1, 'Edit': 1, 'Bash': 1}
- **prism**: resolved=True turns=6 tokens=227842 wall_s=26.6 cost=$0.12029019999999999
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 2}

> [2026-09-20 21:36:35]    native resolved=True tokens=133382 | prism resolved=True tokens=227842 prism_calls=2 [FLAGGED]

> [2026-09-20 21:36:35] -- gin-gonic__gin__pr4698 (go) --

## gin-gonic__gin__pr4698 (go)

- native: resolved=True tokens=529963 turns=15 wall_s=28.9
- prism : resolved=True tokens=339699 turns=9 wall_s=20.9 prism_calls=2
- token ratio (prism/native): 0.64x

**FLAGGED** (token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=529963 wall_s=28.9 cost=$0.18006100000000005
  - tools: {'Grep': 7, 'Read': 4, 'Bash': 2, 'Edit': 1}
- **prism**: resolved=True turns=9 tokens=339699 wall_s=20.9 cost=$0.1288038
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 2, 'Bash': 3}

> [2026-09-20 21:38:30]    native resolved=True tokens=529963 | prism resolved=True tokens=339699 prism_calls=2 [FLAGGED]

> [2026-09-20 21:38:30] -- Textualize__rich__pr3882 (python) --

## Textualize__rich__pr3882 (python)

- native: resolved=True tokens=303932 turns=9 wall_s=15.5
- prism : resolved=True tokens=108253 turns=3 wall_s=4.7 prism_calls=1
- token ratio (prism/native): 0.36x

**FLAGGED** (token ratio 0.36x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=9 tokens=303932 wall_s=15.5 cost=$0.1285204
  - tools: {'Grep': 2, 'Bash': 4, 'Read': 1, 'Edit': 1}
- **prism**: resolved=True turns=3 tokens=108253 wall_s=4.7 cost=$0.078116
  - tools: {'mcp__prism__prism': 1, 'Edit': 1}

> [2026-09-20 21:39:05]    native resolved=True tokens=303932 | prism resolved=True tokens=108253 prism_calls=1 [FLAGGED]

> [2026-09-20 21:39:05] -- psf__requests__pr7315 (python) --

## psf__requests__pr7315 (python)

- native: resolved=False tokens=1487583 turns=35 wall_s=308.3
- prism : resolved=True tokens=1829588 turns=34 wall_s=250.1 prism_calls=7
- token ratio (prism/native): 1.23x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=35 tokens=1487583 wall_s=308.3 cost=$0.5282998000000001
  - tools: {'Grep': 5, 'Bash': 23, 'Read': 5, 'Edit': 1}
- **prism**: resolved=True turns=34 tokens=1829588 wall_s=250.1 cost=$0.7217142000000001
  - tools: {'mcp__prism__prism': 7, 'Bash': 16, 'Grep': 4, 'ToolSearch': 1, 'WebSearch': 1, 'WebFetch': 1, 'Read': 2, 'Edit': 1}

> [2026-09-20 21:49:02]    native resolved=False tokens=1487583 | prism resolved=True tokens=1829588 prism_calls=7 [FLAGGED]

> [2026-09-20 21:49:02] -- gin-gonic__gin__pr4472 (go) --

## gin-gonic__gin__pr4472 (go)

- native: resolved=True tokens=278128 turns=8 wall_s=16.5
- prism : resolved=True tokens=225050 turns=6 wall_s=18.5 prism_calls=2
- token ratio (prism/native): 0.81x

> [2026-09-20 21:50:44]    native resolved=True tokens=278128 | prism resolved=True tokens=225050 prism_calls=2

> [2026-09-20 21:50:44] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=402125 turns=10 wall_s=28.0
- prism : resolved=False tokens=410656 turns=10 wall_s=27.2 prism_calls=4
- token ratio (prism/native): 1.02x

> [2026-09-20 21:51:49]    native resolved=False tokens=402125 | prism resolved=False tokens=410656 prism_calls=4

> [2026-09-20 21:51:49] -- gin-gonic__gin__pr4819 (go) --

## gin-gonic__gin__pr4819 (go)

- native: resolved=True tokens=236037 turns=7 wall_s=20.8
- prism : resolved=True tokens=198481 turns=5 wall_s=11.5 prism_calls=1
- token ratio (prism/native): 0.84x

> [2026-09-20 21:55:23]    native resolved=True tokens=236037 | prism resolved=True tokens=198481 prism_calls=1

> [2026-09-20 21:55:23] -- pallets__click__pr3466 (python) --

## pallets__click__pr3466 (python)

- native: resolved=True tokens=1551603 turns=33 wall_s=144.0
- prism : resolved=False tokens=1269420 turns=24 wall_s=96.2 prism_calls=5
- token ratio (prism/native): 0.82x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=33 tokens=1551603 wall_s=144.0 cost=$0.5611770000000001
  - tools: {'Grep': 6, 'Read': 9, 'Bash': 16, 'Edit': 1}
- **prism**: resolved=False turns=24 tokens=1269420 wall_s=96.2 cost=$0.46110159999999994
  - tools: {'mcp__prism__prism': 5, 'Grep': 2, 'Read': 1, 'Edit': 4, 'Bash': 11}

> [2026-09-20 22:02:01]    native resolved=True tokens=1551603 | prism resolved=False tokens=1269420 prism_calls=5 [FLAGGED]

> [2026-09-20 22:02:01] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=495946 turns=13 wall_s=58.1
- prism : resolved=True tokens=522035 turns=12 wall_s=42.6 prism_calls=2
- token ratio (prism/native): 1.05x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=13 tokens=495946 wall_s=58.1 cost=$0.193357
  - tools: {'Grep': 1, 'Read': 1, 'Edit': 2, 'Bash': 8}
- **prism**: resolved=True turns=12 tokens=522035 wall_s=42.6 cost=$0.210501
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 8}

> [2026-09-20 22:06:19]    native resolved=False tokens=495946 | prism resolved=True tokens=522035 prism_calls=2 [FLAGGED]

> [2026-09-20 22:06:19] -- FasterXML__jackson-databind__pr6012 (java) --

## FasterXML__jackson-databind__pr6012 (java)

- native: resolved=True tokens=502039 turns=15 wall_s=35.1
- prism : resolved=True tokens=397953 turns=10 wall_s=23.8 prism_calls=3
- token ratio (prism/native): 0.79x

> [2026-09-20 22:11:22]    native resolved=True tokens=502039 | prism resolved=True tokens=397953 prism_calls=3

> [2026-09-20 22:11:22] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=133947 turns=4 wall_s=18.1
- prism : resolved=False tokens=188806 turns=5 wall_s=30.0 prism_calls=1
- token ratio (prism/native): 1.41x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=4 tokens=133947 wall_s=18.1 cost=$0.0849378
  - tools: {'Grep': 1, 'Edit': 1, 'Bash': 1}
- **prism**: resolved=False turns=5 tokens=188806 wall_s=30.0 cost=$0.11098480000000001
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-20 22:12:39]    native resolved=True tokens=133947 | prism resolved=False tokens=188806 prism_calls=1 [FLAGGED]

> [2026-09-20 22:12:39] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=1235018 turns=27 wall_s=334.9
- prism : resolved=True tokens=499866 turns=11 wall_s=37.3 prism_calls=3
- token ratio (prism/native): 0.40x

**FLAGGED** (resolve mismatch, token ratio 0.40x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=27 tokens=1235018 wall_s=334.9 cost=$0.4993918
  - tools: {'Grep': 6, 'Read': 2, 'Bash': 16, 'Edit': 2}
- **prism**: resolved=True turns=11 tokens=499866 wall_s=37.3 cost=$0.2114098
  - tools: {'mcp__prism__prism': 3, 'Grep': 1, 'ToolSearch': 1, 'Bash': 4, 'Edit': 1}

> [2026-09-20 22:20:09]    native resolved=False tokens=1235018 | prism resolved=True tokens=499866 prism_calls=3 [FLAGGED]

> [2026-09-20 22:20:09] -- FasterXML__jackson-databind__pr6102 (java) --

## FasterXML__jackson-databind__pr6102 (java)

- native: resolved=True tokens=439545 turns=11 wall_s=20.3
- prism : resolved=True tokens=255917 turns=6 wall_s=22.1 prism_calls=1
- token ratio (prism/native): 0.58x

**FLAGGED** (token ratio 0.58x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=439545 wall_s=20.3 cost=$0.16588180000000002
  - tools: {'Grep': 3, 'Glob': 1, 'Bash': 3, 'Read': 1, 'Edit': 2}
- **prism**: resolved=True turns=6 tokens=255917 wall_s=22.1 cost=$0.1242264
  - tools: {'mcp__prism__prism': 1, 'Edit': 2, 'Bash': 2}

> [2026-09-20 22:22:06]    native resolved=True tokens=439545 | prism resolved=True tokens=255917 prism_calls=1 [FLAGGED]

> [2026-09-20 22:22:06] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=1150776 turns=24 wall_s=104.8
- prism : resolved=False tokens=378915 turns=8 wall_s=56.2 prism_calls=3
- token ratio (prism/native): 0.33x

**FLAGGED** (token ratio 0.33x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=24 tokens=1150776 wall_s=104.8 cost=$0.4456735999999999
  - tools: {'Bash': 14, 'Read': 4, 'Grep': 4, 'Edit': 1}
- **prism**: resolved=False turns=8 tokens=378915 wall_s=56.2 cost=$0.1934206
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Bash': 3}

> [2026-09-20 22:25:39]    native resolved=False tokens=1150776 | prism resolved=False tokens=378915 prism_calls=3 [FLAGGED]

> [2026-09-20 22:25:39] -- FasterXML__jackson-databind__pr6105 (java) --

## FasterXML__jackson-databind__pr6105 (java)

- native: resolved=False tokens=1632020 turns=32 wall_s=485.0
- prism : resolved=True tokens=634020 turns=14 wall_s=54.7 prism_calls=0
- token ratio (prism/native): 0.39x

**FLAGGED** (resolve mismatch, token ratio 0.39x outside [0.67, 1.5])

**Attribution: NON-ADOPTION.** Prism was never called (0 mcp__prism__prism calls) in this cell -- this result is not attributable to prism's engine or context quality, only to the agent not reaching for the tool.

- **native**: resolved=False turns=32 tokens=1632020 wall_s=485.0 cost=$0.6217896
  - tools: {'Bash': 30, 'ToolSearch': 1}
- **prism**: resolved=True turns=14 tokens=634020 wall_s=54.7 cost=$0.2342208
  - tools: {'Bash': 7, 'Grep': 3, 'Read': 1, 'Edit': 2}

> [2026-09-20 22:37:15]    native resolved=False tokens=1632020 | prism resolved=True tokens=634020 prism_calls=0 [FLAGGED]

> [2026-09-20 22:37:15] -- expressjs__express__pr7459 (js) --

## expressjs__express__pr7459 (js)

- native: resolved=True tokens=430328 turns=12 wall_s=49.0
- prism : resolved=True tokens=276520 turns=7 wall_s=23.4 prism_calls=1
- token ratio (prism/native): 0.64x

**FLAGGED** (token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=430328 wall_s=49.0 cost=$0.1812196
  - tools: {'Grep': 2, 'Bash': 5, 'Read': 2, 'Edit': 2}
- **prism**: resolved=True turns=7 tokens=276520 wall_s=23.4 cost=$0.1455054
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 4}

> [2026-09-20 22:38:45]    native resolved=True tokens=430328 | prism resolved=True tokens=276520 prism_calls=1 [FLAGGED]

> [2026-09-20 22:38:45] -- pallets__click__pr3534 (python) --

## pallets__click__pr3534 (python)

- native: resolved=True tokens=496373 turns=13 wall_s=39.9
- prism : resolved=True tokens=432917 turns=10 wall_s=36.3 prism_calls=3
- token ratio (prism/native): 0.87x

> [2026-09-20 22:42:40]    native resolved=True tokens=496373 | prism resolved=True tokens=432917 prism_calls=3

> [2026-09-20 22:42:40] -- FasterXML__jackson-databind__pr6056 (java) --

## FasterXML__jackson-databind__pr6056 (java)

- native: resolved=True tokens=416619 turns=11 wall_s=37.8
- prism : resolved=True tokens=683551 turns=13 wall_s=83.5 prism_calls=4
- token ratio (prism/native): 1.64x

**FLAGGED** (token ratio 1.64x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=416619 wall_s=37.8 cost=$0.1709274
  - tools: {'Grep': 4, 'Read': 1, 'Edit': 1, 'Bash': 4}
- **prism**: resolved=True turns=13 tokens=683551 wall_s=83.5 cost=$0.2993256
  - tools: {'mcp__prism__prism': 4, 'Bash': 5, 'Read': 2, 'Edit': 1}

> [2026-09-20 22:45:32]    native resolved=True tokens=416619 | prism resolved=True tokens=683551 prism_calls=4 [FLAGGED]

> [2026-09-20 22:45:32] -- apache__commons-lang__pr1670 (java) --

## apache__commons-lang__pr1670 (java)

- native: resolved=True tokens=1286657 turns=26 wall_s=517.3
- prism : resolved=False tokens=341070 turns=8 wall_s=363.9 prism_calls=1
- token ratio (prism/native): 0.27x

**FLAGGED** (resolve mismatch, token ratio 0.27x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=26 tokens=1286657 wall_s=517.3 cost=$0.47562820000000006
  - tools: {'Grep': 4, 'Read': 2, 'Edit': 5, 'Bash': 14}
- **prism**: resolved=False turns=8 tokens=341070 wall_s=363.9 cost=$0.1922584
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Edit': 1, 'Bash': 4}

> [2026-09-20 23:00:46]    native resolved=True tokens=1286657 | prism resolved=False tokens=341070 prism_calls=1 [FLAGGED]

> [2026-09-20 23:00:46] -- FasterXML__jackson-databind__pr6039 (java) --

## FasterXML__jackson-databind__pr6039 (java)

- native: resolved=True tokens=3261009 turns=47 wall_s=469.5
- prism : resolved=True tokens=987290 turns=19 wall_s=104.1 prism_calls=3
- token ratio (prism/native): 0.30x

**FLAGGED** (token ratio 0.30x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=47 tokens=3261009 wall_s=469.5 cost=$1.1799996
  - tools: {'Grep': 5, 'Read': 6, 'Bash': 30, 'ToolSearch': 1, 'Edit': 3, 'Write': 1}
- **prism**: resolved=True turns=19 tokens=987290 wall_s=104.1 cost=$0.39570859999999997
  - tools: {'mcp__prism__prism': 3, 'Bash': 13, 'Read': 1, 'Edit': 1}

> [2026-09-20 23:11:13]    native resolved=True tokens=3261009 | prism resolved=True tokens=987290 prism_calls=3 [FLAGGED]

> [2026-09-20 23:11:13] -- apache__commons-lang__pr1699 (java) --

## apache__commons-lang__pr1699 (java)

- native: resolved=True tokens=240308 turns=7 wall_s=18.6
- prism : resolved=False tokens=110583 turns=4 wall_s=7.5 prism_calls=1
- token ratio (prism/native): 0.46x

**FLAGGED** (resolve mismatch, token ratio 0.46x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=7 tokens=240308 wall_s=18.6 cost=$0.0956908
  - tools: {'Grep': 2, 'Read': 1, 'Edit': 2, 'Bash': 1}
- **prism**: resolved=False turns=4 tokens=110583 wall_s=7.5 cost=$0.0652718
  - tools: {'mcp__prism__prism': 1, 'Edit': 2}

> [2026-09-20 23:12:09]    native resolved=True tokens=240308 | prism resolved=False tokens=110583 prism_calls=1 [FLAGGED]

> [2026-09-20 23:12:09] -- FasterXML__jackson-databind__pr6042 (java) --

## FasterXML__jackson-databind__pr6042 (java)

- native: resolved=True tokens=604789 turns=15 wall_s=76.7
- prism : resolved=True tokens=429047 turns=11 wall_s=29.6 prism_calls=1
- token ratio (prism/native): 0.71x

> [2026-09-20 23:15:08]    native resolved=True tokens=604789 | prism resolved=True tokens=429047 prism_calls=1

> [2026-09-20 23:15:08] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=484012 turns=15 wall_s=39.3
- prism : resolved=False tokens=700080 turns=15 wall_s=82.8 prism_calls=6
- token ratio (prism/native): 1.45x

> [2026-09-20 23:20:14]    native resolved=False tokens=484012 | prism resolved=False tokens=700080 prism_calls=6

> [2026-09-20 23:20:14] -- gin-gonic__gin__pr4702 (go) --

## gin-gonic__gin__pr4702 (go)

- native: resolved=True tokens=204021 turns=6 wall_s=14.3
- prism : resolved=True tokens=184069 turns=5 wall_s=15.5 prism_calls=1
- token ratio (prism/native): 0.90x

> [2026-09-20 23:21:49]    native resolved=True tokens=204021 | prism resolved=True tokens=184069 prism_calls=1

> [2026-09-20 23:21:49] -- FasterXML__jackson-databind__pr6047 (java) --

## FasterXML__jackson-databind__pr6047 (java)

- native: resolved=True tokens=351583 turns=9 wall_s=20.1
- prism : resolved=True tokens=242639 turns=6 wall_s=15.4 prism_calls=2
- token ratio (prism/native): 0.69x

> [2026-09-20 23:23:39]    native resolved=True tokens=351583 | prism resolved=True tokens=242639 prism_calls=2

> [2026-09-20 23:23:39] -- pallets__click__pr3482 (python) --

## pallets__click__pr3482 (python)

- native: resolved=True tokens=795140 turns=20 wall_s=76.7
- prism : resolved=True tokens=1109220 turns=20 wall_s=102.8 prism_calls=4
- token ratio (prism/native): 1.39x

> [2026-09-20 23:29:18]    native resolved=True tokens=795140 | prism resolved=True tokens=1109220 prism_calls=4

> [2026-09-20 23:29:18] -- pallets__click__pr3493 (python) --

## pallets__click__pr3493 (python)

- native: resolved=True tokens=315706 turns=9 wall_s=29.8
- prism : resolved=True tokens=393760 turns=10 wall_s=35.8 prism_calls=1
- token ratio (prism/native): 1.25x

> [2026-09-20 23:33:00]    native resolved=True tokens=315706 | prism resolved=True tokens=393760 prism_calls=1

> [2026-09-20 23:33:00] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=True tokens=432286 turns=12 wall_s=28.4
- prism : resolved=False tokens=309766 turns=8 wall_s=20.5 prism_calls=2
- token ratio (prism/native): 0.72x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=432286 wall_s=28.4 cost=$0.1609738
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 1, 'Bash': 6}
- **prism**: resolved=False turns=8 tokens=309766 wall_s=20.5 cost=$0.1296816
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 4}

> [2026-09-20 23:36:25]    native resolved=True tokens=432286 | prism resolved=False tokens=309766 prism_calls=2 [FLAGGED]

> [2026-09-20 23:36:25] -- apache__commons-lang__pr1720 (java) --

## apache__commons-lang__pr1720 (java)

- native: resolved=True tokens=556859 turns=15 wall_s=50.0
- prism : resolved=False tokens=374280 turns=9 wall_s=59.0 prism_calls=4
- token ratio (prism/native): 0.67x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=556859 wall_s=50.0 cost=$0.1998508
  - tools: {'Grep': 4, 'Bash': 8, 'Read': 1, 'Edit': 1}
- **prism**: resolved=False turns=9 tokens=374280 wall_s=59.0 cost=$0.16243080000000001
  - tools: {'mcp__prism__prism': 4, 'Edit': 1, 'Bash': 3}

> [2026-09-20 23:38:47]    native resolved=True tokens=556859 | prism resolved=False tokens=374280 prism_calls=4 [FLAGGED]

> [2026-09-20 23:38:47] -- apache__commons-lang__pr1713 (java) --

## apache__commons-lang__pr1713 (java)

- native: resolved=True tokens=522918 turns=14 wall_s=45.1
- prism : resolved=False tokens=464377 turns=11 wall_s=196.1 prism_calls=2
- token ratio (prism/native): 0.89x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=14 tokens=522918 wall_s=45.1 cost=$0.19192479999999998
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 2, 'Bash': 7}
- **prism**: resolved=False turns=11 tokens=464377 wall_s=196.1 cost=$0.20350700000000002
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 6}

> [2026-09-20 23:43:18]    native resolved=True tokens=522918 | prism resolved=False tokens=464377 prism_calls=2 [FLAGGED]

> [2026-09-20 23:43:18] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=True tokens=1498986 turns=30 wall_s=179.0
- prism : resolved=False tokens=3683322 turns=42 wall_s=417.1 prism_calls=10
- token ratio (prism/native): 2.46x

**FLAGGED** (resolve mismatch, token ratio 2.46x outside [0.67, 1.5])

**Attribution: prism WAS called (10x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=30 tokens=1498986 wall_s=179.0 cost=$0.5486447999999999
  - tools: {'Grep': 8, 'Read': 6, 'Bash': 13, 'Edit': 2}
- **prism**: resolved=False turns=42 tokens=3683322 wall_s=417.1 cost=$1.3474560000000002
  - tools: {'mcp__prism__prism': 10, 'Bash': 19, 'Read': 4, 'Edit': 7, 'Write': 1}

> [2026-09-20 23:54:31]    native resolved=True tokens=1498986 | prism resolved=False tokens=3683322 prism_calls=10 [FLAGGED]

> [2026-09-20 23:54:31] -- FasterXML__jackson-databind__pr6099 (java) --

## FasterXML__jackson-databind__pr6099 (java)

- native: resolved=True tokens=274336 turns=8 wall_s=15.4
- prism : resolved=True tokens=648723 turns=16 wall_s=90.3 prism_calls=5
- token ratio (prism/native): 2.36x

**FLAGGED** (token ratio 2.36x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=8 tokens=274336 wall_s=15.4 cost=$0.1076252
  - tools: {'Grep': 2, 'Read': 2, 'Edit': 2, 'Bash': 1}
- **prism**: resolved=True turns=16 tokens=648723 wall_s=90.3 cost=$0.24005720000000003
  - tools: {'mcp__prism__prism': 5, 'Edit': 2, 'Bash': 8}

> [2026-09-20 23:57:10]    native resolved=True tokens=274336 | prism resolved=True tokens=648723 prism_calls=5 [FLAGGED]

> [2026-09-20 23:57:10] -- gin-gonic__gin__pr4535 (go) --

## gin-gonic__gin__pr4535 (go)

- native: resolved=False tokens=274591 turns=8 wall_s=18.9
- prism : resolved=False tokens=152053 turns=4 wall_s=15.5 prism_calls=1
- token ratio (prism/native): 0.55x

**FLAGGED** (token ratio 0.55x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=8 tokens=274591 wall_s=18.9 cost=$0.1069832
  - tools: {'Grep': 3, 'Bash': 2, 'Read': 1, 'Edit': 1}
- **prism**: resolved=False turns=4 tokens=152053 wall_s=15.5 cost=$0.0785366
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 1}

> [2026-09-20 23:58:50]    native resolved=False tokens=274591 | prism resolved=False tokens=152053 prism_calls=1 [FLAGGED]

> [2026-09-20 23:58:50] -- apache__commons-lang__pr1733 (java) --

## apache__commons-lang__pr1733 (java)

- native: resolved=True tokens=398158 turns=11 wall_s=29.7
- prism : resolved=False tokens=286125 turns=10 wall_s=39.2 prism_calls=2
- token ratio (prism/native): 0.72x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=398158 wall_s=29.7 cost=$0.15017760000000002
  - tools: {'Grep': 3, 'Read': 2, 'Edit': 4, 'Bash': 1}
- **prism**: resolved=False turns=10 tokens=286125 wall_s=39.2 cost=$0.1407586
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 4, 'Bash': 2}

> [2026-09-21 00:00:29]    native resolved=True tokens=398158 | prism resolved=False tokens=286125 prism_calls=2 [FLAGGED]

> [2026-09-21 00:00:29] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=True tokens=890508 turns=20 wall_s=61.8
- prism : resolved=True tokens=1746444 turns=28 wall_s=171.3 prism_calls=5
- token ratio (prism/native): 1.96x

**FLAGGED** (token ratio 1.96x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=20 tokens=890508 wall_s=61.8 cost=$0.3220642
  - tools: {'Grep': 3, 'Read': 4, 'Bash': 10, 'Edit': 2}
- **prism**: resolved=True turns=28 tokens=1746444 wall_s=171.3 cost=$0.6500537999999998
  - tools: {'mcp__prism__prism': 5, 'Read': 2, 'Bash': 15, 'Edit': 4, 'Grep': 1}

> [2026-09-21 00:07:01]    native resolved=True tokens=890508 | prism resolved=True tokens=1746444 prism_calls=5 [FLAGGED]

> [2026-09-21 00:07:01] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=548397 turns=11 wall_s=215.0
- prism : resolved=False tokens=572659 turns=13 wall_s=259.4 prism_calls=2
- token ratio (prism/native): 1.04x

> [2026-09-21 00:15:24]    native resolved=False tokens=548397 | prism resolved=False tokens=572659 prism_calls=2

> [2026-09-21 00:15:24] -- pallets__click__pr3504 (python) --

## pallets__click__pr3504 (python)

- native: resolved=False tokens=2605764 turns=45 wall_s=264.0
- prism : resolved=False tokens=619983 turns=13 wall_s=59.2 prism_calls=2
- token ratio (prism/native): 0.24x

**FLAGGED** (token ratio 0.24x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=45 tokens=2605764 wall_s=264.0 cost=$0.8969182
  - tools: {'Grep': 9, 'Read': 8, 'Bash': 27}
- **prism**: resolved=False turns=13 tokens=619983 wall_s=59.2 cost=$0.2540622
  - tools: {'mcp__prism__prism': 2, 'Bash': 10}

> [2026-09-21 00:22:08]    native resolved=False tokens=2605764 | prism resolved=False tokens=619983 prism_calls=2 [FLAGGED]

> [2026-09-21 00:22:08] -- FasterXML__jackson-databind__pr6061 (java) --

## FasterXML__jackson-databind__pr6061 (java)

- native: resolved=True tokens=560613 turns=15 wall_s=52.8
- prism : resolved=False tokens=958698 turns=22 wall_s=87.0 prism_calls=1
- token ratio (prism/native): 1.71x

**FLAGGED** (resolve mismatch, token ratio 1.71x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=560613 wall_s=52.8 cost=$0.21543720000000002
  - tools: {'Bash': 8, 'Grep': 2, 'Read': 1, 'Edit': 3}
- **prism**: resolved=False turns=22 tokens=958698 wall_s=87.0 cost=$0.34404519999999994
  - tools: {'Bash': 16, 'ToolSearch': 1, 'mcp__prism__prism': 1, 'Read': 2, 'Edit': 1}

> [2026-09-21 00:25:43]    native resolved=True tokens=560613 | prism resolved=False tokens=958698 prism_calls=1 [FLAGGED]

> [2026-09-21 00:25:43] -- apache__commons-lang__pr1591 (java) --

## apache__commons-lang__pr1591 (java)

- native: resolved=True tokens=364555 turns=9 wall_s=71.3
- prism : resolved=False tokens=427915 turns=9 wall_s=246.3 prism_calls=2
- token ratio (prism/native): 1.17x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=9 tokens=364555 wall_s=71.3 cost=$0.1944254
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 1, 'Bash': 3}
- **prism**: resolved=False turns=9 tokens=427915 wall_s=246.3 cost=$0.2673276
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 5}

> [2026-09-21 00:31:32]    native resolved=True tokens=364555 | prism resolved=False tokens=427915 prism_calls=2 [FLAGGED]

> [2026-09-21 00:31:32] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=250118 turns=7 wall_s=42.9
- prism : resolved=False tokens=368448 turns=9 wall_s=51.4 prism_calls=4
- token ratio (prism/native): 1.47x

> [2026-09-21 00:33:36]    native resolved=False tokens=250118 | prism resolved=False tokens=368448 prism_calls=4

> [2026-09-21 00:33:36] -- apache__commons-lang__pr1709 (java) --

## apache__commons-lang__pr1709 (java)

- native: resolved=True tokens=449172 turns=13 wall_s=41.6
- prism : resolved=False tokens=501837 turns=15 wall_s=192.3 prism_calls=8
- token ratio (prism/native): 1.12x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (8x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=13 tokens=449172 wall_s=41.6 cost=$0.1739934
  - tools: {'Grep': 2, 'Read': 4, 'Edit': 3, 'Bash': 3}
- **prism**: resolved=False turns=15 tokens=501837 wall_s=192.3 cost=$0.2146114
  - tools: {'mcp__prism__prism': 8, 'Edit': 3, 'Bash': 3}

> [2026-09-21 00:37:59]    native resolved=True tokens=449172 | prism resolved=False tokens=501837 prism_calls=8 [FLAGGED]

> [2026-09-21 00:37:59] -- FasterXML__jackson-databind__pr6044 (java) --

## FasterXML__jackson-databind__pr6044 (java)

- native: resolved=False tokens=1067075 turns=24 wall_s=155.7
- prism : resolved=False tokens=1292746 turns=22 wall_s=151.0 prism_calls=4
- token ratio (prism/native): 1.21x

> [2026-09-21 00:43:59]    native resolved=False tokens=1067075 | prism resolved=False tokens=1292746 prism_calls=4

> [2026-09-21 00:43:59] -- apache__commons-lang__pr1750 (java) --

## apache__commons-lang__pr1750 (java)

- native: resolved=False tokens=168153 turns=5 wall_s=24.4
- prism : resolved=False tokens=334526 turns=8 wall_s=37.2 prism_calls=1
- token ratio (prism/native): 1.99x

**FLAGGED** (token ratio 1.99x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=5 tokens=168153 wall_s=24.4 cost=$0.0759994
  - tools: {'Grep': 2, 'Bash': 2}
- **prism**: resolved=False turns=8 tokens=334526 wall_s=37.2 cost=$0.1448784
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Bash': 5}

> [2026-09-21 00:45:31]    native resolved=False tokens=168153 | prism resolved=False tokens=334526 prism_calls=1 [FLAGGED]

> [2026-09-21 00:45:31] -- FasterXML__jackson-databind__pr6018 (java) --

## FasterXML__jackson-databind__pr6018 (java)

- native: resolved=False tokens=898535 turns=21 wall_s=141.5
- prism : resolved=False tokens=1094496 turns=18 wall_s=125.3 prism_calls=6
- token ratio (prism/native): 1.22x

> [2026-09-21 00:51:14]    native resolved=False tokens=898535 | prism resolved=False tokens=1094496 prism_calls=6

> [2026-09-21 00:51:14] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=691191 turns=16 wall_s=96.3
- prism : resolved=False tokens=976039 turns=19 wall_s=128.1 prism_calls=2
- token ratio (prism/native): 1.41x

> [2026-09-21 00:57:35]    native resolved=False tokens=691191 | prism resolved=False tokens=976039 prism_calls=2

> [2026-09-21 00:57:35] -- akheron__jansson__pr741 (c) --

## akheron__jansson__pr741 (c)

- native: resolved=True tokens=1531802 turns=34 wall_s=92.1
- prism : resolved=True tokens=1844212 turns=37 wall_s=167.6 prism_calls=4
- token ratio (prism/native): 1.20x

> [2026-09-21 01:02:05]    native resolved=True tokens=1531802 | prism resolved=True tokens=1844212 prism_calls=4

> [2026-09-21 01:02:05] -- pallets__click__pr3473 (python) --

## pallets__click__pr3473 (python)

- native: resolved=False tokens=1242731 turns=28 wall_s=76.6
- prism : resolved=False tokens=1319659 turns=23 wall_s=112.9 prism_calls=6
- token ratio (prism/native): 1.06x

> [2026-09-21 01:07:50]    native resolved=False tokens=1242731 | prism resolved=False tokens=1319659 prism_calls=6

> [2026-09-21 01:07:50] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=True tokens=1334737 turns=26 wall_s=117.3
- prism : resolved=True tokens=1419663 turns=27 wall_s=90.2 prism_calls=1
- token ratio (prism/native): 1.06x

> [2026-09-21 01:11:27]    native resolved=True tokens=1334737 | prism resolved=True tokens=1419663 prism_calls=1

> [2026-09-21 01:11:27] -- FasterXML__jackson-databind__pr6008 (java) --

## FasterXML__jackson-databind__pr6008 (java)

- native: resolved=False tokens=1825315 turns=31 wall_s=270.6
- prism : resolved=True tokens=1304250 turns=22 wall_s=180.6 prism_calls=5
- token ratio (prism/native): 0.71x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=31 tokens=1825315 wall_s=270.6 cost=$0.8467638
  - tools: {'Bash': 8, 'Read': 8, 'Grep': 11, 'Edit': 3}
- **prism**: resolved=True turns=22 tokens=1304250 wall_s=180.6 cost=$0.5924285999999999
  - tools: {'mcp__prism__prism': 5, 'Read': 5, 'Edit': 4, 'Grep': 1, 'Bash': 6}

> [2026-09-21 01:20:15]    native resolved=False tokens=1825315 | prism resolved=True tokens=1304250 prism_calls=5 [FLAGGED]

> [2026-09-21 01:20:15] -- FasterXML__jackson-databind__pr6076 (java) --

## FasterXML__jackson-databind__pr6076 (java)

- native: resolved=False tokens=2121553 turns=33 wall_s=324.4
- prism : resolved=False tokens=4911244 turns=53 wall_s=470.2 prism_calls=7
- token ratio (prism/native): 2.31x

**FLAGGED** (token ratio 2.31x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=33 tokens=2121553 wall_s=324.4 cost=$0.7744378
  - tools: {'Grep': 9, 'Read': 5, 'Bash': 15, 'Write': 1, 'Edit': 2}
- **prism**: resolved=False turns=53 tokens=4911244 wall_s=470.2 cost=$1.7097758000000007
  - tools: {'mcp__prism__prism': 7, 'Read': 10, 'Bash': 25, 'Grep': 1, 'Edit': 8, 'Write': 1}

> [2026-09-21 01:34:24]    native resolved=False tokens=2121553 | prism resolved=False tokens=4911244 prism_calls=7 [FLAGGED]


# SUMMARY

50/50 tasks completed.

- native resolved: 32/50
- prism  resolved: 25/50
- native tokens total: 39906942
- prism  tokens total: 38988712 (0.98x native)
- flagged cells: 31 (1 non-adoption, 30 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- gin-gonic__gin__pr4695
- gin-gonic__gin__pr4698
- Textualize__rich__pr3882
- psf__requests__pr7315
- pallets__click__pr3466
- pallets__click__pr3471
- apache__commons-lang__pr1631
- FasterXML__jackson-databind__pr6030
- FasterXML__jackson-databind__pr6102
- FasterXML__jackson-databind__pr6052
- expressjs__express__pr7459
- FasterXML__jackson-databind__pr6056
- apache__commons-lang__pr1670
- FasterXML__jackson-databind__pr6039
- apache__commons-lang__pr1699
- pallets__click__pr3434
- apache__commons-lang__pr1720
- apache__commons-lang__pr1713
- FasterXML__jackson-databind__pr6019
- FasterXML__jackson-databind__pr6099
- gin-gonic__gin__pr4535
- apache__commons-lang__pr1733
- pallets__click__pr3653
- pallets__click__pr3504
- FasterXML__jackson-databind__pr6061
- apache__commons-lang__pr1591
- apache__commons-lang__pr1709
- apache__commons-lang__pr1750
- FasterXML__jackson-databind__pr6008
- FasterXML__jackson-databind__pr6076

Completed 2026-09-21 01:34:24

> [2026-09-21 01:34:24] DONE: 50/50 tasks, 31 flagged (1 non-adoption, 30 real)
