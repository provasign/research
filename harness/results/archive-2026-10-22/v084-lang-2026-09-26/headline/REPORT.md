# Overnight run: native vs resident prism_init

Started 2026-09-26 20:34:17. 71 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-26 20:34:17] starting: 71 tasks, 0 already done

> [2026-09-26 20:34:17] -- urfave__cli__pr2296 (go) --

## urfave__cli__pr2296 (go)

- native: resolved=True tokens=987681 turns=22 wall_s=198.4
- prism : resolved=True tokens=330470 turns=8 wall_s=86.0 prism_calls=1
- token ratio (prism/native): 0.33x

**FLAGGED** (token ratio 0.33x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=22 tokens=987681 wall_s=198.4 cost=$0.4269016
  - tools: {'Grep': 6, 'Edit': 2, 'Read': 4, 'Bash': 9}
- **prism**: resolved=True turns=8 tokens=330470 wall_s=86.0 cost=$0.27585639999999995
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 5}

> [2026-09-26 20:39:18]    native resolved=True tokens=987681 | prism resolved=True tokens=330470 prism_calls=1 [FLAGGED]

> [2026-09-26 20:39:18] -- urfave__cli__pr2309 (go) --

## urfave__cli__pr2309 (go)

- native: resolved=True tokens=893587 turns=21 wall_s=204.7
- prism : resolved=True tokens=822029 turns=17 wall_s=75.9 prism_calls=3
- token ratio (prism/native): 0.92x

> [2026-09-26 20:44:12]    native resolved=True tokens=893587 | prism resolved=True tokens=822029 prism_calls=3

> [2026-09-26 20:44:12] -- urfave__cli__pr2290 (go) --

## urfave__cli__pr2290 (go)

- native: resolved=True tokens=617553 turns=14 wall_s=78.8
- prism : resolved=True tokens=353303 turns=9 wall_s=26.3 prism_calls=2
- token ratio (prism/native): 0.57x

**FLAGGED** (token ratio 0.57x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=14 tokens=617553 wall_s=78.8 cost=$0.27860759999999996
  - tools: {'Grep': 5, 'Read': 4, 'Bash': 3, 'Edit': 1}
- **prism**: resolved=True turns=9 tokens=353303 wall_s=26.3 cost=$0.1578274
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 4}

> [2026-09-26 20:46:11]    native resolved=True tokens=617553 | prism resolved=True tokens=353303 prism_calls=2 [FLAGGED]

> [2026-09-26 20:46:11] -- urfave__cli__pr2419 (go) --

## urfave__cli__pr2419 (go)

- native: resolved=True tokens=216861 turns=6 wall_s=39.2
- prism : resolved=True tokens=200935 turns=5 wall_s=16.5 prism_calls=1
- token ratio (prism/native): 0.93x

> [2026-09-26 20:47:21]    native resolved=True tokens=216861 | prism resolved=True tokens=200935 prism_calls=1

> [2026-09-26 20:47:21] -- urfave__cli__pr2297 (go) --

## urfave__cli__pr2297 (go)

- native: resolved=True tokens=337867 turns=9 wall_s=38.8
- prism : resolved=True tokens=500809 turns=12 wall_s=39.7 prism_calls=1
- token ratio (prism/native): 1.48x

> [2026-09-26 20:48:53]    native resolved=True tokens=337867 | prism resolved=True tokens=500809 prism_calls=1

> [2026-09-26 20:48:53] -- google__gson__pr3067 (java) --

## google__gson__pr3067 (java)

- native: resolved=True tokens=422073 turns=12 wall_s=42.6
- prism : resolved=True tokens=312468 turns=8 wall_s=38.3 prism_calls=3
- token ratio (prism/native): 0.74x

> [2026-09-26 20:50:32]    native resolved=True tokens=422073 | prism resolved=True tokens=312468 prism_calls=3

> [2026-09-26 20:50:32] -- urfave__cli__pr2311 (go) --

## urfave__cli__pr2311 (go)

- native: resolved=False tokens=207072 turns=6 wall_s=19.2
- prism : resolved=False tokens=149469 turns=4 wall_s=11.4 prism_calls=1
- token ratio (prism/native): 0.72x

> [2026-09-26 20:51:16]    native resolved=False tokens=207072 | prism resolved=False tokens=149469 prism_calls=1

> [2026-09-26 20:51:16] -- apache__dubbo__pr16350 (java) --

## apache__dubbo__pr16350 (java)

- native: resolved=True tokens=245718 turns=7 wall_s=28.6
- prism : resolved=True tokens=262846 turns=7 wall_s=32.5 prism_calls=2
- token ratio (prism/native): 1.07x

> [2026-09-26 20:57:08]    native resolved=True tokens=245718 | prism resolved=True tokens=262846 prism_calls=2

> [2026-09-26 20:57:08] -- apache__dubbo__pr16348 (java) --

## apache__dubbo__pr16348 (java)

- native: resolved=True tokens=280114 turns=8 wall_s=30.7
- prism : resolved=True tokens=147919 turns=4 wall_s=24.8 prism_calls=1
- token ratio (prism/native): 0.53x

**FLAGGED** (token ratio 0.53x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=8 tokens=280114 wall_s=30.7 cost=$0.131881
  - tools: {'Grep': 3, 'Edit': 1, 'Bash': 3}
- **prism**: resolved=True turns=4 tokens=147919 wall_s=24.8 cost=$0.0948372
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 1}

> [2026-09-26 21:02:53]    native resolved=True tokens=280114 | prism resolved=True tokens=147919 prism_calls=1 [FLAGGED]

> [2026-09-26 21:02:53] -- colinhacks__zod__pr6439 (ts) --

## colinhacks__zod__pr6439 (ts)

- native: resolved=True tokens=559606 turns=12 wall_s=55.2
- prism : resolved=True tokens=556498 turns=11 wall_s=61.2 prism_calls=2
- token ratio (prism/native): 0.99x

> [2026-09-26 21:05:34]    native resolved=True tokens=559606 | prism resolved=True tokens=556498 prism_calls=2

> [2026-09-26 21:05:34] -- go-chi__chi__pr1085 (go) --

## go-chi__chi__pr1085 (go)

