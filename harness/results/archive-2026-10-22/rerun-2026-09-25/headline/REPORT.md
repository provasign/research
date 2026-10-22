# Overnight run: native vs resident prism_init

Started 2026-09-25 07:56:43. 50 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-25 07:56:43] starting: 50 tasks, 0 already done

> [2026-09-25 07:56:43] -- gin-gonic__gin__pr4695 (go) --

## gin-gonic__gin__pr4695 (go)

- native: resolved=True tokens=201592 turns=6 wall_s=21.5
- prism : resolved=True tokens=224573 turns=6 wall_s=20.4 prism_calls=2
- token ratio (prism/native): 1.11x

> [2026-09-25 07:57:49]    native resolved=True tokens=201592 | prism resolved=True tokens=224573 prism_calls=2

> [2026-09-25 07:57:49] -- gin-gonic__gin__pr4698 (go) --

## gin-gonic__gin__pr4698 (go)

- native: resolved=True tokens=219652 turns=6 wall_s=26.3
- prism : resolved=True tokens=228079 turns=6 wall_s=41.3 prism_calls=2
- token ratio (prism/native): 1.04x

> [2026-09-25 07:59:17]    native resolved=True tokens=219652 | prism resolved=True tokens=228079 prism_calls=2

> [2026-09-25 07:59:17] -- Textualize__rich__pr3882 (python) --

## Textualize__rich__pr3882 (python)

- native: resolved=True tokens=312672 turns=9 wall_s=24.9
- prism : resolved=True tokens=352829 turns=9 wall_s=25.0 prism_calls=1
- token ratio (prism/native): 1.13x

> [2026-09-25 08:00:24]    native resolved=True tokens=312672 | prism resolved=True tokens=352829 prism_calls=1

> [2026-09-25 08:00:24] -- psf__requests__pr7315 (python) --

## psf__requests__pr7315 (python)

- native: resolved=False tokens=1302436 turns=29 wall_s=227.7
- prism : resolved=False tokens=2615092 turns=46 wall_s=434.2 prism_calls=4
- token ratio (prism/native): 2.01x

