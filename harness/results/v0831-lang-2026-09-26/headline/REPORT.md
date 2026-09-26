# Overnight run: native vs resident prism_init

Started 2026-09-26 13:58:50. 71 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-26 13:58:50] starting: 71 tasks, 0 already done

> [2026-09-26 13:58:50] -- urfave__cli__pr2296 (go) --

## urfave__cli__pr2296 (go)

- native: resolved=True tokens=411339 turns=11 wall_s=65.1
- prism : resolved=True tokens=332648 turns=8 wall_s=43.4 prism_calls=1
- token ratio (prism/native): 0.81x

> [2026-09-26 14:00:54]    native resolved=True tokens=411339 | prism resolved=True tokens=332648 prism_calls=1

> [2026-09-26 14:00:54] -- urfave__cli__pr2309 (go) --

## urfave__cli__pr2309 (go)

- native: resolved=True tokens=475673 turns=11 wall_s=44.8
- prism : resolved=True tokens=987044 turns=17 wall_s=68.5 prism_calls=3
- token ratio (prism/native): 2.08x

**FLAGGED** (token ratio 2.08x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=475673 wall_s=44.8 cost=$0.2325402
  - tools: {'Grep': 3, 'Read': 4, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=True turns=17 tokens=987044 wall_s=68.5 cost=$0.4182342
  - tools: {'mcp__prism__prism': 3, 'Read': 4, 'Grep': 5, 'Edit': 1, 'Bash': 3}

> [2026-09-26 14:03:01]    native resolved=True tokens=475673 | prism resolved=True tokens=987044 prism_calls=3 [FLAGGED]

> [2026-09-26 14:03:01] -- urfave__cli__pr2290 (go) --

## urfave__cli__pr2290 (go)

- native: resolved=True tokens=1167855 turns=25 wall_s=125.2
- prism : resolved=True tokens=366478 turns=8 wall_s=31.4 prism_calls=3
- token ratio (prism/native): 0.31x

**FLAGGED** (token ratio 0.31x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=25 tokens=1167855 wall_s=125.2 cost=$0.45088020000000006
  - tools: {'Grep': 13, 'Bash': 7, 'Read': 3, 'Edit': 1}
- **prism**: resolved=True turns=8 tokens=366478 wall_s=31.4 cost=$0.20114880000000002
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Read': 1, 'Bash': 2}

> [2026-09-26 14:05:52]    native resolved=True tokens=1167855 | prism resolved=True tokens=366478 prism_calls=3 [FLAGGED]

> [2026-09-26 14:05:52] -- urfave__cli__pr2419 (go) --

## urfave__cli__pr2419 (go)

- native: resolved=False tokens=300228 turns=8 wall_s=27.7
- prism : resolved=False tokens=245368 turns=6 wall_s=55.5 prism_calls=1
- token ratio (prism/native): 0.82x

> [2026-09-26 14:07:30]    native resolved=False tokens=300228 | prism resolved=False tokens=245368 prism_calls=1

> [2026-09-26 14:07:30] -- urfave__cli__pr2297 (go) --

## urfave__cli__pr2297 (go)

- native: resolved=True tokens=375346 turns=10 wall_s=37.0
- prism : resolved=True tokens=424144 turns=10 wall_s=44.3 prism_calls=1
- token ratio (prism/native): 1.13x

> [2026-09-26 14:09:06]    native resolved=True tokens=375346 | prism resolved=True tokens=424144 prism_calls=1

> [2026-09-26 14:09:06] -- google__gson__pr3067 (java) --

## google__gson__pr3067 (java)

- native: resolved=True tokens=276987 turns=8 wall_s=123.8
- prism : resolved=True tokens=265282 turns=7 wall_s=26.5 prism_calls=2
- token ratio (prism/native): 0.96x

> [2026-09-26 14:11:54]    native resolved=True tokens=276987 | prism resolved=True tokens=265282 prism_calls=2

> [2026-09-26 14:11:54] -- urfave__cli__pr2311 (go) --

## urfave__cli__pr2311 (go)

- native: resolved=False tokens=242072 turns=7 wall_s=20.2
- prism : resolved=False tokens=148435 turns=4 wall_s=14.1 prism_calls=1
- token ratio (prism/native): 0.61x

**FLAGGED** (token ratio 0.61x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=7 tokens=242072 wall_s=20.2 cost=$0.11901740000000001
  - tools: {'Grep': 1, 'Bash': 3, 'Read': 1, 'Edit': 1}
- **prism**: resolved=False turns=4 tokens=148435 wall_s=14.1 cost=$0.0930486
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 1}

> [2026-09-26 14:12:42]    native resolved=False tokens=242072 | prism resolved=False tokens=148435 prism_calls=1 [FLAGGED]

> [2026-09-26 14:12:42] -- apache__dubbo__pr16350 (java) --

## apache__dubbo__pr16350 (java)

- native: resolved=True tokens=248670 turns=7 wall_s=40.5
- prism : resolved=True tokens=184573 turns=5 wall_s=30.4 prism_calls=1
- token ratio (prism/native): 0.74x

> [2026-09-26 14:18:48]    native resolved=True tokens=248670 | prism resolved=True tokens=184573 prism_calls=1

> [2026-09-26 14:18:48] -- apache__dubbo__pr16348 (java) --

## apache__dubbo__pr16348 (java)

- native: resolved=True tokens=249010 turns=7 wall_s=31.9
- prism : resolved=True tokens=265979 turns=7 wall_s=74.9 prism_calls=3
- token ratio (prism/native): 1.07x

> [2026-09-26 14:25:27]    native resolved=True tokens=249010 | prism resolved=True tokens=265979 prism_calls=3

> [2026-09-26 14:25:27] -- colinhacks__zod__pr6439 (ts) --

## colinhacks__zod__pr6439 (ts)

- native: resolved=True tokens=595841 turns=13 wall_s=73.4
- prism : resolved=True tokens=988114 turns=20 wall_s=80.4 prism_calls=0
- token ratio (prism/native): 1.66x

**FLAGGED** (token ratio 1.66x outside [0.67, 1.5])

**Attribution: NON-ADOPTION.** Prism was never called (0 mcp__prism__prism calls) in this cell -- this result is not attributable to prism's engine or context quality, only to the agent not reaching for the tool.

- **native**: resolved=True turns=13 tokens=595841 wall_s=73.4 cost=$0.26677
  - tools: {'Grep': 2, 'Edit': 1, 'Bash': 8, 'Glob': 1}
- **prism**: resolved=True turns=20 tokens=988114 wall_s=80.4 cost=$0.363625
  - tools: {'Grep': 2, 'Edit': 1, 'Bash': 15, 'Write': 1}

> [2026-09-26 14:28:43]    native resolved=True tokens=595841 | prism resolved=True tokens=988114 prism_calls=0 [FLAGGED]

> [2026-09-26 14:28:43] -- go-chi__chi__pr1085 (go) --

## go-chi__chi__pr1085 (go)

- native: resolved=True tokens=168571 turns=5 wall_s=41.6
- prism : resolved=True tokens=147401 turns=4 wall_s=37.9 prism_calls=1
- token ratio (prism/native): 0.87x

> [2026-09-26 14:30:12]    native resolved=True tokens=168571 | prism resolved=True tokens=147401 prism_calls=1

> [2026-09-26 14:30:12] -- labstack__echo__pr3006 (go) --

## labstack__echo__pr3006 (go)

- native: resolved=True tokens=756951 turns=18 wall_s=78.1
- prism : resolved=True tokens=1496850 turns=22 wall_s=201.5 prism_calls=3
- token ratio (prism/native): 1.98x

**FLAGGED** (token ratio 1.98x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=18 tokens=756951 wall_s=78.1 cost=$0.31072619999999995
  - tools: {'Bash': 7, 'Grep': 6, 'Read': 3, 'Edit': 1}
- **prism**: resolved=True turns=22 tokens=1496850 wall_s=201.5 cost=$0.6562502
  - tools: {'mcp__prism__prism': 3, 'Bash': 11, 'Read': 4, 'Edit': 3}

> [2026-09-26 14:35:07]    native resolved=True tokens=756951 | prism resolved=True tokens=1496850 prism_calls=3 [FLAGGED]

> [2026-09-26 14:35:07] -- colinhacks__zod__pr6298 (ts) --

## colinhacks__zod__pr6298 (ts)

- native: resolved=True tokens=410290 turns=10 wall_s=42.8
- prism : resolved=True tokens=430786 turns=9 wall_s=43.1 prism_calls=1
- token ratio (prism/native): 1.05x

> [2026-09-26 14:37:09]    native resolved=True tokens=410290 | prism resolved=True tokens=430786 prism_calls=1

> [2026-09-26 14:37:09] -- honojs__hono__pr5373 (ts) --

## honojs__hono__pr5373 (ts)

- native: resolved=True tokens=789475 turns=20 wall_s=111.2
- prism : resolved=True tokens=778292 turns=18 wall_s=67.5 prism_calls=1
- token ratio (prism/native): 0.99x

> [2026-09-26 14:40:58]    native resolved=True tokens=789475 | prism resolved=True tokens=778292 prism_calls=1

> [2026-09-26 14:40:58] -- FasterXML__jackson-dataformat-xml__pr825 (java) --

## FasterXML__jackson-dataformat-xml__pr825 (java)

- native: resolved=True tokens=1924427 turns=41 wall_s=355.0
- prism : resolved=True tokens=2432120 turns=37 wall_s=193.9 prism_calls=3
- token ratio (prism/native): 1.26x

> [2026-09-26 14:50:24]    native resolved=True tokens=1924427 | prism resolved=True tokens=2432120 prism_calls=3

> [2026-09-26 14:50:24] -- urfave__cli__pr2440 (go) --

## urfave__cli__pr2440 (go)

- native: resolved=True tokens=928562 turns=21 wall_s=99.6
- prism : resolved=True tokens=395366 turns=8 wall_s=39.2 prism_calls=3
- token ratio (prism/native): 0.43x

**FLAGGED** (token ratio 0.43x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=21 tokens=928562 wall_s=99.6 cost=$0.33888840000000003
  - tools: {'Grep': 5, 'Read': 5, 'Edit': 2, 'Bash': 8}
- **prism**: resolved=True turns=8 tokens=395366 wall_s=39.2 cost=$0.22735
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-26 14:52:57]    native resolved=True tokens=928562 | prism resolved=True tokens=395366 prism_calls=3 [FLAGGED]

> [2026-09-26 14:52:57] -- FasterXML__jackson-databind__pr5977 (java) --

## FasterXML__jackson-databind__pr5977 (java)

- native: resolved=True tokens=2214149 turns=38 wall_s=664.9
- prism : resolved=False tokens=1418293 turns=23 wall_s=289.7 prism_calls=5
- token ratio (prism/native): 0.64x

**FLAGGED** (resolve mismatch, token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=38 tokens=2214149 wall_s=664.9 cost=$1.0880869
  - tools: {'Agent': 1, 'Bash': 22, 'Grep': 5, 'Read': 7, 'Edit': 1, 'Write': 1}
- **prism**: resolved=False turns=23 tokens=1418293 wall_s=289.7 cost=$0.6376609999999999
  - tools: {'mcp__prism__prism': 5, 'Bash': 14, 'Edit': 2, 'Read': 1}

> [2026-09-26 15:10:05]    native resolved=True tokens=2214149 | prism resolved=False tokens=1418293 prism_calls=5 [FLAGGED]

> [2026-09-26 15:10:05] -- colinhacks__zod__pr6129 (ts) --

## colinhacks__zod__pr6129 (ts)

- native: resolved=True tokens=1301678 turns=27 wall_s=114.4
- prism : resolved=False tokens=961304 turns=20 wall_s=68.2 prism_calls=0
- token ratio (prism/native): 0.74x

**FLAGGED** (resolve mismatch)

**Attribution: NON-ADOPTION.** Prism was never called (0 mcp__prism__prism calls) in this cell -- this result is not attributable to prism's engine or context quality, only to the agent not reaching for the tool.

- **native**: resolved=True turns=27 tokens=1301678 wall_s=114.4 cost=$0.4748648000000001
  - tools: {'Grep': 6, 'Read': 2, 'Edit': 2, 'Bash': 15, 'Write': 1}
- **prism**: resolved=False turns=20 tokens=961304 wall_s=68.2 cost=$0.3470712
  - tools: {'Grep': 10, 'Read': 2, 'Edit': 1, 'Bash': 6}

> [2026-09-26 15:13:48]    native resolved=True tokens=1301678 | prism resolved=False tokens=961304 prism_calls=0 [FLAGGED]

> [2026-09-26 15:13:48] -- FasterXML__jackson-databind__pr6186 (java) --

## FasterXML__jackson-databind__pr6186 (java)

- native: resolved=True tokens=425851 turns=12 wall_s=75.4
- prism : resolved=True tokens=228626 turns=6 wall_s=26.2 prism_calls=1
- token ratio (prism/native): 0.54x

**FLAGGED** (token ratio 0.54x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=425851 wall_s=75.4 cost=$0.18019839999999998
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 1, 'Bash': 6}
- **prism**: resolved=True turns=6 tokens=228626 wall_s=26.2 cost=$0.1224082
  - tools: {'mcp__prism__prism': 1, 'Read': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-26 15:16:34]    native resolved=True tokens=425851 | prism resolved=True tokens=228626 prism_calls=1 [FLAGGED]

> [2026-09-26 15:16:34] -- honojs__hono__pr5366 (ts) --

## honojs__hono__pr5366 (ts)

- native: resolved=True tokens=535473 turns=14 wall_s=70.4
- prism : resolved=True tokens=632267 turns=15 wall_s=45.8 prism_calls=1
- token ratio (prism/native): 1.18x

> [2026-09-26 15:19:16]    native resolved=True tokens=535473 | prism resolved=True tokens=632267 prism_calls=1

> [2026-09-26 15:19:16] -- go-chi__chi__pr1029 (go) --

## go-chi__chi__pr1029 (go)

- native: resolved=True tokens=601267 turns=18 wall_s=75.8
- prism : resolved=True tokens=316431 turns=7 wall_s=51.5 prism_calls=2
- token ratio (prism/native): 0.53x

**FLAGGED** (token ratio 0.53x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=18 tokens=601267 wall_s=75.8 cost=$0.24046260000000003
  - tools: {'Grep': 7, 'Read': 3, 'Edit': 3, 'Bash': 4}
- **prism**: resolved=True turns=7 tokens=316431 wall_s=51.5 cost=$0.18323800000000004
  - tools: {'mcp__prism__prism': 2, 'Read': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-26 15:21:33]    native resolved=True tokens=601267 | prism resolved=True tokens=316431 prism_calls=2 [FLAGGED]

> [2026-09-26 15:21:33] -- h3js__h3__pr1273 (ts) --

## h3js__h3__pr1273 (ts)

- native: resolved=False tokens=2913343 turns=49 wall_s=357.9
- prism : resolved=False tokens=2044477 turns=33 wall_s=328.5 prism_calls=7
- token ratio (prism/native): 0.70x

> [2026-09-26 15:33:35]    native resolved=False tokens=2913343 | prism resolved=False tokens=2044477 prism_calls=7

> [2026-09-26 15:33:35] -- apache__dubbo__pr16391 (java) --

## apache__dubbo__pr16391 (java)

- native: resolved=True tokens=714119 turns=15 wall_s=256.1
- prism : resolved=True tokens=1604757 turns=26 wall_s=553.9 prism_calls=4
- token ratio (prism/native): 2.25x

**FLAGGED** (token ratio 2.25x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=714119 wall_s=256.1 cost=$0.3520202
  - tools: {'Read': 3, 'Grep': 3, 'Edit': 1, 'Bash': 7}
- **prism**: resolved=True turns=26 tokens=1604757 wall_s=553.9 cost=$0.6058978
  - tools: {'mcp__prism__prism': 4, 'Read': 1, 'Edit': 3, 'Bash': 16, 'Write': 1}

> [2026-09-26 15:51:58]    native resolved=True tokens=714119 | prism resolved=True tokens=1604757 prism_calls=4 [FLAGGED]

> [2026-09-26 15:51:58] -- go-chi__chi__pr1158 (go) --

## go-chi__chi__pr1158 (go)

- native: resolved=False tokens=623850 turns=17 wall_s=172.7
- prism : resolved=True tokens=555297 turns=12 wall_s=103.2 prism_calls=1
- token ratio (prism/native): 0.89x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=17 tokens=623850 wall_s=172.7 cost=$0.3390776
  - tools: {'Grep': 2, 'Glob': 1, 'Read': 5, 'Edit': 2, 'Bash': 6}
- **prism**: resolved=True turns=12 tokens=555297 wall_s=103.2 cost=$0.3051082
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 8, 'Read': 1}

> [2026-09-26 15:56:43]    native resolved=False tokens=623850 | prism resolved=True tokens=555297 prism_calls=1 [FLAGGED]

> [2026-09-26 15:56:43] -- urfave__cli__pr2355 (go) --

## urfave__cli__pr2355 (go)

- native: resolved=True tokens=4387627 turns=63 wall_s=656.1
- prism : resolved=True tokens=2418159 turns=31 wall_s=241.1 prism_calls=5
- token ratio (prism/native): 0.55x

**FLAGGED** (token ratio 0.55x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=63 tokens=4387627 wall_s=656.1 cost=$1.4933458000000002
  - tools: {'Grep': 15, 'Read': 21, 'Edit': 6, 'Bash': 20}
- **prism**: resolved=True turns=31 tokens=2418159 wall_s=241.1 cost=$0.9498507999999999
  - tools: {'mcp__prism__prism': 5, 'Read': 4, 'Edit': 6, 'Bash': 14, 'Grep': 1}

> [2026-09-26 16:11:56]    native resolved=True tokens=4387627 | prism resolved=True tokens=2418159 prism_calls=5 [FLAGGED]

> [2026-09-26 16:11:56] -- h3js__h3__pr1314 (ts) --

## h3js__h3__pr1314 (ts)

- native: resolved=False tokens=487106 turns=14 wall_s=49.6
- prism : resolved=True tokens=413911 turns=11 wall_s=45.6 prism_calls=5
- token ratio (prism/native): 0.85x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=14 tokens=487106 wall_s=49.6 cost=$0.2179272
  - tools: {'Grep': 6, 'Edit': 1, 'Bash': 6}
- **prism**: resolved=True turns=11 tokens=413911 wall_s=45.6 cost=$0.2101992
  - tools: {'mcp__prism__prism': 5, 'Edit': 1, 'Bash': 4}

> [2026-09-26 16:13:49]    native resolved=False tokens=487106 | prism resolved=True tokens=413911 prism_calls=5 [FLAGGED]

> [2026-09-26 16:13:49] -- FasterXML__jackson-dataformat-xml__pr827 (java) --

## FasterXML__jackson-dataformat-xml__pr827 (java)

- native: resolved=True tokens=3695994 turns=56 wall_s=475.0
- prism : resolved=False tokens=5447715 turns=58 wall_s=1021.3 prism_calls=3
- token ratio (prism/native): 1.47x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=56 tokens=3695994 wall_s=475.0 cost=$1.3743940000000006
  - tools: {'Bash': 35, 'Read': 14, 'Edit': 6}
- **prism**: resolved=False turns=58 tokens=5447715 wall_s=1021.3 cost=$1.9379199999999996
  - tools: {'mcp__prism__prism': 3, 'Read': 12, 'Bash': 32, 'Grep': 3, 'Write': 1, 'Edit': 6}

> [2026-09-26 16:39:02]    native resolved=True tokens=3695994 | prism resolved=False tokens=5447715 prism_calls=3 [FLAGGED]

> [2026-09-26 16:39:02] -- FasterXML__jackson-databind__pr5964 (java) --

## FasterXML__jackson-databind__pr5964 (java)

- native: resolved=True tokens=710002 turns=17 wall_s=126.0
- prism : resolved=True tokens=672210 turns=13 wall_s=213.6 prism_calls=5
- token ratio (prism/native): 0.95x

> [2026-09-26 16:46:06]    native resolved=True tokens=710002 | prism resolved=True tokens=672210 prism_calls=5

> [2026-09-26 16:46:06] -- FasterXML__jackson-databind__pr6155 (java) --

## FasterXML__jackson-databind__pr6155 (java)

- native: resolved=True tokens=286148 turns=8 wall_s=44.7
- prism : resolved=True tokens=234847 turns=7 wall_s=71.3 prism_calls=1
- token ratio (prism/native): 0.82x

> [2026-09-26 16:49:04]    native resolved=True tokens=286148 | prism resolved=True tokens=234847 prism_calls=1

> [2026-09-26 16:49:04] -- FasterXML__jackson-databind__pr6138 (java) --

## FasterXML__jackson-databind__pr6138 (java)

- native: resolved=True tokens=431436 turns=10 wall_s=59.7
- prism : resolved=True tokens=322207 turns=7 wall_s=33.1 prism_calls=1
- token ratio (prism/native): 0.75x

> [2026-09-26 16:52:02]    native resolved=True tokens=431436 | prism resolved=True tokens=322207 prism_calls=1

> [2026-09-26 16:52:02] -- honojs__hono__pr5164 (ts) --

## honojs__hono__pr5164 (ts)

- native: resolved=True tokens=444543 turns=12 wall_s=64.1
- prism : resolved=True tokens=743861 turns=17 wall_s=113.1 prism_calls=1
- token ratio (prism/native): 1.67x

**FLAGGED** (token ratio 1.67x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=444543 wall_s=64.1 cost=$0.2018182
  - tools: {'Grep': 1, 'Read': 1, 'Edit': 2, 'Bash': 7}
- **prism**: resolved=True turns=17 tokens=743861 wall_s=113.1 cost=$0.2977214
  - tools: {'mcp__prism__prism': 1, 'Read': 2, 'Edit': 2, 'Bash': 11}

> [2026-09-26 16:55:46]    native resolved=True tokens=444543 | prism resolved=True tokens=743861 prism_calls=1 [FLAGGED]

> [2026-09-26 16:55:46] -- colinhacks__zod__pr6144 (ts) --

## colinhacks__zod__pr6144 (ts)

- native: resolved=True tokens=576815 turns=13 wall_s=60.7
- prism : resolved=True tokens=634566 turns=13 wall_s=65.8 prism_calls=2
- token ratio (prism/native): 1.10x

> [2026-09-26 16:58:32]    native resolved=True tokens=576815 | prism resolved=True tokens=634566 prism_calls=2

> [2026-09-26 16:58:32] -- honojs__hono__pr5199 (ts) --

## honojs__hono__pr5199 (ts)

- native: resolved=True tokens=691045 turns=17 wall_s=188.9
- prism : resolved=True tokens=445286 turns=10 wall_s=62.2 prism_calls=2
- token ratio (prism/native): 0.64x

**FLAGGED** (token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=17 tokens=691045 wall_s=188.9 cost=$0.2859900000000001
  - tools: {'Read': 4, 'Edit': 2, 'Bash': 10}
- **prism**: resolved=True turns=10 tokens=445286 wall_s=62.2 cost=$0.213261
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 5, 'Read': 1}

> [2026-09-26 17:03:27]    native resolved=True tokens=691045 | prism resolved=True tokens=445286 prism_calls=2 [FLAGGED]

> [2026-09-26 17:03:27] -- google__gson__pr3116 (java) --

## google__gson__pr3116 (java)

- native: resolved=False tokens=1012148 turns=20 wall_s=235.3
- prism : resolved=False tokens=1094968 turns=21 wall_s=172.2 prism_calls=5
- token ratio (prism/native): 1.08x

> [2026-09-26 17:10:32]    native resolved=False tokens=1012148 | prism resolved=False tokens=1094968 prism_calls=5

> [2026-09-26 17:10:32] -- FasterXML__jackson-databind__pr5959 (java) --

## FasterXML__jackson-databind__pr5959 (java)

- native: resolved=False tokens=2356421 turns=38 wall_s=428.0
- prism : resolved=False tokens=3551520 turns=46 wall_s=421.2 prism_calls=11
- token ratio (prism/native): 1.51x

**FLAGGED** (token ratio 1.51x outside [0.67, 1.5])

**Attribution: prism WAS called (11x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=38 tokens=2356421 wall_s=428.0 cost=$0.9075280000000001
  - tools: {'Bash': 15, 'Grep': 9, 'Read': 7, 'Edit': 6}
- **prism**: resolved=False turns=46 tokens=3551520 wall_s=421.2 cost=$1.2274923999999996
  - tools: {'mcp__prism__prism': 10, 'Edit': 4, 'Bash': 28, 'mcp__prism__lookup': 1, 'Read': 2}

> [2026-09-26 17:26:10]    native resolved=False tokens=2356421 | prism resolved=False tokens=3551520 prism_calls=11 [FLAGGED]

> [2026-09-26 17:26:10] -- FasterXML__jackson-databind__pr5943 (java) --

## FasterXML__jackson-databind__pr5943 (java)

- native: resolved=True tokens=1406900 turns=28 wall_s=160.0
- prism : resolved=True tokens=2372143 turns=43 wall_s=242.3 prism_calls=3
- token ratio (prism/native): 1.69x

**FLAGGED** (token ratio 1.69x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=28 tokens=1406900 wall_s=160.0 cost=$0.5183255999999998
  - tools: {'Grep': 3, 'Read': 1, 'Edit': 2, 'Bash': 19, 'Write': 1, 'ScheduleWakeup': 1}
- **prism**: resolved=True turns=43 tokens=2372143 wall_s=242.3 cost=$0.7911208000000003
  - tools: {'mcp__prism__prism': 3, 'Read': 1, 'Edit': 1, 'Bash': 37}

> [2026-09-26 17:34:17]    native resolved=True tokens=1406900 | prism resolved=True tokens=2372143 prism_calls=3 [FLAGGED]

> [2026-09-26 17:34:17] -- google__gson__pr3112 (java) --

## google__gson__pr3112 (java)

- native: resolved=False tokens=472316 turns=15 wall_s=60.3
- prism : resolved=False tokens=448230 turns=10 wall_s=39.7 prism_calls=1
- token ratio (prism/native): 0.95x

> [2026-09-26 17:36:14]    native resolved=False tokens=472316 | prism resolved=False tokens=448230 prism_calls=1

> [2026-09-26 17:36:14] -- FasterXML__jackson-databind__pr5994 (java) --

## FasterXML__jackson-databind__pr5994 (java)

- native: resolved=False tokens=472335 turns=13 wall_s=37.5
- prism : resolved=False tokens=1893684 turns=36 wall_s=278.0 prism_calls=2
- token ratio (prism/native): 4.01x

**FLAGGED** (token ratio 4.01x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=13 tokens=472335 wall_s=37.5 cost=$0.19044660000000002
  - tools: {'Grep': 4, 'Read': 1, 'Edit': 3, 'Bash': 4}
- **prism**: resolved=False turns=36 tokens=1893684 wall_s=278.0 cost=$0.6627992000000001
  - tools: {'mcp__prism__prism': 2, 'Read': 2, 'Edit': 3, 'Bash': 28}

> [2026-09-26 17:46:19]    native resolved=False tokens=472335 | prism resolved=False tokens=1893684 prism_calls=2 [FLAGGED]

> [2026-09-26 17:46:19] -- apache__dubbo__pr16395 (java) --

## apache__dubbo__pr16395 (java)

- native: resolved=False tokens=871461 turns=19 wall_s=223.5
- prism : resolved=False tokens=1317844 turns=20 wall_s=468.6 prism_calls=5
- token ratio (prism/native): 1.51x

**FLAGGED** (token ratio 1.51x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=19 tokens=871461 wall_s=223.5 cost=$0.4232306
  - tools: {'Grep': 7, 'Read': 3, 'Edit': 1, 'Bash': 7}
- **prism**: resolved=False turns=20 tokens=1317844 wall_s=468.6 cost=$0.6957974
  - tools: {'mcp__prism__prism': 5, 'Read': 3, 'Grep': 3, 'Edit': 1, 'Bash': 7}

> [2026-09-26 18:03:08]    native resolved=False tokens=871461 | prism resolved=False tokens=1317844 prism_calls=5 [FLAGGED]

> [2026-09-26 18:03:08] -- honojs__hono__pr5311 (ts) --

## honojs__hono__pr5311 (ts)

- native: resolved=True tokens=569238 turns=17 wall_s=57.2
- prism : resolved=True tokens=455461 turns=14 wall_s=66.9 prism_calls=3
- token ratio (prism/native): 0.80x

> [2026-09-26 18:06:00]    native resolved=True tokens=569238 | prism resolved=True tokens=455461 prism_calls=3

> [2026-09-26 18:06:00] -- urllib3__urllib3__pr5020 (python) --

## urllib3__urllib3__pr5020 (python)

- native: resolved=False tokens=2169907 turns=46 wall_s=203.7
- prism : resolved=False tokens=2521139 turns=35 wall_s=281.0 prism_calls=6
- token ratio (prism/native): 1.16x

> [2026-09-26 18:14:39]    native resolved=False tokens=2169907 | prism resolved=False tokens=2521139 prism_calls=6

> [2026-09-26 18:14:39] -- go-chi__chi__pr1148 (go) --

## go-chi__chi__pr1148 (go)

- native: resolved=False tokens=1839672 turns=37 wall_s=269.4
- prism : resolved=False tokens=1343028 turns=21 wall_s=292.5 prism_calls=10
- token ratio (prism/native): 0.73x

> [2026-09-26 18:24:10]    native resolved=False tokens=1839672 | prism resolved=False tokens=1343028 prism_calls=10

> [2026-09-26 18:24:10] -- google__gson__pr3000 (java) --

## google__gson__pr3000 (java)

- native: resolved=True tokens=936464 turns=22 wall_s=79.2
- prism : resolved=True tokens=316217 turns=8 wall_s=34.4 prism_calls=1
- token ratio (prism/native): 0.34x

**FLAGGED** (token ratio 0.34x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=22 tokens=936464 wall_s=79.2 cost=$0.3554996
  - tools: {'Grep': 4, 'Read': 4, 'Edit': 7, 'Bash': 6}
- **prism**: resolved=True turns=8 tokens=316217 wall_s=34.4 cost=$0.1568054
  - tools: {'mcp__prism__prism': 1, 'Edit': 3, 'Bash': 3}

> [2026-09-26 18:26:21]    native resolved=True tokens=936464 | prism resolved=True tokens=316217 prism_calls=1 [FLAGGED]

> [2026-09-26 18:26:21] -- FasterXML__jackson-databind__pr5976 (java) --
