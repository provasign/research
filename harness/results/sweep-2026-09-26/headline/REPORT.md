# Overnight run: native vs resident prism_init

Started 2026-09-26 04:04:47. 50 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-26 04:04:47] starting: 50 tasks, 0 already done

> [2026-09-26 04:04:47] -- gin-gonic__gin__pr4695 (go) --

## gin-gonic__gin__pr4695 (go)

- native: resolved=True tokens=310860 turns=9 wall_s=31.2
- prism : resolved=True tokens=223043 turns=6 wall_s=19.6 prism_calls=2
- token ratio (prism/native): 0.72x

> [2026-09-26 04:06:04]    native resolved=True tokens=310860 | prism resolved=True tokens=223043 prism_calls=2

> [2026-09-26 04:06:04] -- gin-gonic__gin__pr4698 (go) --

## gin-gonic__gin__pr4698 (go)

- native: resolved=True tokens=178185 turns=5 wall_s=28.5
- prism : resolved=True tokens=267254 turns=7 wall_s=28.0 prism_calls=3
- token ratio (prism/native): 1.50x

> [2026-09-26 04:07:23]    native resolved=True tokens=178185 | prism resolved=True tokens=267254 prism_calls=3

> [2026-09-26 04:07:23] -- Textualize__rich__pr3882 (python) --

## Textualize__rich__pr3882 (python)

- native: resolved=True tokens=624791 turns=17 wall_s=59.7
- prism : resolved=True tokens=295291 turns=8 wall_s=36.1 prism_calls=1
- token ratio (prism/native): 0.47x

**FLAGGED** (token ratio 0.47x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=17 tokens=624791 wall_s=59.7 cost=$0.2731108
  - tools: {'Grep': 3, 'Edit': 1, 'Bash': 12}
- **prism**: resolved=True turns=8 tokens=295291 wall_s=36.1 cost=$0.1318212
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 5}

> [2026-09-26 04:09:13]    native resolved=True tokens=624791 | prism resolved=True tokens=295291 prism_calls=1 [FLAGGED]

> [2026-09-26 04:09:13] -- psf__requests__pr7315 (python) --

## psf__requests__pr7315 (python)

- native: resolved=False tokens=1792147 turns=38 wall_s=291.7
- prism : resolved=False tokens=1422477 turns=23 wall_s=261.3 prism_calls=5
- token ratio (prism/native): 0.79x

> [2026-09-26 04:18:45]    native resolved=False tokens=1792147 | prism resolved=False tokens=1422477 prism_calls=5

> [2026-09-26 04:18:45] -- gin-gonic__gin__pr4472 (go) --

## gin-gonic__gin__pr4472 (go)

- native: resolved=True tokens=281451 turns=8 wall_s=21.4
- prism : resolved=True tokens=232828 turns=6 wall_s=28.9 prism_calls=2
- token ratio (prism/native): 0.83x

> [2026-09-26 04:19:58]    native resolved=True tokens=281451 | prism resolved=True tokens=232828 prism_calls=2

> [2026-09-26 04:19:58] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=695473 turns=18 wall_s=74.8
- prism : resolved=False tokens=616582 turns=13 wall_s=68.2 prism_calls=3
- token ratio (prism/native): 0.89x

> [2026-09-26 04:22:32]    native resolved=False tokens=695473 | prism resolved=False tokens=616582 prism_calls=3

> [2026-09-26 04:22:32] -- gin-gonic__gin__pr4819 (go) --

## gin-gonic__gin__pr4819 (go)

- native: resolved=True tokens=329771 turns=9 wall_s=31.5
- prism : resolved=True tokens=381492 turns=9 wall_s=37.8 prism_calls=1
- token ratio (prism/native): 1.16x

> [2026-09-26 04:24:09]    native resolved=True tokens=329771 | prism resolved=True tokens=381492 prism_calls=1

> [2026-09-26 04:24:09] -- pallets__click__pr3466 (python) --