**FLAGGED** (token ratio 2.01x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=29 tokens=1302436 wall_s=227.7 cost=$0.5001946000000002
  - tools: {'Grep': 4, 'Bash': 22, 'Read': 1, 'Edit': 1}
- **prism**: resolved=False turns=46 tokens=2615092 wall_s=434.2 cost=$0.9854930000000001
  - tools: {'mcp__prism__prism': 4, 'Glob': 1, 'Bash': 29, 'Grep': 2, 'Read': 7, 'Edit': 1}

> [2026-09-25 08:39:27]    native resolved=False tokens=1302436 | prism resolved=False tokens=2615092 prism_calls=4 [FLAGGED]

> [2026-09-25 08:39:27] -- gin-gonic__gin__pr4472 (go) --

## gin-gonic__gin__pr4472 (go)

- native: resolved=True tokens=281928 turns=8 wall_s=25.4
- prism : resolved=True tokens=352059 turns=9 wall_s=21.7 prism_calls=3
- token ratio (prism/native): 1.25x

> [2026-09-25 08:40:35]    native resolved=True tokens=281928 | prism resolved=True tokens=352059 prism_calls=3

> [2026-09-25 08:40:35] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=689198 turns=18 wall_s=69.4
- prism : resolved=False tokens=589521 turns=13 wall_s=46.2 prism_calls=3
- token ratio (prism/native): 0.86x

> [2026-09-25 08:42:42]    native resolved=False tokens=689198 | prism resolved=False tokens=589521 prism_calls=3

> [2026-09-25 08:42:42] -- gin-gonic__gin__pr4819 (go) --

## gin-gonic__gin__pr4819 (go)

- native: resolved=True tokens=215438 turns=6 wall_s=25.9
- prism : resolved=True tokens=338224 turns=8 wall_s=38.5 prism_calls=3
- token ratio (prism/native): 1.57x

**FLAGGED** (token ratio 1.57x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=6 tokens=215438 wall_s=25.9 cost=$0.12400739999999999
  - tools: {'Grep': 1, 'Read': 1, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=True turns=8 tokens=338224 wall_s=38.5 cost=$0.1776238
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-25 08:44:27]    native resolved=True tokens=215438 | prism resolved=True tokens=338224 prism_calls=3 [FLAGGED]

> [2026-09-25 08:44:27] -- pallets__click__pr3466 (python) --

## pallets__click__pr3466 (python)

- native: resolved=True tokens=1692219 turns=33 wall_s=183.0
- prism : resolved=False tokens=1780681 turns=30 wall_s=209.5 prism_calls=7
- token ratio (prism/native): 1.05x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=33 tokens=1692219 wall_s=183.0 cost=$0.651504
  - tools: {'Grep': 10, 'Glob': 1, 'Read': 5, 'Bash': 11, 'Edit': 5}
- **prism**: resolved=False turns=30 tokens=1780681 wall_s=209.5 cost=$0.6902957999999999
  - tools: {'mcp__prism__prism': 7, 'Grep': 5, 'Read': 5, 'Bash': 9, 'Edit': 3}

> [2026-09-25 08:51:27]    native resolved=True tokens=1692219 | prism resolved=False tokens=1780681 prism_calls=7 [FLAGGED]

> [2026-09-25 08:51:27] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=522793 turns=14 wall_s=63.4
- prism : resolved=False tokens=849576 turns=18 wall_s=87.6 prism_calls=2
- token ratio (prism/native): 1.63x

**FLAGGED** (token ratio 1.63x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=14 tokens=522793 wall_s=63.4 cost=$0.218076
  - tools: {'Grep': 1, 'Read': 2, 'Edit': 2, 'Bash': 8}
- **prism**: resolved=False turns=18 tokens=849576 wall_s=87.6 cost=$0.3355814
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 2, 'Bash': 12}

> [2026-09-25 08:54:32]    native resolved=False tokens=522793 | prism resolved=False tokens=849576 prism_calls=2 [FLAGGED]

> [2026-09-25 08:54:32] -- FasterXML__jackson-databind__pr6012 (java) --

## FasterXML__jackson-databind__pr6012 (java)

- native: resolved=True tokens=477401 turns=12 wall_s=87.3
- prism : resolved=True tokens=222697 turns=6 wall_s=56.7 prism_calls=3
- token ratio (prism/native): 0.47x

**FLAGGED** (token ratio 0.47x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=477401 wall_s=87.3 cost=$0.23872799999999997
  - tools: {'Grep': 5, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=6 tokens=222697 wall_s=56.7 cost=$0.1155756
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 1}

> [2026-09-25 08:58:19]    native resolved=True tokens=477401 | prism resolved=True tokens=222697 prism_calls=3 [FLAGGED]

> [2026-09-25 08:58:19] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=132438 turns=4 wall_s=16.0
- prism : resolved=True tokens=262954 turns=7 wall_s=38.6 prism_calls=2
- token ratio (prism/native): 1.99x

**FLAGGED** (token ratio 1.99x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=4 tokens=132438 wall_s=16.0 cost=$0.0828856
  - tools: {'Grep': 1, 'Edit': 1, 'Bash': 1}
- **prism**: resolved=True turns=7 tokens=262954 wall_s=38.6 cost=$0.1338974
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-25 08:59:51]    native resolved=True tokens=132438 | prism resolved=True tokens=262954 prism_calls=2 [FLAGGED]

> [2026-09-25 08:59:51] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=983195 turns=22 wall_s=87.3
- prism : resolved=False tokens=714680 turns=13 wall_s=83.4 prism_calls=7
- token ratio (prism/native): 0.73x

> [2026-09-25 09:04:10]    native resolved=False tokens=983195 | prism resolved=False tokens=714680 prism_calls=7

> [2026-09-25 09:04:10] -- FasterXML__jackson-databind__pr6102 (java) --

## FasterXML__jackson-databind__pr6102 (java)

- native: resolved=True tokens=958409 turns=21 wall_s=99.5
- prism : resolved=True tokens=483118 turns=11 wall_s=52.3 prism_calls=1
- token ratio (prism/native): 0.50x

**FLAGGED** (token ratio 0.50x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=21 tokens=958409 wall_s=99.5 cost=$0.3818346
  - tools: {'Grep': 2, 'Bash': 16, 'Read': 1, 'Edit': 1}
- **prism**: resolved=True turns=11 tokens=483118 wall_s=52.3 cost=$0.2160622
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 8}

> [2026-09-25 09:08:07]    native resolved=True tokens=958409 | prism resolved=True tokens=483118 prism_calls=1 [FLAGGED]

> [2026-09-25 09:08:07] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=436732 turns=11 wall_s=54.6
- prism : resolved=False tokens=982106 turns=19 wall_s=96.3 prism_calls=4
- token ratio (prism/native): 2.25x

**FLAGGED** (token ratio 2.25x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=11 tokens=436732 wall_s=54.6 cost=$0.21610200000000004
  - tools: {'Grep': 2, 'Read': 3, 'Bash': 5}
- **prism**: resolved=False turns=19 tokens=982106 wall_s=96.3 cost=$0.4021776
  - tools: {'mcp__prism__prism': 4, 'Bash': 13, 'Read': 1}

> [2026-09-25 09:11:37]    native resolved=False tokens=436732 | prism resolved=False tokens=982106 prism_calls=4 [FLAGGED]

> [2026-09-25 09:11:37] -- FasterXML__jackson-databind__pr6105 (java) --

## FasterXML__jackson-databind__pr6105 (java)

- native: resolved=True tokens=741841 turns=18 wall_s=130.8
- prism : resolved=True tokens=987435 turns=20 wall_s=154.9 prism_calls=1
- token ratio (prism/native): 1.33x

> [2026-09-25 09:21:11]    native resolved=True tokens=741841 | prism resolved=True tokens=987435 prism_calls=1

> [2026-09-25 09:21:11] -- expressjs__express__pr7459 (js) --

## expressjs__express__pr7459 (js)

- native: resolved=True tokens=360133 turns=10 wall_s=39.2
- prism : resolved=True tokens=290823 turns=7 wall_s=39.3 prism_calls=1
- token ratio (prism/native): 0.81x

> [2026-09-25 09:22:52]    native resolved=True tokens=360133 | prism resolved=True tokens=290823 prism_calls=1

> [2026-09-25 09:22:52] -- pallets__click__pr3534 (python) --

## pallets__click__pr3534 (python)

- native: resolved=True tokens=775593 turns=19 wall_s=65.0
- prism : resolved=False tokens=567840 turns=13 wall_s=63.4 prism_calls=3
- token ratio (prism/native): 0.73x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=19 tokens=775593 wall_s=65.0 cost=$0.30340280000000003
  - tools: {'Grep': 4, 'Read': 2, 'Bash': 11, 'Edit': 1}
- **prism**: resolved=False turns=13 tokens=567840 wall_s=63.4 cost=$0.2514348
  - tools: {'mcp__prism__prism': 3, 'Edit': 2, 'Bash': 7}

> [2026-09-25 09:25:35]    native resolved=True tokens=775593 | prism resolved=False tokens=567840 prism_calls=3 [FLAGGED]

> [2026-09-25 09:25:35] -- FasterXML__jackson-databind__pr6056 (java) --

## FasterXML__jackson-databind__pr6056 (java)

- native: resolved=True tokens=967727 turns=23 wall_s=97.4
- prism : resolved=False tokens=None turns=None wall_s=None prism_calls=0

**FLAGGED** (resolve mismatch)

**Attribution: NON-ADOPTION.** Prism was never called (0 mcp__prism__prism calls) in this cell -- this result is not attributable to prism's engine or context quality, only to the agent not reaching for the tool.

- **native**: resolved=True turns=23 tokens=967727 wall_s=97.4 cost=$0.3526952
  - tools: {'Bash': 17, 'Read': 3, 'Edit': 1, 'Write': 1}
- **prism**: resolved=False turns=None tokens=None wall_s=None cost=$None
  - tools: None
  - error: TimeoutExpired: Command '['claude', '-p', '\n\nISSUE:\n`@JsonView` by-passed for `@JsonUnwrapped` Field/Setter properties [CVE-2026-59889]\n\nIssue similar to #5971, but for "regular", not Creator-based, properties (that is, Field / Setter method).\n\nFix the SOURCE code in this repository so the issue is resolved 

> [2026-09-25 09:58:01]    native resolved=True tokens=967727 | prism resolved=False tokens=None prism_calls=0 [FLAGGED]

> [2026-09-25 09:58:01] -- apache__commons-lang__pr1670 (java) --

## apache__commons-lang__pr1670 (java)

- native: resolved=True tokens=603344 turns=14 wall_s=375.8
- prism : resolved=True tokens=522943 turns=11 wall_s=390.2 prism_calls=1
- token ratio (prism/native): 0.87x

> [2026-09-25 10:11:30]    native resolved=True tokens=603344 | prism resolved=True tokens=522943 prism_calls=1

> [2026-09-25 10:11:30] -- FasterXML__jackson-databind__pr6039 (java) --

## FasterXML__jackson-databind__pr6039 (java)

- native: resolved=True tokens=1197607 turns=26 wall_s=394.2
- prism : resolved=True tokens=1049237 turns=21 wall_s=261.9 prism_calls=7
- token ratio (prism/native): 0.88x

> [2026-09-25 10:23:28]    native resolved=True tokens=1197607 | prism resolved=True tokens=1049237 prism_calls=7

> [2026-09-25 10:23:28] -- apache__commons-lang__pr1699 (java) --

## apache__commons-lang__pr1699 (java)

- native: resolved=True tokens=172042 turns=7 wall_s=26.8
- prism : resolved=True tokens=300500 turns=8 wall_s=32.7 prism_calls=1
- token ratio (prism/native): 1.75x

**FLAGGED** (token ratio 1.75x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=7 tokens=172042 wall_s=26.8 cost=$0.1047786
  - tools: {'Grep': 2, 'Edit': 2, 'Bash': 2}
- **prism**: resolved=True turns=8 tokens=300500 wall_s=32.7 cost=$0.1442418
  - tools: {'mcp__prism__prism': 1, 'Edit': 2, 'Bash': 4}

> [2026-09-25 10:25:06]    native resolved=True tokens=172042 | prism resolved=True tokens=300500 prism_calls=1 [FLAGGED]

> [2026-09-25 10:25:06] -- FasterXML__jackson-databind__pr6042 (java) --

## FasterXML__jackson-databind__pr6042 (java)

- native: resolved=False tokens=4044938 turns=58 wall_s=348.4
- prism : resolved=True tokens=4305487 turns=49 wall_s=447.6 prism_calls=3
- token ratio (prism/native): 1.06x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=58 tokens=4044938 wall_s=348.4 cost=$1.4052373999999996
  - tools: {'Bash': 31, 'Grep': 11, 'Read': 8, 'Edit': 4, 'Write': 2, 'ScheduleWakeup': 1}
- **prism**: resolved=True turns=49 tokens=4305487 wall_s=447.6 cost=$1.5391362000000004
  - tools: {'mcp__prism__prism': 3, 'Read': 9, 'Grep': 3, 'Edit': 5, 'Bash': 28}

> [2026-09-25 10:39:49]    native resolved=False tokens=4044938 | prism resolved=True tokens=4305487 prism_calls=3 [FLAGGED]

> [2026-09-25 10:39:49] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=480521 turns=13 wall_s=35.1
- prism : resolved=False tokens=527488 turns=11 wall_s=38.7 prism_calls=4
- token ratio (prism/native): 1.10x

> [2026-09-25 10:41:39]    native resolved=False tokens=480521 | prism resolved=False tokens=527488 prism_calls=4

> [2026-09-25 10:41:39] -- gin-gonic__gin__pr4702 (go) --

## gin-gonic__gin__pr4702 (go)

- native: resolved=True tokens=241097 turns=7 wall_s=18.4
- prism : resolved=False tokens=187155 turns=5 wall_s=16.0 prism_calls=1
- token ratio (prism/native): 0.78x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=7 tokens=241097 wall_s=18.4 cost=$0.120615
  - tools: {'Grep': 2, 'Read': 1, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=False turns=5 tokens=187155 wall_s=16.0 cost=$0.10978480000000002
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-25 10:42:40]    native resolved=True tokens=241097 | prism resolved=False tokens=187155 prism_calls=1 [FLAGGED]

> [2026-09-25 10:42:40] -- FasterXML__jackson-databind__pr6047 (java) --

## FasterXML__jackson-databind__pr6047 (java)

- native: resolved=True tokens=874254 turns=20 wall_s=136.0
- prism : resolved=True tokens=764762 turns=16 wall_s=159.7 prism_calls=2
- token ratio (prism/native): 0.87x

> [2026-09-25 10:49:02]    native resolved=True tokens=874254 | prism resolved=True tokens=764762 prism_calls=2

> [2026-09-25 10:49:02] -- pallets__click__pr3482 (python) --

## pallets__click__pr3482 (python)

- native: resolved=True tokens=573339 turns=17 wall_s=56.5
- prism : resolved=True tokens=759841 turns=16 wall_s=77.4 prism_calls=3
- token ratio (prism/native): 1.33x

> [2026-09-25 10:51:49]    native resolved=True tokens=573339 | prism resolved=True tokens=759841 prism_calls=3

> [2026-09-25 10:51:49] -- pallets__click__pr3493 (python) --

## pallets__click__pr3493 (python)

- native: resolved=True tokens=392974 turns=11 wall_s=32.8
- prism : resolved=True tokens=341131 turns=9 wall_s=21.8 prism_calls=2
- token ratio (prism/native): 0.87x

> [2026-09-25 10:53:14]    native resolved=True tokens=392974 | prism resolved=True tokens=341131 prism_calls=2

> [2026-09-25 10:53:14] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=True tokens=634867 turns=17 wall_s=47.6
- prism : resolved=False tokens=570993 turns=14 wall_s=42.5 prism_calls=2
- token ratio (prism/native): 0.90x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=17 tokens=634867 wall_s=47.6 cost=$0.24480139999999997
  - tools: {'Grep': 3, 'Read': 2, 'Edit': 2, 'Bash': 9}
- **prism**: resolved=False turns=14 tokens=570993 wall_s=42.5 cost=$0.22575040000000005
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 10}

> [2026-09-25 10:55:15]    native resolved=True tokens=634867 | prism resolved=False tokens=570993 prism_calls=2 [FLAGGED]

> [2026-09-25 10:55:15] -- apache__commons-lang__pr1720 (java) --

## apache__commons-lang__pr1720 (java)

- native: resolved=True tokens=367967 turns=10 wall_s=50.5
- prism : resolved=True tokens=1429391 turns=27 wall_s=270.0 prism_calls=5
- token ratio (prism/native): 3.88x

**FLAGGED** (token ratio 3.88x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=10 tokens=367967 wall_s=50.5 cost=$0.17794639999999998
  - tools: {'Grep': 3, 'Read': 2, 'Edit': 1, 'Bash': 3}
- **prism**: resolved=True turns=27 tokens=1429391 wall_s=270.0 cost=$0.5519894000000002
  - tools: {'mcp__prism__prism': 5, 'Bash': 16, 'Read': 3, 'Edit': 1, 'ScheduleWakeup': 1}

> [2026-09-25 11:01:19]    native resolved=True tokens=367967 | prism resolved=True tokens=1429391 prism_calls=5 [FLAGGED]

> [2026-09-25 11:01:19] -- apache__commons-lang__pr1713 (java) --

## apache__commons-lang__pr1713 (java)

- native: resolved=True tokens=475107 turns=13 wall_s=65.0
- prism : resolved=False tokens=313510 turns=8 wall_s=37.7 prism_calls=1
- token ratio (prism/native): 0.66x

**FLAGGED** (resolve mismatch, token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=13 tokens=475107 wall_s=65.0 cost=$0.20191760000000003
  - tools: {'Grep': 3, 'Read': 2, 'Edit': 2, 'Bash': 5}
- **prism**: resolved=False turns=8 tokens=313510 wall_s=37.7 cost=$0.155084
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Edit': 1, 'Bash': 4}

> [2026-09-25 11:03:41]    native resolved=True tokens=475107 | prism resolved=False tokens=313510 prism_calls=1 [FLAGGED]

> [2026-09-25 11:03:41] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=True tokens=8949920 turns=96 wall_s=984.4
- prism : resolved=True tokens=8506844 turns=84 wall_s=665.3 prism_calls=13
- token ratio (prism/native): 0.95x

> [2026-09-25 11:32:41]    native resolved=True tokens=8949920 | prism resolved=True tokens=8506844 prism_calls=13

> [2026-09-25 11:32:41] -- FasterXML__jackson-databind__pr6099 (java) --

> [2026-09-25 13:35:25] starting: 50 tasks, 31 already done

> [2026-09-25 13:35:25] -- FasterXML__jackson-databind__pr6099 (java) --

> [2026-09-25 21:59:34] starting: 50 tasks, 31 already done

> [2026-09-25 21:59:34] -- FasterXML__jackson-databind__pr6099 (java) --