- native: resolved=True tokens=134391 turns=4 wall_s=16.7
- prism : resolved=True tokens=185189 turns=5 wall_s=17.5 prism_calls=1
- token ratio (prism/native): 1.38x

> [2026-09-26 21:06:17]    native resolved=True tokens=134391 | prism resolved=True tokens=185189 prism_calls=1

> [2026-09-26 21:06:17] -- labstack__echo__pr3006 (go) --

## labstack__echo__pr3006 (go)

- native: resolved=True tokens=1046993 turns=23 wall_s=107.6
- prism : resolved=True tokens=1727770 turns=28 wall_s=251.2 prism_calls=7
- token ratio (prism/native): 1.65x

**FLAGGED** (token ratio 1.65x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=23 tokens=1046993 wall_s=107.6 cost=$0.42568500000000004
  - tools: {'Bash': 16, 'Read': 4, 'Edit': 2}
- **prism**: resolved=True turns=28 tokens=1727770 wall_s=251.2 cost=$0.7658441999999999
  - tools: {'mcp__prism__prism': 7, 'Grep': 5, 'Read': 6, 'Edit': 2, 'Bash': 7}

> [2026-09-26 21:12:31]    native resolved=True tokens=1046993 | prism resolved=True tokens=1727770 prism_calls=7 [FLAGGED]

> [2026-09-26 21:12:31] -- colinhacks__zod__pr6298 (ts) --

## colinhacks__zod__pr6298 (ts)

- native: resolved=True tokens=371373 turns=9 wall_s=40.8
- prism : resolved=True tokens=174684 turns=4 wall_s=17.5 prism_calls=1
- token ratio (prism/native): 0.47x

**FLAGGED** (token ratio 0.47x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=9 tokens=371373 wall_s=40.8 cost=$0.17984540000000002
  - tools: {'Grep': 1, 'Read': 1, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=4 tokens=174684 wall_s=17.5 cost=$0.1262022
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 1}

> [2026-09-26 21:14:07]    native resolved=True tokens=371373 | prism resolved=True tokens=174684 prism_calls=1 [FLAGGED]

> [2026-09-26 21:14:07] -- honojs__hono__pr5373 (ts) --

## honojs__hono__pr5373 (ts)

- native: resolved=True tokens=356058 turns=10 wall_s=46.8
- prism : resolved=True tokens=188906 turns=5 wall_s=21.1 prism_calls=1
- token ratio (prism/native): 0.53x

**FLAGGED** (token ratio 0.53x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=10 tokens=356058 wall_s=46.8 cost=$0.15847
  - tools: {'Grep': 1, 'Read': 1, 'Edit': 2, 'Bash': 5}
- **prism**: resolved=True turns=5 tokens=188906 wall_s=21.1 cost=$0.11192660000000001
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-26 21:16:10]    native resolved=True tokens=356058 | prism resolved=True tokens=188906 prism_calls=1 [FLAGGED]

> [2026-09-26 21:16:10] -- FasterXML__jackson-dataformat-xml__pr825 (java) --

## FasterXML__jackson-dataformat-xml__pr825 (java)

- native: resolved=False tokens=175280 turns=7 wall_s=28.9
- prism : resolved=False tokens=0 turns=1 wall_s=0.6 prism_calls=0

> [2026-09-26 21:16:45]    native resolved=False tokens=175280 | prism resolved=False tokens=0 prism_calls=0

> [2026-09-26 21:16:45] -- urfave__cli__pr2440 (go) --

## urfave__cli__pr2440 (go)

- native: resolved=False tokens=0 turns=1 wall_s=0.5
- prism : resolved=False tokens=0 turns=1 wall_s=0.8 prism_calls=0

> [2026-09-26 21:16:52]    native resolved=False tokens=0 | prism resolved=False tokens=0 prism_calls=0

> [2026-09-26 21:16:52] -- FasterXML__jackson-databind__pr5977 (java) --

> [2026-09-26 21:19:05] starting: 71 tasks, 14 already done

> [2026-09-26 21:19:05] -- FasterXML__jackson-dataformat-xml__pr825 (java) --

## FasterXML__jackson-dataformat-xml__pr825 (java)

- native: resolved=True tokens=1989207 turns=36 wall_s=162.4
- prism : resolved=True tokens=4033977 turns=53 wall_s=334.8 prism_calls=10
- token ratio (prism/native): 2.03x

**FLAGGED** (token ratio 2.03x outside [0.67, 1.5])

**Attribution: prism WAS called (10x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=36 tokens=1989207 wall_s=162.4 cost=$0.7629694
  - tools: {'Grep': 9, 'Bash': 19, 'Read': 4, 'Edit': 2, 'Write': 1}
- **prism**: resolved=True turns=53 tokens=4033977 wall_s=334.8 cost=$1.4136046000000002
  - tools: {'mcp__prism__prism': 10, 'Bash': 31, 'Grep': 6, 'Read': 4, 'Edit': 1}

> [2026-09-26 21:27:40]    native resolved=True tokens=1989207 | prism resolved=True tokens=4033977 prism_calls=10 [FLAGGED]

> [2026-09-26 21:27:40] -- urfave__cli__pr2440 (go) --

## urfave__cli__pr2440 (go)

- native: resolved=True tokens=763339 turns=18 wall_s=67.8
- prism : resolved=True tokens=637852 turns=13 wall_s=57.3 prism_calls=7
- token ratio (prism/native): 0.84x

> [2026-09-26 21:30:00]    native resolved=True tokens=763339 | prism resolved=True tokens=637852 prism_calls=7

> [2026-09-26 21:30:00] -- FasterXML__jackson-databind__pr5977 (java) --

## FasterXML__jackson-databind__pr5977 (java)

- native: resolved=False tokens=2018896 turns=33 wall_s=270.9
- prism : resolved=False tokens=646828 turns=14 wall_s=154.5 prism_calls=4
- token ratio (prism/native): 0.32x

**FLAGGED** (token ratio 0.32x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=33 tokens=2018896 wall_s=270.9 cost=$0.8104344
  - tools: {'Grep': 10, 'Read': 7, 'Bash': 15}
- **prism**: resolved=False turns=14 tokens=646828 wall_s=154.5 cost=$0.38319600000000004
  - tools: {'mcp__prism__prism': 4, 'Read': 2, 'Bash': 6, 'Grep': 1}

> [2026-09-26 21:38:05]    native resolved=False tokens=2018896 | prism resolved=False tokens=646828 prism_calls=4 [FLAGGED]

> [2026-09-26 21:38:05] -- colinhacks__zod__pr6129 (ts) --

## colinhacks__zod__pr6129 (ts)

- native: resolved=True tokens=539402 turns=13 wall_s=59.3
- prism : resolved=True tokens=744878 turns=14 wall_s=72.3 prism_calls=2
- token ratio (prism/native): 1.38x

> [2026-09-26 21:41:00]    native resolved=True tokens=539402 | prism resolved=True tokens=744878 prism_calls=2

> [2026-09-26 21:41:00] -- FasterXML__jackson-databind__pr6186 (java) --

## FasterXML__jackson-databind__pr6186 (java)

- native: resolved=True tokens=587263 turns=16 wall_s=56.3
- prism : resolved=True tokens=269673 turns=7 wall_s=70.3 prism_calls=2
- token ratio (prism/native): 0.46x

**FLAGGED** (token ratio 0.46x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=16 tokens=587263 wall_s=56.3 cost=$0.23192439999999998
  - tools: {'Grep': 5, 'Read': 4, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=7 tokens=269673 wall_s=70.3 cost=$0.13806240000000003
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-26 21:44:10]    native resolved=True tokens=587263 | prism resolved=True tokens=269673 prism_calls=2 [FLAGGED]

> [2026-09-26 21:44:10] -- honojs__hono__pr5366 (ts) --

## honojs__hono__pr5366 (ts)

- native: resolved=True tokens=424579 turns=11 wall_s=67.6
- prism : resolved=True tokens=395363 turns=10 wall_s=47.8 prism_calls=1
- token ratio (prism/native): 0.93x

> [2026-09-26 21:47:01]    native resolved=True tokens=424579 | prism resolved=True tokens=395363 prism_calls=1

> [2026-09-26 21:47:01] -- go-chi__chi__pr1029 (go) --

## go-chi__chi__pr1029 (go)

- native: resolved=True tokens=518075 turns=14 wall_s=74.6
- prism : resolved=True tokens=456060 turns=11 wall_s=72.2 prism_calls=5
- token ratio (prism/native): 0.88x

> [2026-09-26 21:49:37]    native resolved=True tokens=518075 | prism resolved=True tokens=456060 prism_calls=5

> [2026-09-26 21:49:37] -- h3js__h3__pr1273 (ts) --

## h3js__h3__pr1273 (ts)

- native: resolved=False tokens=834668 turns=21 wall_s=83.3
- prism : resolved=False tokens=1099715 turns=22 wall_s=99.5 prism_calls=3
- token ratio (prism/native): 1.32x

> [2026-09-26 21:53:18]    native resolved=False tokens=834668 | prism resolved=False tokens=1099715 prism_calls=3

> [2026-09-26 21:53:18] -- apache__dubbo__pr16391 (java) --

## apache__dubbo__pr16391 (java)

- native: resolved=True tokens=623438 turns=14 wall_s=132.4
- prism : resolved=True tokens=984781 turns=20 wall_s=485.2 prism_calls=6
- token ratio (prism/native): 1.58x

**FLAGGED** (token ratio 1.58x outside [0.67, 1.5])

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=14 tokens=623438 wall_s=132.4 cost=$0.27750980000000003
  - tools: {'Read': 2, 'Edit': 2, 'Grep': 2, 'Bash': 7}
- **prism**: resolved=True turns=20 tokens=984781 wall_s=485.2 cost=$0.3953848
  - tools: {'mcp__prism__prism': 6, 'Edit': 3, 'Read': 1, 'Bash': 9}

> [2026-09-26 22:08:32]    native resolved=True tokens=623438 | prism resolved=True tokens=984781 prism_calls=6 [FLAGGED]

> [2026-09-26 22:08:32] -- go-chi__chi__pr1158 (go) --

## go-chi__chi__pr1158 (go)

- native: resolved=True tokens=644118 turns=16 wall_s=136.3
- prism : resolved=True tokens=685610 turns=15 wall_s=199.0 prism_calls=2
- token ratio (prism/native): 1.06x

> [2026-09-26 22:14:17]    native resolved=True tokens=644118 | prism resolved=True tokens=685610 prism_calls=2

> [2026-09-26 22:14:17] -- urfave__cli__pr2355 (go) --

## urfave__cli__pr2355 (go)

- native: resolved=True tokens=3012150 turns=41 wall_s=322.0
- prism : resolved=True tokens=2245442 turns=36 wall_s=243.3 prism_calls=12
- token ratio (prism/native): 0.75x

> [2026-09-26 22:23:57]    native resolved=True tokens=3012150 | prism resolved=True tokens=2245442 prism_calls=12

> [2026-09-26 22:23:57] -- h3js__h3__pr1314 (ts) --

## h3js__h3__pr1314 (ts)

- native: resolved=False tokens=272284 turns=9 wall_s=20.2
- prism : resolved=False tokens=358334 turns=12 wall_s=51.6 prism_calls=8
- token ratio (prism/native): 1.32x

> [2026-09-26 22:25:31]    native resolved=False tokens=272284 | prism resolved=False tokens=358334 prism_calls=8

> [2026-09-26 22:25:31] -- FasterXML__jackson-dataformat-xml__pr827 (java) --

## FasterXML__jackson-dataformat-xml__pr827 (java)

- native: resolved=True tokens=2484040 turns=48 wall_s=375.5
- prism : resolved=False tokens=1750720 turns=28 wall_s=248.8 prism_calls=5
- token ratio (prism/native): 0.70x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=48 tokens=2484040 wall_s=375.5 cost=$0.9030574000000003
  - tools: {'Grep': 15, 'Glob': 1, 'Bash': 18, 'Read': 8, 'Edit': 4, 'Write': 1}
- **prism**: resolved=False turns=28 tokens=1750720 wall_s=248.8 cost=$0.7532226000000001
  - tools: {'mcp__prism__prism': 5, 'Read': 6, 'Bash': 13, 'Edit': 3}

> [2026-09-26 22:36:11]    native resolved=True tokens=2484040 | prism resolved=False tokens=1750720 prism_calls=5 [FLAGGED]

> [2026-09-26 22:36:11] -- FasterXML__jackson-databind__pr5964 (java) --

## FasterXML__jackson-databind__pr5964 (java)

- native: resolved=True tokens=1748994 turns=33 wall_s=173.0
- prism : resolved=True tokens=661512 turns=14 wall_s=114.2 prism_calls=8
- token ratio (prism/native): 0.38x

**FLAGGED** (token ratio 0.38x outside [0.67, 1.5])

**Attribution: prism WAS called (8x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=33 tokens=1748994 wall_s=173.0 cost=$0.6634431999999999
  - tools: {'Grep': 13, 'Read': 8, 'Edit': 1, 'Bash': 10}
- **prism**: resolved=True turns=14 tokens=661512 wall_s=114.2 cost=$0.30483760000000004
  - tools: {'mcp__prism__prism': 8, 'Edit': 1, 'Bash': 4}

> [2026-09-26 22:42:23]    native resolved=True tokens=1748994 | prism resolved=True tokens=661512 prism_calls=8 [FLAGGED]

> [2026-09-26 22:42:23] -- FasterXML__jackson-databind__pr6155 (java) --

## FasterXML__jackson-databind__pr6155 (java)

- native: resolved=True tokens=319107 turns=9 wall_s=36.1
- prism : resolved=True tokens=263241 turns=7 wall_s=55.5 prism_calls=3
- token ratio (prism/native): 0.82x

> [2026-09-26 22:44:56]    native resolved=True tokens=319107 | prism resolved=True tokens=263241 prism_calls=3

> [2026-09-26 22:44:56] -- FasterXML__jackson-databind__pr6138 (java) --

## FasterXML__jackson-databind__pr6138 (java)

- native: resolved=True tokens=338975 turns=8 wall_s=47.8
- prism : resolved=True tokens=404898 turns=9 wall_s=48.9 prism_calls=2
- token ratio (prism/native): 1.19x

> [2026-09-26 22:47:59]    native resolved=True tokens=338975 | prism resolved=True tokens=404898 prism_calls=2

> [2026-09-26 22:47:59] -- honojs__hono__pr5164 (ts) --

## honojs__hono__pr5164 (ts)

- native: resolved=True tokens=418989 turns=11 wall_s=61.9
- prism : resolved=True tokens=351220 turns=9 wall_s=32.6 prism_calls=1
- token ratio (prism/native): 0.84x

> [2026-09-26 22:50:27]    native resolved=True tokens=418989 | prism resolved=True tokens=351220 prism_calls=1

> [2026-09-26 22:50:27] -- colinhacks__zod__pr6144 (ts) --

## colinhacks__zod__pr6144 (ts)

- native: resolved=True tokens=769115 turns=17 wall_s=80.1
- prism : resolved=True tokens=538754 turns=11 wall_s=50.6 prism_calls=3
- token ratio (prism/native): 0.70x

> [2026-09-26 22:53:18]    native resolved=True tokens=769115 | prism resolved=True tokens=538754 prism_calls=3

> [2026-09-26 22:53:18] -- honojs__hono__pr5199 (ts) --

## honojs__hono__pr5199 (ts)

- native: resolved=True tokens=344853 turns=9 wall_s=44.3
- prism : resolved=True tokens=393618 turns=10 wall_s=44.0 prism_calls=3
- token ratio (prism/native): 1.14x

> [2026-09-26 22:55:35]    native resolved=True tokens=344853 | prism resolved=True tokens=393618 prism_calls=3

> [2026-09-26 22:55:35] -- google__gson__pr3116 (java) --

## google__gson__pr3116 (java)

- native: resolved=False tokens=588287 turns=13 wall_s=140.7
- prism : resolved=False tokens=448244 turns=10 wall_s=84.2 prism_calls=3
- token ratio (prism/native): 0.76x

> [2026-09-26 22:59:39]    native resolved=False tokens=588287 | prism resolved=False tokens=448244 prism_calls=3

> [2026-09-26 22:59:39] -- FasterXML__jackson-databind__pr5959 (java) --

## FasterXML__jackson-databind__pr5959 (java)

- native: resolved=False tokens=4474631 turns=58 wall_s=490.0
- prism : resolved=False tokens=2469694 turns=34 wall_s=432.5 prism_calls=7
- token ratio (prism/native): 0.55x

**FLAGGED** (token ratio 0.55x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=58 tokens=4474631 wall_s=490.0 cost=$1.5392024000000002
  - tools: {'Grep': 11, 'Read': 16, 'Edit': 13, 'Bash': 17}
- **prism**: resolved=False turns=34 tokens=2469694 wall_s=432.5 cost=$0.9441402000000002
  - tools: {'mcp__prism__prism': 7, 'Read': 4, 'Bash': 16, 'Edit': 3, 'Grep': 2, 'Write': 1}

> [2026-09-26 23:16:32]    native resolved=False tokens=4474631 | prism resolved=False tokens=2469694 prism_calls=7 [FLAGGED]

> [2026-09-26 23:16:32] -- FasterXML__jackson-databind__pr5943 (java) --

## FasterXML__jackson-databind__pr5943 (java)

- native: resolved=True tokens=776512 turns=20 wall_s=123.4
- prism : resolved=True tokens=268157 turns=7 wall_s=77.7 prism_calls=2
- token ratio (prism/native): 0.35x

**FLAGGED** (token ratio 0.35x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=20 tokens=776512 wall_s=123.4 cost=$0.3293266
  - tools: {'Grep': 3, 'Bash': 14, 'Read': 1, 'Edit': 1}
- **prism**: resolved=True turns=7 tokens=268157 wall_s=77.7 cost=$0.13786259999999997
  - tools: {'mcp__prism__prism': 2, 'Edit': 2, 'Bash': 2}

> [2026-09-26 23:21:16]    native resolved=True tokens=776512 | prism resolved=True tokens=268157 prism_calls=2 [FLAGGED]

> [2026-09-26 23:21:16] -- google__gson__pr3112 (java) --

## google__gson__pr3112 (java)

- native: resolved=False tokens=555645 turns=14 wall_s=75.0
- prism : resolved=False tokens=469235 turns=11 wall_s=53.8 prism_calls=2
- token ratio (prism/native): 0.84x

> [2026-09-26 23:23:42]    native resolved=False tokens=555645 | prism resolved=False tokens=469235 prism_calls=2

> [2026-09-26 23:23:42] -- FasterXML__jackson-databind__pr5994 (java) --

## FasterXML__jackson-databind__pr5994 (java)

- native: resolved=False tokens=424317 turns=11 wall_s=129.8
- prism : resolved=False tokens=822014 turns=19 wall_s=205.9 prism_calls=5
- token ratio (prism/native): 1.94x

**FLAGGED** (token ratio 1.94x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=11 tokens=424317 wall_s=129.8 cost=$0.2199968
  - tools: {'Grep': 2, 'Read': 1, 'Edit': 3, 'Bash': 4}
- **prism**: resolved=False turns=19 tokens=822014 wall_s=205.9 cost=$0.323762
  - tools: {'mcp__prism__prism': 5, 'Edit': 5, 'Read': 1, 'Bash': 7}

> [2026-09-26 23:34:06]    native resolved=False tokens=424317 | prism resolved=False tokens=822014 prism_calls=5 [FLAGGED]

> [2026-09-26 23:34:06] -- apache__dubbo__pr16395 (java) --

## apache__dubbo__pr16395 (java)

- native: resolved=False tokens=1243486 turns=23 wall_s=283.2
- prism : resolved=False tokens=2162380 turns=30 wall_s=504.5 prism_calls=9
- token ratio (prism/native): 1.74x

**FLAGGED** (token ratio 1.74x outside [0.67, 1.5])

**Attribution: prism WAS called (9x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=23 tokens=1243486 wall_s=283.2 cost=$0.6551822000000002
  - tools: {'Grep': 9, 'Read': 6, 'Edit': 2, 'Bash': 5}
- **prism**: resolved=False turns=30 tokens=2162380 wall_s=504.5 cost=$0.9960885999999999
  - tools: {'mcp__prism__prism': 9, 'Edit': 1, 'Grep': 3, 'Bash': 11, 'Read': 5}

> [2026-09-26 23:52:30]    native resolved=False tokens=1243486 | prism resolved=False tokens=2162380 prism_calls=9 [FLAGGED]

> [2026-09-26 23:52:30] -- honojs__hono__pr5311 (ts) --

## honojs__hono__pr5311 (ts)

- native: resolved=True tokens=211800 turns=7 wall_s=20.8
- prism : resolved=True tokens=307967 turns=8 wall_s=21.5 prism_calls=3
- token ratio (prism/native): 1.45x

> [2026-09-26 23:54:07]    native resolved=True tokens=211800 | prism resolved=True tokens=307967 prism_calls=3

> [2026-09-26 23:54:07] -- urllib3__urllib3__pr5020 (python) --

## urllib3__urllib3__pr5020 (python)

- native: resolved=False tokens=1610850 turns=39 wall_s=241.5
- prism : resolved=False tokens=2240305 turns=39 wall_s=234.8 prism_calls=7
- token ratio (prism/native): 1.39x

> [2026-09-27 00:02:37]    native resolved=False tokens=1610850 | prism resolved=False tokens=2240305 prism_calls=7

> [2026-09-27 00:02:37] -- go-chi__chi__pr1148 (go) --

## go-chi__chi__pr1148 (go)

- native: resolved=True tokens=1469204 turns=33 wall_s=249.1
- prism : resolved=True tokens=1368211 turns=28 wall_s=250.6 prism_calls=5
- token ratio (prism/native): 0.93x

> [2026-09-27 00:11:06]    native resolved=True tokens=1469204 | prism resolved=True tokens=1368211 prism_calls=5

> [2026-09-27 00:11:06] -- google__gson__pr3000 (java) --

## google__gson__pr3000 (java)

- native: resolved=True tokens=438666 turns=11 wall_s=37.2
- prism : resolved=True tokens=358106 turns=9 wall_s=35.8 prism_calls=1
- token ratio (prism/native): 0.82x

> [2026-09-27 00:12:36]    native resolved=True tokens=438666 | prism resolved=True tokens=358106 prism_calls=1

> [2026-09-27 00:12:36] -- FasterXML__jackson-databind__pr5976 (java) --

## FasterXML__jackson-databind__pr5976 (java)

- native: resolved=True tokens=7169082 turns=75 wall_s=799.1
- prism : resolved=True tokens=11602150 turns=91 wall_s=954.8 prism_calls=5
- token ratio (prism/native): 1.62x

**FLAGGED** (token ratio 1.62x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=75 tokens=7169082 wall_s=799.1 cost=$2.487134799999999
  - tools: {'Grep': 19, 'Read': 26, 'Bash': 20, 'Edit': 8, 'Write': 1}
- **prism**: resolved=True turns=91 tokens=11602150 wall_s=954.8 cost=$3.584971400000002
  - tools: {'mcp__prism__prism': 5, 'Read': 24, 'Bash': 41, 'Write': 3, 'Edit': 16, 'Grep': 1}

> [2026-09-27 00:43:20]    native resolved=True tokens=7169082 | prism resolved=True tokens=11602150 prism_calls=5 [FLAGGED]

> [2026-09-27 00:43:20] -- FasterXML__jackson-dataformat-xml__pr817 (java) --

## FasterXML__jackson-dataformat-xml__pr817 (java)

- native: resolved=True tokens=3572562 turns=41 wall_s=431.2
- prism : resolved=True tokens=4724122 turns=53 wall_s=602.1 prism_calls=11
- token ratio (prism/native): 1.32x

> [2026-09-27 01:00:50]    native resolved=True tokens=3572562 | prism resolved=True tokens=4724122 prism_calls=11

> [2026-09-27 01:00:50] -- google__gson__pr3059 (java) --

## google__gson__pr3059 (java)

- native: resolved=False tokens=554599 turns=13 wall_s=69.4
- prism : resolved=False tokens=546229 turns=13 wall_s=77.6 prism_calls=8
- token ratio (prism/native): 0.98x

> [2026-09-27 01:03:34]    native resolved=False tokens=554599 | prism resolved=False tokens=546229 prism_calls=8

> [2026-09-27 01:03:34] -- urllib3__urllib3__pr3786 (python) --

## urllib3__urllib3__pr3786 (python)

- native: resolved=False tokens=3630054 turns=56 wall_s=379.7
- prism : resolved=False tokens=3619569 turns=46 wall_s=419.1 prism_calls=7
- token ratio (prism/native): 1.00x

> [2026-09-27 01:18:22]    native resolved=False tokens=3630054 | prism resolved=False tokens=3619569 prism_calls=7

> [2026-09-27 01:18:22] -- h3js__h3__pr1352 (ts) --

## h3js__h3__pr1352 (ts)

- native: resolved=True tokens=1741415 turns=31 wall_s=160.8
- prism : resolved=True tokens=938108 turns=18 wall_s=95.8 prism_calls=3
- token ratio (prism/native): 0.54x

**FLAGGED** (token ratio 0.54x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=31 tokens=1741415 wall_s=160.8 cost=$0.6764212
  - tools: {'Grep': 2, 'Read': 6, 'Edit': 6, 'Bash': 16}
- **prism**: resolved=True turns=18 tokens=938108 wall_s=95.8 cost=$0.3878274000000001
  - tools: {'mcp__prism__prism': 3, 'Edit': 4, 'Bash': 9, 'Read': 1}

> [2026-09-27 01:23:01]    native resolved=True tokens=1741415 | prism resolved=True tokens=938108 prism_calls=3 [FLAGGED]

> [2026-09-27 01:23:01] -- FasterXML__jackson-dataformat-xml__pr821 (java) --

## FasterXML__jackson-dataformat-xml__pr821 (java)

- native: resolved=True tokens=1082352 turns=23 wall_s=240.0
- prism : resolved=True tokens=1679008 turns=30 wall_s=275.5 prism_calls=4
- token ratio (prism/native): 1.55x

**FLAGGED** (token ratio 1.55x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=23 tokens=1082352 wall_s=240.0 cost=$0.4388688
  - tools: {'Bash': 16, 'Read': 2, 'Edit': 3, 'Write': 1}
- **prism**: resolved=True turns=30 tokens=1679008 wall_s=275.5 cost=$0.6238728000000001
  - tools: {'mcp__prism__prism': 4, 'Read': 1, 'Bash': 22, 'Edit': 2}

> [2026-09-27 01:31:51]    native resolved=True tokens=1082352 | prism resolved=True tokens=1679008 prism_calls=4 [FLAGGED]

> [2026-09-27 01:31:51] -- Textualize__rich__pr3938 (python) --

## Textualize__rich__pr3938 (python)

- native: resolved=False tokens=1549627 turns=32 wall_s=166.6
- prism : resolved=False tokens=1931909 turns=33 wall_s=222.8 prism_calls=9
- token ratio (prism/native): 1.25x

> [2026-09-27 01:38:35]    native resolved=False tokens=1549627 | prism resolved=False tokens=1931909 prism_calls=9

> [2026-09-27 01:38:35] -- colinhacks__zod__pr6500 (ts) --

## colinhacks__zod__pr6500 (ts)

- native: resolved=False tokens=2594309 turns=39 wall_s=196.0
- prism : resolved=False tokens=4058197 turns=53 wall_s=280.1 prism_calls=4
- token ratio (prism/native): 1.56x

**FLAGGED** (token ratio 1.56x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=39 tokens=2594309 wall_s=196.0 cost=$0.9172240000000002
  - tools: {'Grep': 12, 'Read': 8, 'Bash': 12, 'Write': 1, 'Edit': 5}
- **prism**: resolved=False turns=53 tokens=4058197 wall_s=280.1 cost=$1.2871942000000003
  - tools: {'mcp__prism__prism': 4, 'Read': 12, 'Bash': 21, 'Write': 3, 'Edit': 7, 'Grep': 5}

> [2026-09-27 01:47:17]    native resolved=False tokens=2594309 | prism resolved=False tokens=4058197 prism_calls=4 [FLAGGED]

> [2026-09-27 01:47:17] -- pallets__werkzeug__pr3081 (python) --

## pallets__werkzeug__pr3081 (python)

- native: resolved=False tokens=572480 turns=7 wall_s=1452.8
- prism : resolved=False tokens=None turns=None wall_s=None prism_calls=0

> [2026-09-27 02:41:45]    native resolved=False tokens=572480 | prism resolved=False tokens=None prism_calls=0

> [2026-09-27 02:41:45] -- google__gson__pr3057 (java) --

## google__gson__pr3057 (java)

- native: resolved=False tokens=809674 turns=19 wall_s=102.7
- prism : resolved=False tokens=460964 turns=10 wall_s=61.8 prism_calls=3
- token ratio (prism/native): 0.57x

**FLAGGED** (token ratio 0.57x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=19 tokens=809674 wall_s=102.7 cost=$0.3456526
  - tools: {'Grep': 5, 'Read': 1, 'Bash': 11, 'Edit': 1}
- **prism**: resolved=False turns=10 tokens=460964 wall_s=61.8 cost=$0.2440366
  - tools: {'mcp__prism__prism': 3, 'Edit': 2, 'Bash': 4}

> [2026-09-27 02:44:48]    native resolved=False tokens=809674 | prism resolved=False tokens=460964 prism_calls=3 [FLAGGED]

> [2026-09-27 02:44:48] -- FasterXML__jackson-dataformat-xml__pr822 (java) --

## FasterXML__jackson-dataformat-xml__pr822 (java)

- native: resolved=True tokens=2223069 turns=42 wall_s=227.6
- prism : resolved=True tokens=1924547 turns=30 wall_s=498.4 prism_calls=6
- token ratio (prism/native): 0.87x

> [2026-09-27 02:57:10]    native resolved=True tokens=2223069 | prism resolved=True tokens=1924547 prism_calls=6

> [2026-09-27 02:57:10] -- FasterXML__jackson-dataformat-xml__pr829 (java) --

## FasterXML__jackson-dataformat-xml__pr829 (java)

- native: resolved=True tokens=4525329 turns=61 wall_s=432.7
- prism : resolved=True tokens=2621035 turns=38 wall_s=242.1 prism_calls=12
- token ratio (prism/native): 0.58x

**FLAGGED** (token ratio 0.58x outside [0.67, 1.5])

**Attribution: prism WAS called (12x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=61 tokens=4525329 wall_s=432.7 cost=$1.6345654
  - tools: {'Grep': 13, 'Read': 18, 'Edit': 9, 'Bash': 19, 'Write': 1}
- **prism**: resolved=True turns=38 tokens=2621035 wall_s=242.1 cost=$0.9705098000000003
  - tools: {'mcp__prism__prism': 12, 'Bash': 12, 'Read': 5, 'Write': 2, 'Grep': 2, 'Edit': 4}

> [2026-09-27 03:08:41]    native resolved=True tokens=4525329 | prism resolved=True tokens=2621035 prism_calls=12 [FLAGGED]

> [2026-09-27 03:08:41] -- FasterXML__jackson-databind__pr5947 (java) --

## FasterXML__jackson-databind__pr5947 (java)

- native: resolved=True tokens=2359131 turns=37 wall_s=355.1
- prism : resolved=False tokens=2186292 turns=30 wall_s=314.7 prism_calls=6
- token ratio (prism/native): 0.93x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=37 tokens=2359131 wall_s=355.1 cost=$1.0073732
  - tools: {'Bash': 27, 'Grep': 2, 'Glob': 2, 'Read': 3, 'Edit': 2}
- **prism**: resolved=False turns=30 tokens=2186292 wall_s=314.7 cost=$0.8984642
  - tools: {'mcp__prism__prism': 6, 'Read': 5, 'Bash': 16, 'Edit': 2}

> [2026-09-27 03:21:21]    native resolved=True tokens=2359131 | prism resolved=False tokens=2186292 prism_calls=6 [FLAGGED]

> [2026-09-27 03:21:21] -- pydantic__pydantic__pr13516 (python) --

## pydantic__pydantic__pr13516 (python)

- native: resolved=False tokens=566114 turns=14 wall_s=111.7
- prism : resolved=False tokens=726016 turns=15 wall_s=97.1 prism_calls=2
- token ratio (prism/native): 1.28x

> [2026-09-27 03:26:17]    native resolved=False tokens=566114 | prism resolved=False tokens=726016 prism_calls=2

> [2026-09-27 03:26:17] -- pallets__werkzeug__pr3038 (python) --

## pallets__werkzeug__pr3038 (python)

- native: resolved=False tokens=1533308 turns=38 wall_s=245.0
- prism : resolved=False tokens=1522190 turns=30 wall_s=246.7 prism_calls=5
- token ratio (prism/native): 0.99x

> [2026-09-27 03:35:11]    native resolved=False tokens=1533308 | prism resolved=False tokens=1522190 prism_calls=5

> [2026-09-27 03:35:11] -- google__gson__pr3098 (java) --

## google__gson__pr3098 (java)

- native: resolved=False tokens=707053 turns=17 wall_s=73.2
- prism : resolved=False tokens=1370372 turns=25 wall_s=247.9 prism_calls=7
- token ratio (prism/native): 1.94x

**FLAGGED** (token ratio 1.94x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=17 tokens=707053 wall_s=73.2 cost=$0.2785560000000001
  - tools: {'Grep': 3, 'Read': 5, 'Edit': 2, 'Bash': 6}
- **prism**: resolved=False turns=25 tokens=1370372 wall_s=247.9 cost=$0.7200375999999999
  - tools: {'mcp__prism__prism': 7, 'Grep': 2, 'Edit': 4, 'Bash': 8, 'Read': 3}

> [2026-09-27 03:40:49]    native resolved=False tokens=707053 | prism resolved=False tokens=1370372 prism_calls=7 [FLAGGED]

> [2026-09-27 03:40:49] -- pallets__click__pr3228 (python) --

## pallets__click__pr3228 (python)

- native: resolved=False tokens=475977 turns=16 wall_s=34.1
- prism : resolved=False tokens=591685 turns=14 wall_s=45.8 prism_calls=5
- token ratio (prism/native): 1.24x

> [2026-09-27 03:42:35]    native resolved=False tokens=475977 | prism resolved=False tokens=591685 prism_calls=5

> [2026-09-27 03:42:35] -- pallets__click__pr3244 (python) --

## pallets__click__pr3244 (python)

- native: resolved=True tokens=1380984 turns=25 wall_s=301.8
- prism : resolved=False tokens=3578344 turns=53 wall_s=851.3 prism_calls=3
- token ratio (prism/native): 2.59x

**FLAGGED** (resolve mismatch, token ratio 2.59x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=25 tokens=1380984 wall_s=301.8 cost=$0.5785368000000001
  - tools: {'Grep': 2, 'Read': 5, 'Edit': 4, 'Write': 2, 'Bash': 11}
- **prism**: resolved=False turns=53 tokens=3578344 wall_s=851.3 cost=$1.2270655999999998
  - tools: {'mcp__prism__prism': 3, 'Read': 14, 'Grep': 7, 'Bash': 19, 'Edit': 6, 'ToolSearch': 1, 'ScheduleWakeup': 2}

> [2026-09-27 04:02:18]    native resolved=True tokens=1380984 | prism resolved=False tokens=3578344 prism_calls=3 [FLAGGED]

> [2026-09-27 04:02:18] -- FasterXML__jackson-dataformat-xml__pr885 (java) --

## FasterXML__jackson-dataformat-xml__pr885 (java)

- native: resolved=False tokens=481408 turns=12 wall_s=63.4
- prism : resolved=False tokens=677586 turns=14 wall_s=74.5 prism_calls=3
- token ratio (prism/native): 1.41x

> [2026-09-27 04:04:51]    native resolved=False tokens=481408 | prism resolved=False tokens=677586 prism_calls=3

> [2026-09-27 04:04:51] -- pallets__click__pr3533 (python) --

## pallets__click__pr3533 (python)

- native: resolved=True tokens=5563902 turns=68 wall_s=811.6
- prism : resolved=True tokens=4801214 turns=65 wall_s=703.3 prism_calls=13
- token ratio (prism/native): 0.86x

> [2026-09-27 04:30:33]    native resolved=True tokens=5563902 | prism resolved=True tokens=4801214 prism_calls=13

> [2026-09-27 04:30:33] -- FasterXML__jackson-dataformat-xml__pr819 (java) --

## FasterXML__jackson-dataformat-xml__pr819 (java)

- native: resolved=True tokens=7990782 turns=58 wall_s=1349.0
- prism : resolved=True tokens=7868313 turns=73 wall_s=800.5 prism_calls=11
- token ratio (prism/native): 0.98x

> [2026-09-27 05:06:40]    native resolved=True tokens=7990782 | prism resolved=True tokens=7868313 prism_calls=11

> [2026-09-27 05:06:40] -- urllib3__urllib3__pr5093 (python) --

## urllib3__urllib3__pr5093 (python)

- native: resolved=False tokens=1289353 turns=26 wall_s=134.1
- prism : resolved=False tokens=1680415 turns=30 wall_s=235.5 prism_calls=4
- token ratio (prism/native): 1.30x

> [2026-09-27 05:14:18]    native resolved=False tokens=1289353 | prism resolved=False tokens=1680415 prism_calls=4

> [2026-09-27 05:14:18] -- FasterXML__jackson-databind__pr5983 (java) --

## FasterXML__jackson-databind__pr5983 (java)

- native: resolved=False tokens=1615705 turns=27 wall_s=364.6
- prism : resolved=True tokens=2352922 turns=31 wall_s=543.4 prism_calls=6
- token ratio (prism/native): 1.46x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=27 tokens=1615705 wall_s=364.6 cost=$0.8287972000000001
  - tools: {'Bash': 15, 'Read': 5, 'Grep': 1, 'Edit': 5}
- **prism**: resolved=True turns=31 tokens=2352922 wall_s=543.4 cost=$1.0800490000000003
  - tools: {'mcp__prism__prism': 6, 'Bash': 16, 'Read': 4, 'Edit': 3, 'Write': 1}

> [2026-09-27 05:30:56]    native resolved=False tokens=1615705 | prism resolved=True tokens=2352922 prism_calls=6 [FLAGGED]

> [2026-09-27 05:30:56] -- FasterXML__jackson-databind__pr6215 (java) --

## FasterXML__jackson-databind__pr6215 (java)

- native: resolved=False tokens=699079 turns=16 wall_s=187.9
- prism : resolved=False tokens=810499 turns=17 wall_s=112.8 prism_calls=2
- token ratio (prism/native): 1.16x

> [2026-09-27 05:37:22]    native resolved=False tokens=699079 | prism resolved=False tokens=810499 prism_calls=2

> [2026-09-27 05:37:22] -- FasterXML__jackson-databind__pr5953 (java) --

## FasterXML__jackson-databind__pr5953 (java)

- native: resolved=False tokens=1511514 turns=32 wall_s=298.1
- prism : resolved=False tokens=1755870 turns=27 wall_s=426.8 prism_calls=5
- token ratio (prism/native): 1.16x

> [2026-09-27 05:50:57]    native resolved=False tokens=1511514 | prism resolved=False tokens=1755870 prism_calls=5

> [2026-09-27 05:50:57] -- apache__dubbo__pr16325 (java) --

## apache__dubbo__pr16325 (java)

- native: resolved=False tokens=3131903 turns=41 wall_s=359.1
- prism : resolved=False tokens=2306479 turns=31 wall_s=306.6 prism_calls=8
- token ratio (prism/native): 0.74x

> [2026-09-27 06:06:58]    native resolved=False tokens=3131903 | prism resolved=False tokens=2306479 prism_calls=8

> [2026-09-27 06:06:58] -- pallets__click__pr3695 (python) --

## pallets__click__pr3695 (python)

- native: resolved=False tokens=824956 turns=30 wall_s=62.8
- prism : resolved=False tokens=1000573 turns=21 wall_s=95.4 prism_calls=2
- token ratio (prism/native): 1.21x

> [2026-09-27 06:10:02]    native resolved=False tokens=824956 | prism resolved=False tokens=1000573 prism_calls=2

> [2026-09-27 06:10:02] -- pallets__werkzeug__pr3006 (python) --

## pallets__werkzeug__pr3006 (python)

- native: resolved=False tokens=1869844 turns=32 wall_s=423.5
- prism : resolved=False tokens=1019519 turns=21 wall_s=210.6 prism_calls=1
- token ratio (prism/native): 0.55x

**FLAGGED** (token ratio 0.55x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=32 tokens=1869844 wall_s=423.5 cost=$0.6864039999999998
  - tools: {'Grep': 3, 'Read': 5, 'Bash': 16, 'ToolSearch': 2, 'Edit': 5}
- **prism**: resolved=False turns=21 tokens=1019519 wall_s=210.6 cost=$0.3995972
  - tools: {'mcp__prism__prism': 1, 'Read': 3, 'Edit': 5, 'Grep': 2, 'Bash': 8, 'ToolSearch': 1}

> [2026-09-27 06:21:05]    native resolved=False tokens=1869844 | prism resolved=False tokens=1019519 prism_calls=1 [FLAGGED]


# SUMMARY

71/71 tasks completed.

- native resolved: 43/71
- prism  resolved: 41/71
- native tokens total: 99147402
- prism  tokens total: 102104211 (1.03x native)
- flagged cells: 27 (0 non-adoption, 27 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- urfave__cli__pr2296
- urfave__cli__pr2290
- apache__dubbo__pr16348
- labstack__echo__pr3006
- colinhacks__zod__pr6298
- honojs__hono__pr5373
- FasterXML__jackson-dataformat-xml__pr825
- FasterXML__jackson-databind__pr5977
- FasterXML__jackson-databind__pr6186
- apache__dubbo__pr16391
- FasterXML__jackson-dataformat-xml__pr827
- FasterXML__jackson-databind__pr5964
- FasterXML__jackson-databind__pr5959
- FasterXML__jackson-databind__pr5943
- FasterXML__jackson-databind__pr5994
- apache__dubbo__pr16395
- FasterXML__jackson-databind__pr5976
- h3js__h3__pr1352
- FasterXML__jackson-dataformat-xml__pr821
- colinhacks__zod__pr6500
- google__gson__pr3057
- FasterXML__jackson-dataformat-xml__pr829
- FasterXML__jackson-databind__pr5947
- google__gson__pr3098
- pallets__click__pr3244
- FasterXML__jackson-databind__pr5983
- pallets__werkzeug__pr3006

Completed 2026-09-27 06:21:05

> [2026-09-27 06:21:05] DONE: 71/71 tasks, 27 flagged (0 non-adoption, 27 real)