## pallets__click__pr3466 (python)

- native: resolved=False tokens=1756029 turns=38 wall_s=144.1
- prism : resolved=True tokens=1548883 turns=29 wall_s=145.5 prism_calls=4
- token ratio (prism/native): 0.88x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=38 tokens=1756029 wall_s=144.1 cost=$0.6075823999999999
  - tools: {'Grep': 6, 'Bash': 25, 'Read': 4, 'Edit': 2}
- **prism**: resolved=True turns=29 tokens=1548883 wall_s=145.5 cost=$0.5797578000000002
  - tools: {'mcp__prism__prism': 4, 'Bash': 19, 'ToolSearch': 2, 'WebSearch': 1, 'Read': 1, 'Edit': 1}

> [2026-09-26 04:29:25]    native resolved=False tokens=1756029 | prism resolved=True tokens=1548883 prism_calls=4 [FLAGGED]

> [2026-09-26 04:29:25] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=481986 turns=13 wall_s=49.0
- prism : resolved=False tokens=696326 turns=15 wall_s=82.7 prism_calls=2
- token ratio (prism/native): 1.44x

> [2026-09-26 04:32:02]    native resolved=False tokens=481986 | prism resolved=False tokens=696326 prism_calls=2

> [2026-09-26 04:32:02] -- FasterXML__jackson-databind__pr6012 (java) --

## FasterXML__jackson-databind__pr6012 (java)

- native: resolved=True tokens=297052 turns=8 wall_s=38.7
- prism : resolved=True tokens=336892 turns=8 wall_s=78.8 prism_calls=2
- token ratio (prism/native): 1.13x

> [2026-09-26 04:35:22]    native resolved=True tokens=297052 | prism resolved=True tokens=336892 prism_calls=2

> [2026-09-26 04:35:22] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=132456 turns=4 wall_s=21.8
- prism : resolved=True tokens=144786 turns=4 wall_s=22.5 prism_calls=1
- token ratio (prism/native): 1.09x

> [2026-09-26 04:36:43]    native resolved=True tokens=132456 | prism resolved=True tokens=144786 prism_calls=1

> [2026-09-26 04:36:43] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=748083 turns=19 wall_s=85.1
- prism : resolved=False tokens=543468 turns=11 wall_s=58.2 prism_calls=5
- token ratio (prism/native): 0.73x

> [2026-09-26 04:40:32]    native resolved=False tokens=748083 | prism resolved=False tokens=543468 prism_calls=5

> [2026-09-26 04:40:32] -- FasterXML__jackson-databind__pr6102 (java) --

## FasterXML__jackson-databind__pr6102 (java)

- native: resolved=True tokens=670714 turns=15 wall_s=113.5
- prism : resolved=True tokens=560636 turns=12 wall_s=88.3 prism_calls=2
- token ratio (prism/native): 0.84x

> [2026-09-26 04:45:20]    native resolved=True tokens=670714 | prism resolved=True tokens=560636 prism_calls=2

> [2026-09-26 04:45:20] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=401950 turns=10 wall_s=100.3
- prism : resolved=False tokens=643883 turns=14 wall_s=101.9 prism_calls=4
- token ratio (prism/native): 1.60x

