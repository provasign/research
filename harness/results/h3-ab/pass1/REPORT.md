# Overnight run: native vs resident prism_init

Started 2026-09-23 21:41:56. 19 tasks, model=sonnet, arms=prism_body_baseline vs prism_body_exp.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-23 21:41:56] starting: 19 tasks, 0 already done

> [2026-09-23 21:41:56] -- akheron__jansson__pr740 (c) --

## akheron__jansson__pr740 (c)

- native: resolved=False tokens=920309 turns=22 wall_s=117.9
- prism : resolved=False tokens=721089 turns=15 wall_s=67.8 prism_calls=4
- token ratio (prism/native): 0.78x

> [2026-09-23 21:45:13]    native resolved=False tokens=920309 | prism resolved=False tokens=721089 prism_calls=4

> [2026-09-23 21:45:13] -- pallets__click__pr3471 (python) --

## pallets__click__pr3471 (python)

- native: resolved=False tokens=651547 turns=15 wall_s=66.7
- prism : resolved=False tokens=601843 turns=14 wall_s=46.9 prism_calls=3
- token ratio (prism/native): 0.92x

> [2026-09-23 21:49:53]    native resolved=False tokens=651547 | prism resolved=False tokens=601843 prism_calls=3

> [2026-09-23 21:49:53] -- FasterXML__jackson-databind__pr6030 (java) --

## FasterXML__jackson-databind__pr6030 (java)

- native: resolved=False tokens=1479231 turns=24 wall_s=153.0
- prism : resolved=False tokens=2042626 turns=30 wall_s=197.5 prism_calls=7
- token ratio (prism/native): 1.38x

> [2026-09-23 21:57:52]    native resolved=False tokens=1479231 | prism resolved=False tokens=2042626 prism_calls=7

> [2026-09-23 21:57:52] -- FasterXML__jackson-databind__pr6052 (java) --

## FasterXML__jackson-databind__pr6052 (java)

- native: resolved=False tokens=298148 turns=8 wall_s=52.9
- prism : resolved=False tokens=528600 turns=11 wall_s=79.8 prism_calls=3
- token ratio (prism/native): 1.77x