**FLAGGED** (token ratio 1.60x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=10 tokens=401950 wall_s=100.3 cost=$0.235197
  - tools: {'Grep': 1, 'Read': 3, 'Bash': 5}
- **prism**: resolved=False turns=14 tokens=643883 wall_s=101.9 cost=$0.28726199999999996
  - tools: {'mcp__prism__prism': 4, 'Read': 2, 'Bash': 7}

> [2026-09-26 04:49:41]    native resolved=False tokens=401950 | prism resolved=False tokens=643883 prism_calls=4 [FLAGGED]

> [2026-09-26 04:49:41] -- FasterXML__jackson-databind__pr6105 (java) --

## FasterXML__jackson-databind__pr6105 (java)

- native: resolved=True tokens=446670 turns=10 wall_s=83.3
- prism : resolved=True tokens=619365 turns=12 wall_s=147.1 prism_calls=1
- token ratio (prism/native): 1.39x

> [2026-09-26 04:58:18]    native resolved=True tokens=446670 | prism resolved=True tokens=619365 prism_calls=1

> [2026-09-26 04:58:18] -- expressjs__express__pr7459 (js) --

## expressjs__express__pr7459 (js)

- native: resolved=True tokens=337684 turns=10 wall_s=82.2
- prism : resolved=True tokens=341819 turns=8 wall_s=68.6 prism_calls=1
- token ratio (prism/native): 1.01x

> [2026-09-26 05:01:09]    native resolved=True tokens=337684 | prism resolved=True tokens=341819 prism_calls=1

> [2026-09-26 05:01:09] -- pallets__click__pr3534 (python) --

## pallets__click__pr3534 (python)

- native: resolved=True tokens=407773 turns=11 wall_s=49.9
- prism : resolved=True tokens=507060 turns=12 wall_s=65.0 prism_calls=3
- token ratio (prism/native): 1.24x

> [2026-09-26 05:03:30]    native resolved=True tokens=407773 | prism resolved=True tokens=507060 prism_calls=3

> [2026-09-26 05:03:30] -- FasterXML__jackson-databind__pr6056 (java) --

## FasterXML__jackson-databind__pr6056 (java)

- native: resolved=True tokens=2231547 turns=43 wall_s=246.2
- prism : resolved=True tokens=2298727 turns=31 wall_s=181.3 prism_calls=5
- token ratio (prism/native): 1.03x

> [2026-09-26 05:11:38]    native resolved=True tokens=2231547 | prism resolved=True tokens=2298727 prism_calls=5

> [2026-09-26 05:11:38] -- apache__commons-lang__pr1670 (java) --

## apache__commons-lang__pr1670 (java)

- native: resolved=True tokens=555568 turns=13 wall_s=128.0
- prism : resolved=True tokens=365296 turns=9 wall_s=87.1 prism_calls=2
- token ratio (prism/native): 0.66x

**FLAGGED** (token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=13 tokens=555568 wall_s=128.0 cost=$0.3039978
  - tools: {'Grep': 3, 'Read': 4, 'Edit': 2, 'Bash': 3}
- **prism**: resolved=True turns=9 tokens=365296 wall_s=87.1 cost=$0.195269
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 4}

> [2026-09-26 05:15:52]    native resolved=True tokens=555568 | prism resolved=True tokens=365296 prism_calls=2 [FLAGGED]

> [2026-09-26 05:15:52] -- FasterXML__jackson-databind__pr6039 (java) --

## FasterXML__jackson-databind__pr6039 (java)

- native: resolved=False tokens=854745 turns=20 wall_s=114.4
- prism : resolved=True tokens=501644 turns=10 wall_s=161.8 prism_calls=2
- token ratio (prism/native): 0.59x

**FLAGGED** (resolve mismatch, token ratio 0.59x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=20 tokens=854745 wall_s=114.4 cost=$0.3486812
  - tools: {'Grep': 7, 'Read': 3, 'Edit': 2, 'Bash': 7}
- **prism**: resolved=True turns=10 tokens=501644 wall_s=161.8 cost=$0.2976858
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 5}

> [2026-09-26 05:21:29]    native resolved=False tokens=854745 | prism resolved=True tokens=501644 prism_calls=2 [FLAGGED]

> [2026-09-26 05:21:29] -- apache__commons-lang__pr1699 (java) --

## apache__commons-lang__pr1699 (java)

- native: resolved=True tokens=245966 turns=10 wall_s=36.2
- prism : resolved=True tokens=260014 turns=7 wall_s=32.4 prism_calls=1
- token ratio (prism/native): 1.06x

> [2026-09-26 05:23:19]    native resolved=True tokens=245966 | prism resolved=True tokens=260014 prism_calls=1

> [2026-09-26 05:23:19] -- FasterXML__jackson-databind__pr6042 (java) --

## FasterXML__jackson-databind__pr6042 (java)

- native: resolved=True tokens=1359364 turns=28 wall_s=131.6
- prism : resolved=True tokens=1391614 turns=25 wall_s=339.4 prism_calls=9
- token ratio (prism/native): 1.02x

> [2026-09-26 05:32:35]    native resolved=True tokens=1359364 | prism resolved=True tokens=1391614 prism_calls=9

> [2026-09-26 05:32:35] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=431868 turns=12 wall_s=124.0
- prism : resolved=False tokens=547751 turns=11 wall_s=42.5 prism_calls=5
- token ratio (prism/native): 1.27x

> [2026-09-26 05:35:50]    native resolved=False tokens=431868 | prism resolved=False tokens=547751 prism_calls=5

> [2026-09-26 05:35:50] -- gin-gonic__gin__pr4702 (go) --

## gin-gonic__gin__pr4702 (go)

- native: resolved=True tokens=390942 turns=11 wall_s=40.1
- prism : resolved=False tokens=264331 turns=7 wall_s=27.4 prism_calls=1
- token ratio (prism/native): 0.68x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=390942 wall_s=40.1 cost=$0.17184200000000002
  - tools: {'Grep': 4, 'Read': 2, 'Edit': 1, 'Bash': 3}
- **prism**: resolved=False turns=7 tokens=264331 wall_s=27.4 cost=$0.12895959999999998
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 4}

> [2026-09-26 05:37:21]    native resolved=True tokens=390942 | prism resolved=False tokens=264331 prism_calls=1 [FLAGGED]

> [2026-09-26 05:37:21] -- FasterXML__jackson-databind__pr6047 (java) --

## FasterXML__jackson-databind__pr6047 (java)

- native: resolved=True tokens=1053396 turns=24 wall_s=125.8
- prism : resolved=True tokens=1147704 turns=22 wall_s=192.8 prism_calls=5
- token ratio (prism/native): 1.09x

> [2026-09-26 05:44:05]    native resolved=True tokens=1053396 | prism resolved=True tokens=1147704 prism_calls=5

> [2026-09-26 05:44:05] -- pallets__click__pr3482 (python) --

## pallets__click__pr3482 (python)

- native: resolved=True tokens=608798 turns=15 wall_s=60.7
- prism : resolved=True tokens=435045 turns=10 wall_s=56.0 prism_calls=3
- token ratio (prism/native): 0.71x

> [2026-09-26 05:46:28]    native resolved=True tokens=608798 | prism resolved=True tokens=435045 prism_calls=3

> [2026-09-26 05:46:28] -- pallets__click__pr3493 (python) --

## pallets__click__pr3493 (python)

- native: resolved=True tokens=502270 turns=14 wall_s=51.6
- prism : resolved=True tokens=466537 turns=12 wall_s=50.6 prism_calls=1
- token ratio (prism/native): 0.93x

> [2026-09-26 05:48:35]    native resolved=True tokens=502270 | prism resolved=True tokens=466537 prism_calls=1

> [2026-09-26 05:48:35] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=True tokens=468691 turns=13 wall_s=97.2
- prism : resolved=False tokens=348213 turns=9 wall_s=35.1 prism_calls=2
- token ratio (prism/native): 0.74x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=13 tokens=468691 wall_s=97.2 cost=$0.1908838
  - tools: {'Grep': 2, 'Read': 3, 'Edit': 2, 'Bash': 5}
- **prism**: resolved=False turns=9 tokens=348213 wall_s=35.1 cost=$0.15893380000000001
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 5}

> [2026-09-26 05:51:13]    native resolved=True tokens=468691 | prism resolved=False tokens=348213 prism_calls=2 [FLAGGED]