**FLAGGED** (token ratio 1.77x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=8 tokens=298148 wall_s=52.9 cost=$0.14068960000000003
  - tools: {'mcp__prism__prism': 2, 'Read': 2, 'Bash': 3}
- **prism**: resolved=False turns=11 tokens=528600 wall_s=79.8 cost=$0.24509820000000002
  - tools: {'mcp__prism__prism': 3, 'Bash': 6, 'Read': 1}

> [2026-09-23 22:01:43]    native resolved=False tokens=298148 | prism resolved=False tokens=528600 prism_calls=3 [FLAGGED]

> [2026-09-23 22:01:43] -- gin-gonic__gin__pr4805 (go) --

## gin-gonic__gin__pr4805 (go)

- native: resolved=False tokens=600191 turns=12 wall_s=72.6
- prism : resolved=False tokens=782233 turns=20 wall_s=89.2 prism_calls=6
- token ratio (prism/native): 1.30x

> [2026-09-23 22:15:36]    native resolved=False tokens=600191 | prism resolved=False tokens=782233 prism_calls=6

> [2026-09-23 22:15:36] -- pallets__click__pr3434 (python) --

## pallets__click__pr3434 (python)

- native: resolved=False tokens=471922 turns=12 wall_s=51.1
- prism : resolved=False tokens=434239 turns=11 wall_s=44.5 prism_calls=3
- token ratio (prism/native): 0.92x

> [2026-09-23 22:25:04]    native resolved=False tokens=471922 | prism resolved=False tokens=434239 prism_calls=3

> [2026-09-23 22:25:04] -- FasterXML__jackson-databind__pr6019 (java) --

## FasterXML__jackson-databind__pr6019 (java)

- native: resolved=True tokens=1504049 turns=24 wall_s=191.4
- prism : resolved=False tokens=5822144 turns=57 wall_s=668.2 prism_calls=9
- token ratio (prism/native): 3.87x

**FLAGGED** (resolve mismatch, token ratio 3.87x outside [0.67, 1.5])

**Attribution: prism WAS called (9x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=24 tokens=1504049 wall_s=191.4 cost=$0.5932536000000003
  - tools: {'mcp__prism__prism': 5, 'Bash': 18}
- **prism**: resolved=False turns=57 tokens=5822144 wall_s=668.2 cost=$2.1600696
  - tools: {'mcp__prism__prism': 9, 'Bash': 31, 'Grep': 4, 'Read': 2, 'ToolSearch': 1, 'WebSearch': 2, 'WebFetch': 3, 'Edit': 2, 'Write': 2}

> [2026-09-23 22:41:31]    native resolved=True tokens=1504049 | prism resolved=False tokens=5822144 prism_calls=9 [FLAGGED]

> [2026-09-23 22:41:31] -- gin-gonic__gin__pr4535 (go) --

## gin-gonic__gin__pr4535 (go)

- native: resolved=False tokens=277880 turns=7 wall_s=28.2
- prism : resolved=False tokens=414198 turns=10 wall_s=52.1 prism_calls=3
- token ratio (prism/native): 1.49x

> [2026-09-23 22:44:53]    native resolved=False tokens=277880 | prism resolved=False tokens=414198 prism_calls=3

> [2026-09-23 22:44:53] -- pallets__click__pr3653 (python) --

## pallets__click__pr3653 (python)

- native: resolved=False tokens=1626305 turns=27 wall_s=103.5
- prism : resolved=True tokens=2022900 turns=33 wall_s=172.1 prism_calls=6
- token ratio (prism/native): 1.24x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=27 tokens=1626305 wall_s=103.5 cost=$0.5792756
  - tools: {'mcp__prism__prism': 8, 'mcp__prism__read': 1, 'Bash': 14, 'Grep': 1, 'Edit': 2}
- **prism**: resolved=True turns=33 tokens=2022900 wall_s=172.1 cost=$0.6957410000000003
  - tools: {'mcp__prism__prism': 6, 'Bash': 18, 'Read': 3, 'Grep': 3, 'Edit': 2}

> [2026-09-23 22:53:11]    native resolved=False tokens=1626305 | prism resolved=True tokens=2022900 prism_calls=6 [FLAGGED]

> [2026-09-23 22:53:11] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=413596 turns=10 wall_s=55.0
- prism : resolved=False tokens=866147 turns=17 wall_s=215.9 prism_calls=1
- token ratio (prism/native): 2.09x

**FLAGGED** (token ratio 2.09x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=10 tokens=413596 wall_s=55.0 cost=$0.19537020000000002
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 5}
- **prism**: resolved=False turns=17 tokens=866147 wall_s=215.9 cost=$0.3447568
  - tools: {'mcp__prism__prism': 1, 'Edit': 3, 'Bash': 8, 'Read': 3, 'Grep': 1}

> [2026-09-23 22:58:37]    native resolved=False tokens=413596 | prism resolved=False tokens=866147 prism_calls=1 [FLAGGED]

> [2026-09-23 22:58:37] -- pallets__click__pr3504 (python) --

## pallets__click__pr3504 (python)

- native: resolved=False tokens=548770 turns=12 wall_s=49.6
- prism : resolved=False tokens=1211587 turns=23 wall_s=174.2 prism_calls=3
- token ratio (prism/native): 2.21x

**FLAGGED** (token ratio 2.21x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=12 tokens=548770 wall_s=49.6 cost=$0.2204762
  - tools: {'mcp__prism__prism': 2, 'Bash': 8, 'Read': 1}
- **prism**: resolved=False turns=23 tokens=1211587 wall_s=174.2 cost=$0.5048786000000001
  - tools: {'mcp__prism__prism': 3, 'Read': 4, 'Grep': 3, 'Bash': 11, 'Edit': 1}

> [2026-09-23 23:03:46]    native resolved=False tokens=548770 | prism resolved=False tokens=1211587 prism_calls=3 [FLAGGED]

> [2026-09-23 23:03:46] -- FasterXML__jackson-databind__pr6061 (java) --

## FasterXML__jackson-databind__pr6061 (java)

- native: resolved=False tokens=1263682 turns=28 wall_s=193.5
- prism : resolved=False tokens=1025704 turns=22 wall_s=200.6 prism_calls=5
- token ratio (prism/native): 0.81x

> [2026-09-23 23:12:28]    native resolved=False tokens=1263682 | prism resolved=False tokens=1025704 prism_calls=5

> [2026-09-23 23:12:28] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=776493 turns=16 wall_s=267.0
- prism : resolved=False tokens=330614 turns=8 wall_s=50.9 prism_calls=3
- token ratio (prism/native): 0.43x

**FLAGGED** (token ratio 0.43x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=16 tokens=776493 wall_s=267.0 cost=$0.3315822
  - tools: {'mcp__prism__prism': 3, 'Grep': 1, 'Edit': 1, 'Bash': 10}
- **prism**: resolved=False turns=8 tokens=330614 wall_s=50.9 cost=$0.1608522
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 3}

> [2026-09-23 23:18:38]    native resolved=False tokens=776493 | prism resolved=False tokens=330614 prism_calls=3 [FLAGGED]

> [2026-09-23 23:18:38] -- FasterXML__jackson-databind__pr6044 (java) --

## FasterXML__jackson-databind__pr6044 (java)

- native: resolved=False tokens=2451816 turns=33 wall_s=261.8
- prism : resolved=False tokens=3019872 turns=37 wall_s=385.1 prism_calls=7
- token ratio (prism/native): 1.23x

> [2026-09-23 23:31:08]    native resolved=False tokens=2451816 | prism resolved=False tokens=3019872 prism_calls=7

> [2026-09-23 23:31:08] -- FasterXML__jackson-databind__pr6018 (java) --

## FasterXML__jackson-databind__pr6018 (java)

- native: resolved=False tokens=3876802 turns=45 wall_s=233.5
- prism : resolved=False tokens=1568082 turns=24 wall_s=221.0 prism_calls=4
- token ratio (prism/native): 0.40x

**FLAGGED** (token ratio 0.40x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=45 tokens=3876802 wall_s=233.5 cost=$1.2806005999999999
  - tools: {'mcp__prism__prism': 9, 'Grep': 8, 'Read': 5, 'Edit': 2, 'Bash': 20}
- **prism**: resolved=False turns=24 tokens=1568082 wall_s=221.0 cost=$0.6131485999999999
  - tools: {'mcp__prism__prism': 4, 'Read': 6, 'Grep': 2, 'Edit': 2, 'Bash': 9}

> [2026-09-23 23:40:46]    native resolved=False tokens=3876802 | prism resolved=False tokens=1568082 prism_calls=4 [FLAGGED]

> [2026-09-23 23:40:46] -- pallets__click__pr3678 (python) --

## pallets__click__pr3678 (python)

- native: resolved=False tokens=1151341 turns=22 wall_s=223.1
- prism : resolved=False tokens=1047295 turns=20 wall_s=113.1 prism_calls=8
- token ratio (prism/native): 0.91x

> [2026-09-23 23:48:59]    native resolved=False tokens=1151341 | prism resolved=False tokens=1047295 prism_calls=8

> [2026-09-23 23:48:59] -- pallets__click__pr3473 (python) --

## pallets__click__pr3473 (python)

- native: resolved=False tokens=1020615 turns=17 wall_s=69.9
- prism : resolved=False tokens=1025197 turns=18 wall_s=94.7 prism_calls=6
- token ratio (prism/native): 1.00x

> [2026-09-23 23:54:20]    native resolved=False tokens=1020615 | prism resolved=False tokens=1025197 prism_calls=6

> [2026-09-23 23:54:20] -- akheron__jansson__pr731 (c) --

## akheron__jansson__pr731 (c)

- native: resolved=True tokens=2003927 turns=34 wall_s=148.0
- prism : resolved=True tokens=1977644 turns=34 wall_s=147.6 prism_calls=7
- token ratio (prism/native): 0.99x

> [2026-09-23 23:59:26]    native resolved=True tokens=2003927 | prism resolved=True tokens=1977644 prism_calls=7

> [2026-09-23 23:59:26] -- FasterXML__jackson-databind__pr6076 (java) --

## FasterXML__jackson-databind__pr6076 (java)

- native: resolved=False tokens=4324897 turns=49 wall_s=484.4
- prism : resolved=False tokens=10516387 turns=88 wall_s=790.6 prism_calls=5
- token ratio (prism/native): 2.43x

**FLAGGED** (token ratio 2.43x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=49 tokens=4324897 wall_s=484.4 cost=$1.5471888000000007
  - tools: {'mcp__prism__prism': 10, 'Read': 4, 'Write': 2, 'Edit': 9, 'Grep': 1, 'Bash': 22}
- **prism**: resolved=False turns=88 tokens=10516387 wall_s=790.6 cost=$3.0990255999999996
  - tools: {'mcp__prism__prism': 5, 'Bash': 50, 'Read': 13, 'Write': 1, 'Edit': 16, 'Grep': 2}

> [2026-09-24 00:22:24]    native resolved=False tokens=4324897 | prism resolved=False tokens=10516387 prism_calls=5 [FLAGGED]


# SUMMARY

19/19 tasks completed.

- native resolved: 2/19
- prism  resolved: 2/19
- native tokens total: 25661521
- prism  tokens total: 35958401 (1.40x native)
- flagged cells: 8 (0 non-adoption, 8 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- FasterXML__jackson-databind__pr6052
- FasterXML__jackson-databind__pr6019
- pallets__click__pr3653
- apache__commons-lang__pr1703
- pallets__click__pr3504
- apache__commons-lang__pr1655
- FasterXML__jackson-databind__pr6018
- FasterXML__jackson-databind__pr6076

Completed 2026-09-24 00:22:24

> [2026-09-24 00:22:24] DONE: 19/19 tasks, 8 flagged (0 non-adoption, 8 real)