> [2026-09-26 05:51:13] -- apache__commons-lang__pr1720 (java) --

## apache__commons-lang__pr1720 (java)

- native: resolved=False tokens=861729 turns=16 wall_s=156.3
- prism : resolved=True tokens=578274 turns=12 wall_s=70.1 prism_calls=4
- token ratio (prism/native): 0.67x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=16 tokens=861729 wall_s=156.3 cost=$0.41487179999999996
  - tools: {'Grep': 1, 'Read': 2, 'Bash': 11, 'Edit': 1}
- **prism**: resolved=True turns=12 tokens=578274 wall_s=70.1 cost=$0.28448760000000006
  - tools: {'mcp__prism__prism': 4, 'Read': 3, 'Edit': 1, 'Bash': 3}

> [2026-09-26 05:55:43]    native resolved=False tokens=861729 | prism resolved=True tokens=578274 prism_calls=4 [FLAGGED]

> [2026-09-26 05:55:43] -- apache__commons-lang__pr1713 (java) --

## apache__commons-lang__pr1713 (java)

- native: resolved=True tokens=457071 turns=12 wall_s=80.7
- prism : resolved=True tokens=404785 turns=10 wall_s=184.8 prism_calls=1
- token ratio (prism/native): 0.89x

> [2026-09-26 06:00:48]    native resolved=True tokens=457071 | prism resolved=True tokens=404785 prism_calls=1

> [2026-09-26 06:00:48] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=True tokens=7219220 turns=75 wall_s=818.7
- prism : resolved=True tokens=5056436 turns=53 wall_s=570.0 prism_calls=17
- token ratio (prism/native): 0.70x

> [2026-09-26 06:25:25]    native resolved=True tokens=7219220 | prism resolved=True tokens=5056436 prism_calls=17

> [2026-09-26 06:25:25] -- FasterXML__jackson-databind__pr6099 (java) --

## FasterXML__jackson-databind__pr6099 (java)

- native: resolved=True tokens=1013807 turns=23 wall_s=136.6
- prism : resolved=True tokens=1064186 turns=21 wall_s=179.0 prism_calls=6
- token ratio (prism/native): 1.05x

> [2026-09-26 06:31:42]    native resolved=True tokens=1013807 | prism resolved=True tokens=1064186 prism_calls=6

> [2026-09-26 06:31:42] -- gin-gonic__gin__pr4535 (go) --

## gin-gonic__gin__pr4535 (go)

- native: resolved=False tokens=1023176 turns=25 wall_s=103.3
- prism : resolved=True tokens=885260 turns=18 wall_s=131.0 prism_calls=6
- token ratio (prism/native): 0.87x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=25 tokens=1023176 wall_s=103.3 cost=$0.3878806
  - tools: {'Grep': 4, 'Read': 4, 'Bash': 11, 'Write': 2, 'Edit': 3}
- **prism**: resolved=True turns=18 tokens=885260 wall_s=131.0 cost=$0.41865480000000005
  - tools: {'mcp__prism__prism': 6, 'Bash': 7, 'Read': 2, 'Edit': 2}

> [2026-09-26 06:36:00]    native resolved=False tokens=1023176 | prism resolved=True tokens=885260 prism_calls=6 [FLAGGED]

> [2026-09-26 06:36:00] -- apache__commons-lang__pr1733 (java) --

## apache__commons-lang__pr1733 (java)

- native: resolved=True tokens=436049 turns=12 wall_s=41.1
- prism : resolved=True tokens=408736 turns=10 wall_s=42.6 prism_calls=2
- token ratio (prism/native): 0.94x

> [2026-09-26 06:38:02]    native resolved=True tokens=436049 | prism resolved=True tokens=408736 prism_calls=2

> [2026-09-26 06:38:02] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=True tokens=1670509 turns=32 wall_s=167.2
- prism : resolved=True tokens=675488 turns=14 wall_s=84.9 prism_calls=3
- token ratio (prism/native): 0.40x

**FLAGGED** (token ratio 0.40x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=32 tokens=1670509 wall_s=167.2 cost=$0.5931884000000001
  - tools: {'Grep': 4, 'Read': 8, 'Bash': 15, 'Edit': 4}
- **prism**: resolved=True turns=14 tokens=675488 wall_s=84.9 cost=$0.2841884
  - tools: {'mcp__prism__prism': 3, 'Grep': 2, 'Bash': 5, 'Read': 1, 'Edit': 1, 'Write': 1}

> [2026-09-26 06:42:40]    native resolved=True tokens=1670509 | prism resolved=True tokens=675488 prism_calls=3 [FLAGGED]

> [2026-09-26 06:42:40] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=306375 turns=8 wall_s=66.4
- prism : resolved=True tokens=385764 turns=9 wall_s=75.4 prism_calls=1
- token ratio (prism/native): 1.26x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=8 tokens=306375 wall_s=66.4 cost=$0.18637279999999998
  - tools: {'Grep': 2, 'Read': 1, 'Edit': 1, 'Bash': 3}
- **prism**: resolved=True turns=9 tokens=385764 wall_s=75.4 cost=$0.21527359999999998
  - tools: {'mcp__prism__prism': 1, 'Read': 2, 'Edit': 2, 'Bash': 3}

> [2026-09-26 06:45:40]    native resolved=False tokens=306375 | prism resolved=True tokens=385764 prism_calls=1 [FLAGGED]

> [2026-09-26 06:45:40] -- pallets__click__pr3504 (python) --

## pallets__click__pr3504 (python)

- native: resolved=False tokens=478550 turns=12 wall_s=40.4
- prism : resolved=False tokens=476407 turns=11 wall_s=44.8 prism_calls=1
- token ratio (prism/native): 1.00x

> [2026-09-26 06:47:08]    native resolved=False tokens=478550 | prism resolved=False tokens=476407 prism_calls=1

> [2026-09-26 06:47:08] -- FasterXML__jackson-databind__pr6061 (java) --

## FasterXML__jackson-databind__pr6061 (java)

- native: resolved=False tokens=726918 turns=19 wall_s=247.6
- prism : resolved=False tokens=744755 turns=16 wall_s=184.9 prism_calls=7
- token ratio (prism/native): 1.02x

> [2026-09-26 06:55:49]    native resolved=False tokens=726918 | prism resolved=False tokens=744755 prism_calls=7

> [2026-09-26 06:55:49] -- apache__commons-lang__pr1591 (java) --

## apache__commons-lang__pr1591 (java)

- native: resolved=True tokens=732932 turns=16 wall_s=372.1
- prism : resolved=True tokens=483411 turns=11 wall_s=84.7 prism_calls=1
- token ratio (prism/native): 0.66x

**FLAGGED** (token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=16 tokens=732932 wall_s=372.1 cost=$0.3864856
  - tools: {'Grep': 3, 'Read': 3, 'Edit': 3, 'Bash': 6}
- **prism**: resolved=True turns=11 tokens=483411 wall_s=84.7 cost=$0.251958
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Edit': 1, 'Bash': 5, 'Grep': 2}

> [2026-09-26 07:04:08]    native resolved=True tokens=732932 | prism resolved=True tokens=483411 prism_calls=1 [FLAGGED]

> [2026-09-26 07:04:08] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=383556 turns=10 wall_s=46.0
- prism : resolved=False tokens=197115 turns=5 wall_s=51.4 prism_calls=2
- token ratio (prism/native): 0.51x

**FLAGGED** (token ratio 0.51x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=10 tokens=383556 wall_s=46.0 cost=$0.2004196
  - tools: {'Grep': 4, 'Read': 2, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=False turns=5 tokens=197115 wall_s=51.4 cost=$0.14065760000000002
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 1}

> [2026-09-26 07:06:23]    native resolved=False tokens=383556 | prism resolved=False tokens=197115 prism_calls=2 [FLAGGED]

> [2026-09-26 07:06:23] -- apache__commons-lang__pr1709 (java) --

## apache__commons-lang__pr1709 (java)

- native: resolved=True tokens=562847 turns=15 wall_s=69.2
- prism : resolved=True tokens=802132 turns=17 wall_s=161.0 prism_calls=6
- token ratio (prism/native): 1.43x

> [2026-09-26 07:10:51]    native resolved=True tokens=562847 | prism resolved=True tokens=802132 prism_calls=6

> [2026-09-26 07:10:51] -- FasterXML__jackson-databind__pr6044 (java) --

## FasterXML__jackson-databind__pr6044 (java)

- native: resolved=False tokens=6849348 turns=71 wall_s=665.0
- prism : resolved=False tokens=6128024 turns=50 wall_s=670.5 prism_calls=11
- token ratio (prism/native): 0.89x

> [2026-09-26 07:34:09]    native resolved=False tokens=6849348 | prism resolved=False tokens=6128024 prism_calls=11

> [2026-09-26 07:34:09] -- apache__commons-lang__pr1750 (java) --

## apache__commons-lang__pr1750 (java)

- native: resolved=True tokens=333949 turns=9 wall_s=59.9
- prism : resolved=True tokens=838405 turns=18 wall_s=98.9 prism_calls=1
- token ratio (prism/native): 2.51x

**FLAGGED** (token ratio 2.51x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=9 tokens=333949 wall_s=59.9 cost=$0.18163099999999996
  - tools: {'Grep': 1, 'Read': 2, 'Bash': 5}
- **prism**: resolved=True turns=18 tokens=838405 wall_s=98.9 cost=$0.335233
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Edit': 9, 'Grep': 1, 'Bash': 5}

> [2026-09-26 07:37:27]    native resolved=True tokens=333949 | prism resolved=True tokens=838405 prism_calls=1 [FLAGGED]

> [2026-09-26 07:37:27] -- FasterXML__jackson-databind__pr6018 (java) --

## FasterXML__jackson-databind__pr6018 (java)

- native: resolved=False tokens=1064873 turns=23 wall_s=166.4
- prism : resolved=False tokens=998261 turns=22 wall_s=183.6 prism_calls=4
- token ratio (prism/native): 0.94x

> [2026-09-26 07:44:43]    native resolved=False tokens=1064873 | prism resolved=False tokens=998261 prism_calls=4

> [2026-09-26 07:44:43] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=670940 turns=17 wall_s=79.2
- prism : resolved=False tokens=993171 turns=19 wall_s=120.0 prism_calls=7
- token ratio (prism/native): 1.48x

> [2026-09-26 07:48:28]    native resolved=False tokens=670940 | prism resolved=False tokens=993171 prism_calls=7

> [2026-09-26 07:48:28] -- akheron__jansson__pr741 (c) --

## akheron__jansson__pr741 (c)

- native: resolved=True tokens=1570895 turns=32 wall_s=166.3
- prism : resolved=True tokens=2088906 turns=32 wall_s=139.9 prism_calls=2
- token ratio (prism/native): 1.33x

> [2026-09-26 07:53:45]    native resolved=True tokens=1570895 | prism resolved=True tokens=2088906 prism_calls=2

> [2026-09-26 07:53:45] -- pallets__click__pr3473 (python) --

## pallets__click__pr3473 (python)

- native: resolved=False tokens=2198520 turns=41 wall_s=165.5
- prism : resolved=False tokens=578555 turns=12 wall_s=46.8 prism_calls=3
- token ratio (prism/native): 0.26x

**FLAGGED** (token ratio 0.26x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=41 tokens=2198520 wall_s=165.5 cost=$0.7246752
  - tools: {'Bash': 26, 'Grep': 1, 'Read': 10, 'Edit': 3}
- **prism**: resolved=False turns=12 tokens=578555 wall_s=46.8 cost=$0.2598616
  - tools: {'mcp__prism__prism': 3, 'Bash': 6, 'Edit': 2}

> [2026-09-26 07:57:42]    native resolved=False tokens=2198520 | prism resolved=False tokens=578555 prism_calls=3 [FLAGGED]

> [2026-09-26 07:57:42] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=True tokens=1078529 turns=23 wall_s=145.9
- prism : resolved=True tokens=2146599 turns=38 wall_s=168.8 prism_calls=7
- token ratio (prism/native): 1.99x

**FLAGGED** (token ratio 1.99x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=23 tokens=1078529 wall_s=145.9 cost=$0.45631200000000005
  - tools: {'Grep': 1, 'Bash': 11, 'Read': 6, 'Edit': 4}
- **prism**: resolved=True turns=38 tokens=2146599 wall_s=168.8 cost=$0.7312632000000002
  - tools: {'mcp__prism__prism': 7, 'Grep': 5, 'Edit': 13, 'Read': 1, 'Bash': 11}

> [2026-09-26 08:03:07]    native resolved=True tokens=1078529 | prism resolved=True tokens=2146599 prism_calls=7 [FLAGGED]

> [2026-09-26 08:03:07] -- FasterXML__jackson-databind__pr6008 (java) --

## FasterXML__jackson-databind__pr6008 (java)

- native: resolved=True tokens=2038476 turns=36 wall_s=272.6
- prism : resolved=True tokens=793104 turns=13 wall_s=197.0 prism_calls=3
- token ratio (prism/native): 0.39x

**FLAGGED** (token ratio 0.39x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=36 tokens=2038476 wall_s=272.6 cost=$0.8266082000000002
  - tools: {'Grep': 5, 'Read': 6, 'Bash': 19, 'Edit': 5}
- **prism**: resolved=True turns=13 tokens=793104 wall_s=197.0 cost=$0.4954782
  - tools: {'mcp__prism__prism': 3, 'Read': 5, 'Edit': 1, 'Bash': 3}

> [2026-09-26 08:12:23]    native resolved=True tokens=2038476 | prism resolved=True tokens=793104 prism_calls=3 [FLAGGED]

> [2026-09-26 08:12:23] -- FasterXML__jackson-databind__pr6076 (java) --

## FasterXML__jackson-databind__pr6076 (java)

- native: resolved=False tokens=7938956 turns=80 wall_s=703.7
- prism : resolved=False tokens=7609783 turns=63 wall_s=829.2 prism_calls=3
- token ratio (prism/native): 0.96x

> [2026-09-26 08:38:58]    native resolved=False tokens=7938956 | prism resolved=False tokens=7609783 prism_calls=3


# SUMMARY

50/50 tasks completed.

- native resolved: 31/50
- prism  resolved: 34/50
- native tokens total: 58213455
- prism  tokens total: 51746518 (0.89x native)
- flagged cells: 17 (0 non-adoption, 17 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- Textualize__rich__pr3882
- pallets__click__pr3466
- FasterXML__jackson-databind__pr6052
- apache__commons-lang__pr1670
- FasterXML__jackson-databind__pr6039
- gin-gonic__gin__pr4702
- pallets__click__pr3434
- apache__commons-lang__pr1720
- gin-gonic__gin__pr4535
- pallets__click__pr3653
- apache__commons-lang__pr1703
- apache__commons-lang__pr1591
- apache__commons-lang__pr1655
- apache__commons-lang__pr1750
- pallets__click__pr3473
- akheron__jansson__pr731
- FasterXML__jackson-databind__pr6008

Completed 2026-09-26 08:38:58

> [2026-09-26 08:38:58] DONE: 50/50 tasks, 17 flagged (0 non-adoption, 17 real)
