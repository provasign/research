# Overnight run: native vs resident prism_init

Started 2026-09-28 00:25:18. 32 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-28 00:25:18] starting: 32 tasks, 0 already done

> [2026-09-28 00:25:18] -- wide__chi__Routes_Match (go) --

## wide__chi__Routes_Match (go)

- native: resolved=True tokens=520534 turns=21 wall_s=63.1
- prism : resolved=True tokens=495591 turns=28 wall_s=90.6 prism_calls=7
- token ratio (prism/native): 0.95x

> [2026-09-28 00:29:16]    native resolved=True tokens=520534 | prism resolved=True tokens=495591 prism_calls=7

> [2026-09-28 00:29:16] -- wide__click__Command_invoke (python) --

## wide__click__Command_invoke (python)

- native: resolved=True tokens=1265230 turns=29 wall_s=130.3
- prism : resolved=True tokens=1602898 turns=31 wall_s=470.5 prism_calls=12
- token ratio (prism/native): 1.27x

> [2026-09-28 00:40:20]    native resolved=True tokens=1265230 | prism resolved=True tokens=1602898 prism_calls=12

> [2026-09-28 00:40:20] -- wide__h3__EventStream_push (ts) --

## wide__h3__EventStream_push (ts)

- native: resolved=False tokens=823766 turns=23 wall_s=73.3
- prism : resolved=False tokens=1713989 turns=36 wall_s=126.5 prism_calls=3
- token ratio (prism/native): 2.08x

**FLAGGED** (token ratio 2.08x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=23 tokens=823766 wall_s=73.3 cost=$0.37400500000000003
  - tools: {'Grep': 8, 'Read': 5, 'Edit': 2, 'Bash': 7}
- **prism**: resolved=False turns=36 tokens=1713989 wall_s=126.5 cost=$0.5966733999999999
  - tools: {'mcp__prism__prism': 3, 'Grep': 9, 'Read': 4, 'Edit': 13, 'Bash': 6}

> [2026-09-28 00:44:03]    native resolved=False tokens=823766 | prism resolved=False tokens=1713989 prism_calls=3 [FLAGGED]

> [2026-09-28 00:44:03] -- wide__werkzeug__HTTPException_get_headers (python) --

## wide__werkzeug__HTTPException_get_headers (python)

- native: resolved=True tokens=617740 turns=19 wall_s=70.0
- prism : resolved=True tokens=1606832 turns=35 wall_s=234.7 prism_calls=7
- token ratio (prism/native): 2.60x

**FLAGGED** (token ratio 2.60x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=19 tokens=617740 wall_s=70.0 cost=$0.240711
  - tools: {'Grep': 4, 'Bash': 13, 'Read': 1}
- **prism**: resolved=True turns=35 tokens=1606832 wall_s=234.7 cost=$0.5563351999999998
  - tools: {'mcp__prism__prism': 7, 'Read': 3, 'Edit': 7, 'Bash': 17}

> [2026-09-28 00:49:35]    native resolved=True tokens=617740 | prism resolved=True tokens=1606832 prism_calls=7 [FLAGGED]

> [2026-09-28 00:49:35] -- wide__click__ClickException_format_message (python) --

## wide__click__ClickException_format_message (python)

- native: resolved=True tokens=341398 turns=11 wall_s=44.4
- prism : resolved=True tokens=508868 turns=12 wall_s=52.7 prism_calls=4
- token ratio (prism/native): 1.49x

> [2026-09-28 00:51:38]    native resolved=True tokens=341398 | prism resolved=True tokens=508868 prism_calls=4

> [2026-09-28 00:51:38] -- wide__rich__Highlighter_highlight (python) --

## wide__rich__Highlighter_highlight (python)

- native: resolved=True tokens=1096999 turns=24 wall_s=95.4
- prism : resolved=True tokens=1771075 turns=32 wall_s=134.9 prism_calls=4
- token ratio (prism/native): 1.61x

**FLAGGED** (token ratio 1.61x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=24 tokens=1096999 wall_s=95.4 cost=$0.431344
  - tools: {'Grep': 2, 'Read': 5, 'Edit': 5, 'Bash': 11}
- **prism**: resolved=True turns=32 tokens=1771075 wall_s=134.9 cost=$0.6810295999999998
  - tools: {'mcp__prism__prism': 4, 'Read': 4, 'Edit': 7, 'Bash': 11, 'Grep': 5}

> [2026-09-28 00:55:44]    native resolved=True tokens=1096999 | prism resolved=True tokens=1771075 prism_calls=4 [FLAGGED]

> [2026-09-28 00:55:44] -- wide__werkzeug__BaseConverter_to_url (python) --

## wide__werkzeug__BaseConverter_to_url (python)

- native: resolved=True tokens=816992 turns=20 wall_s=208.4
- prism : resolved=True tokens=1471683 turns=31 wall_s=133.3 prism_calls=3
- token ratio (prism/native): 1.80x

**FLAGGED** (token ratio 1.80x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=20 tokens=816992 wall_s=208.4 cost=$0.30303159999999996
  - tools: {'Grep': 2, 'Read': 5, 'Bash': 11, 'Edit': 1}
- **prism**: resolved=True turns=31 tokens=1471683 wall_s=133.3 cost=$0.5026902000000001
  - tools: {'mcp__prism__prism': 3, 'Grep': 2, 'Read': 4, 'Edit': 11, 'Bash': 10}

> [2026-09-28 01:01:55]    native resolved=True tokens=816992 | prism resolved=True tokens=1471683 prism_calls=3 [FLAGGED]

> [2026-09-28 01:01:55] -- wide__jackson-databind__TypeDeserializer_getTypeInclusion (java) --

## wide__jackson-databind__TypeDeserializer_getTypeInclusion (java)

- native: resolved=True tokens=882514 turns=24 wall_s=136.6
- prism : resolved=True tokens=1195701 turns=24 wall_s=166.7 prism_calls=3
- token ratio (prism/native): 1.35x

> [2026-09-28 01:11:34]    native resolved=True tokens=882514 | prism resolved=True tokens=1195701 prism_calls=3

> [2026-09-28 01:11:34] -- wide__gin__ResponseWriter_Status (go) --

## wide__gin__ResponseWriter_Status (go)

- native: resolved=True tokens=566292 turns=19 wall_s=51.1
- prism : resolved=True tokens=850005 turns=32 wall_s=95.1 prism_calls=6
- token ratio (prism/native): 1.50x

**FLAGGED** (token ratio 1.50x outside [0.67, 1.5])

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=19 tokens=566292 wall_s=51.1 cost=$0.23033940000000003
  - tools: {'Grep': 6, 'Read': 1, 'Edit': 5, 'Bash': 6}
- **prism**: resolved=True turns=32 tokens=850005 wall_s=95.1 cost=$0.3607622
  - tools: {'mcp__prism__prism': 6, 'Edit': 15, 'Read': 6, 'Bash': 4}

> [2026-09-28 01:14:24]    native resolved=True tokens=566292 | prism resolved=True tokens=850005 prism_calls=6 [FLAGGED]

> [2026-09-28 01:14:24] -- wide__h3__H3Route_handler (ts) --

## wide__h3__H3Route_handler (ts)

- native: resolved=True tokens=2409527 turns=39 wall_s=132.2
- prism : resolved=True tokens=1869776 turns=43 wall_s=147.5 prism_calls=14
- token ratio (prism/native): 0.78x

> [2026-09-28 01:19:24]    native resolved=True tokens=2409527 | prism resolved=True tokens=1869776 prism_calls=14

> [2026-09-28 01:19:24] -- wide__click__Group_get_command (python) --

## wide__click__Group_get_command (python)

- native: resolved=False tokens=1000914 turns=32 wall_s=135.8
- prism : resolved=True tokens=639298 turns=15 wall_s=58.5 prism_calls=2
- token ratio (prism/native): 0.64x

**FLAGGED** (resolve mismatch, token ratio 0.64x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=32 tokens=1000914 wall_s=135.8 cost=$0.401949
  - tools: {'Grep': 10, 'Read': 6, 'Bash': 7, 'Edit': 8}
- **prism**: resolved=True turns=15 tokens=639298 wall_s=58.5 cost=$0.2600184
  - tools: {'mcp__prism__prism': 2, 'Bash': 11, 'Read': 1}

> [2026-09-28 01:23:06]    native resolved=False tokens=1000914 | prism resolved=True tokens=639298 prism_calls=2 [FLAGGED]

> [2026-09-28 01:23:06] -- wide__hono__SetHeadersOptions_append (ts) --

## wide__hono__SetHeadersOptions_append (ts)

- native: resolved=True tokens=439943 turns=15 wall_s=45.1
- prism : resolved=True tokens=1201244 turns=34 wall_s=122.1 prism_calls=2
- token ratio (prism/native): 2.73x

**FLAGGED** (token ratio 2.73x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=439943 wall_s=45.1 cost=$0.2072862
  - tools: {'Grep': 4, 'Read': 2, 'Edit': 3, 'Bash': 5}
- **prism**: resolved=True turns=34 tokens=1201244 wall_s=122.1 cost=$0.44290619999999997
  - tools: {'mcp__prism__prism': 2, 'Grep': 12, 'Edit': 11, 'Read': 1, 'Bash': 7}

> [2026-09-28 01:26:51]    native resolved=True tokens=439943 | prism resolved=True tokens=1201244 prism_calls=2 [FLAGGED]

> [2026-09-28 01:26:51] -- wide__echo__HTTPStatusCoder_StatusCode (go) --

## wide__echo__HTTPStatusCoder_StatusCode (go)

- native: resolved=False tokens=833160 turns=31 wall_s=90.9
- prism : resolved=False tokens=1040151 turns=22 wall_s=74.4 prism_calls=3
- token ratio (prism/native): 1.25x

> [2026-09-28 01:29:54]    native resolved=False tokens=833160 | prism resolved=False tokens=1040151 prism_calls=3

> [2026-09-28 01:29:54] -- wide__rich__ProgressColumn_render (python) --

## wide__rich__ProgressColumn_render (python)

- native: resolved=True tokens=711621 turns=23 wall_s=70.2
- prism : resolved=True tokens=1300905 turns=34 wall_s=103.7 prism_calls=14
- token ratio (prism/native): 1.83x

**FLAGGED** (token ratio 1.83x outside [0.67, 1.5])

**Attribution: prism WAS called (14x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=23 tokens=711621 wall_s=70.2 cost=$0.3181203999999999
  - tools: {'Bash': 11, 'Grep': 7, 'Read': 2, 'Edit': 2}
- **prism**: resolved=True turns=34 tokens=1300905 wall_s=103.7 cost=$0.5204870000000001
  - tools: {'mcp__prism__prism': 13, 'mcp__prism__read': 1, 'Grep': 1, 'Read': 2, 'Bash': 10, 'Edit': 6}

> [2026-09-28 01:33:05]    native resolved=True tokens=711621 | prism resolved=True tokens=1300905 prism_calls=14 [FLAGGED]

> [2026-09-28 01:33:05] -- wide__hono__Hono_basePath (ts) --

## wide__hono__Hono_basePath (ts)

- native: resolved=True tokens=822734 turns=25 wall_s=79.7
- prism : resolved=False tokens=662254 turns=16 wall_s=75.2 prism_calls=4
- token ratio (prism/native): 0.80x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=25 tokens=822734 wall_s=79.7 cost=$0.3224914000000001
  - tools: {'Grep': 8, 'Bash': 10, 'Read': 3, 'Edit': 3}
- **prism**: resolved=False turns=16 tokens=662254 wall_s=75.2 cost=$0.263541
  - tools: {'mcp__prism__prism': 4, 'Read': 1, 'Edit': 2, 'Bash': 8}

> [2026-09-28 01:36:30]    native resolved=True tokens=822734 | prism resolved=False tokens=662254 prism_calls=4 [FLAGGED]

> [2026-09-28 01:36:30] -- wide__werkzeug__Response_get_data (python) --

## wide__werkzeug__Response_get_data (python)

- native: resolved=True tokens=1730605 turns=68 wall_s=521.8
- prism : resolved=True tokens=1280286 turns=44 wall_s=175.3 prism_calls=6
- token ratio (prism/native): 0.74x

> [2026-09-28 01:48:37]    native resolved=True tokens=1730605 | prism resolved=True tokens=1280286 prism_calls=6

> [2026-09-28 01:48:37] -- wide__hono__ConnInfo_remote (ts) --

## wide__hono__ConnInfo_remote (ts)

- native: resolved=True tokens=973401 turns=41 wall_s=118.5
- prism : resolved=True tokens=1418308 turns=66 wall_s=195.5 prism_calls=5
- token ratio (prism/native): 1.46x

> [2026-09-28 01:54:43]    native resolved=True tokens=973401 | prism resolved=True tokens=1418308 prism_calls=5

> [2026-09-28 01:54:43] -- wide__jackson-databind__TypeDeserializer_forProperty (java) --

## wide__jackson-databind__TypeDeserializer_forProperty (java)

- native: resolved=True tokens=611235 turns=37 wall_s=148.6
- prism : resolved=True tokens=589765 turns=30 wall_s=170.2 prism_calls=8
- token ratio (prism/native): 0.96x

> [2026-09-28 02:04:38]    native resolved=True tokens=611235 | prism resolved=True tokens=589765 prism_calls=8

> [2026-09-28 02:04:38] -- wide__jackson-databind__ResolvableDeserializer_resolve (java) --

## wide__jackson-databind__ResolvableDeserializer_resolve (java)

- native: resolved=True tokens=1573867 turns=44 wall_s=342.1
- prism : resolved=True tokens=1190481 turns=36 wall_s=178.5 prism_calls=7
- token ratio (prism/native): 0.76x

> [2026-09-28 02:17:55]    native resolved=True tokens=1573867 | prism resolved=True tokens=1190481 prism_calls=7

> [2026-09-28 02:17:55] -- wide__cli__Flag_ValueFromContext (go) --

## wide__cli__Flag_ValueFromContext (go)

- native: resolved=False tokens=371054 turns=11 wall_s=21.4
- prism : resolved=True tokens=397403 turns=10 wall_s=40.0 prism_calls=1
- token ratio (prism/native): 1.07x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=11 tokens=371054 wall_s=21.4 cost=$0.14735959999999998
  - tools: {'Bash': 6, 'Grep': 4}
- **prism**: resolved=True turns=10 tokens=397403 wall_s=40.0 cost=$0.17705520000000002
  - tools: {'mcp__prism__prism': 1, 'Bash': 5, 'Grep': 3}

> [2026-09-28 02:19:10]    native resolved=False tokens=371054 | prism resolved=True tokens=397403 prism_calls=1 [FLAGGED]

> [2026-09-28 02:19:10] -- wide__jackson-databind__SettableBeanProperty_set (java) --

## wide__jackson-databind__SettableBeanProperty_set (java)

- native: resolved=True tokens=90224 turns=2 wall_s=249.4
- prism : resolved=False tokens=1150446 turns=56 wall_s=204.7 prism_calls=6
- token ratio (prism/native): 12.75x

**FLAGGED** (resolve mismatch, token ratio 12.75x outside [0.67, 1.5])

**Attribution: prism WAS called (6x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=2 tokens=90224 wall_s=249.4 cost=$0.7604657000000002
  - tools: {'Bash': 7, 'Agent': 1}
- **prism**: resolved=False turns=56 tokens=1150446 wall_s=204.7 cost=$0.6049144000000001
  - tools: {'mcp__prism__prism': 6, 'Read': 19, 'Edit': 24, 'Bash': 6}

> [2026-09-28 02:31:18]    native resolved=True tokens=90224 | prism resolved=False tokens=1150446 prism_calls=6 [FLAGGED]

> [2026-09-28 02:31:18] -- wide__hono__Router_match (ts) --

## wide__hono__Router_match (ts)

- native: resolved=True tokens=1600544 turns=61 wall_s=185.2
- prism : resolved=False tokens=1943861 turns=58 wall_s=203.3 prism_calls=5
- token ratio (prism/native): 1.21x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=61 tokens=1600544 wall_s=185.2 cost=$0.6582528000000003
  - tools: {'Grep': 21, 'Read': 13, 'Edit': 19, 'Bash': 7}
- **prism**: resolved=False turns=58 tokens=1943861 wall_s=203.3 cost=$0.8305877999999999
  - tools: {'mcp__prism__prism': 5, 'Read': 21, 'Edit': 23, 'Grep': 2, 'Bash': 6}

> [2026-09-28 02:38:42]    native resolved=True tokens=1600544 | prism resolved=False tokens=1943861 prism_calls=5 [FLAGGED]

> [2026-09-28 02:38:42] -- wide__gin__Binding_Name (go) --

## wide__gin__Binding_Name (go)

- native: resolved=True tokens=1260913 turns=56 wall_s=123.9
- prism : resolved=True tokens=1060794 turns=40 wall_s=111.5 prism_calls=12
- token ratio (prism/native): 0.84x

> [2026-09-28 02:43:01]    native resolved=True tokens=1260913 | prism resolved=True tokens=1060794 prism_calls=12

> [2026-09-28 02:43:01] -- wide__cli__Command_Subcommands (go) --

## wide__cli__Command_Subcommands (go)

- native: resolved=True tokens=509314 turns=14 wall_s=41.0
- prism : resolved=True tokens=1453636 turns=29 wall_s=101.2 prism_calls=7
- token ratio (prism/native): 2.85x

**FLAGGED** (token ratio 2.85x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=14 tokens=509314 wall_s=41.0 cost=$0.20430240000000002
  - tools: {'Bash': 10, 'Grep': 3}
- **prism**: resolved=True turns=29 tokens=1453636 wall_s=101.2 cost=$0.4920603999999999
  - tools: {'mcp__prism__prism': 7, 'Edit': 2, 'Bash': 19}

> [2026-09-28 02:45:36]    native resolved=True tokens=509314 | prism resolved=True tokens=1453636 prism_calls=7 [FLAGGED]

> [2026-09-28 02:45:36] -- wide__zod__ZodRegistry_get (ts) --

## wide__zod__ZodRegistry_get (ts)

- native: resolved=True tokens=3054058 turns=52 wall_s=247.5
- prism : resolved=True tokens=5342709 turns=79 wall_s=274.2 prism_calls=5
- token ratio (prism/native): 1.75x

**FLAGGED** (token ratio 1.75x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=52 tokens=3054058 wall_s=247.5 cost=$0.9453401999999997
  - tools: {'Grep': 13, 'Read': 7, 'Edit': 22, 'Bash': 9}
- **prism**: resolved=True turns=79 tokens=5342709 wall_s=274.2 cost=$1.4931298
  - tools: {'mcp__prism__prism': 5, 'Edit': 31, 'Read': 15, 'Grep': 21, 'Bash': 6}

> [2026-09-28 02:55:15]    native resolved=True tokens=3054058 | prism resolved=True tokens=5342709 prism_calls=5 [FLAGGED]

> [2026-09-28 02:55:15] -- wide__echo__Router_Route (go) --

## wide__echo__Router_Route (go)

- native: resolved=True tokens=695013 turns=23 wall_s=71.3
- prism : resolved=True tokens=932348 turns=21 wall_s=72.0 prism_calls=2
- token ratio (prism/native): 1.34x

> [2026-09-28 02:57:56]    native resolved=True tokens=695013 | prism resolved=True tokens=932348 prism_calls=2

> [2026-09-28 02:57:56] -- wide__jackson-core__BufferRecyclerPool (java) --

## wide__jackson-core__BufferRecyclerPool (java)

- native: resolved=True tokens=787107 turns=17 wall_s=100.3
- prism : resolved=True tokens=2060209 turns=29 wall_s=137.0 prism_calls=3
- token ratio (prism/native): 2.62x

**FLAGGED** (token ratio 2.62x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=17 tokens=787107 wall_s=100.3 cost=$0.36469700000000005
  - tools: {'Bash': 14, 'Read': 2}
- **prism**: resolved=True turns=29 tokens=2060209 wall_s=137.0 cost=$0.8455576
  - tools: {'mcp__prism__prism': 3, 'Read': 8, 'Grep': 2, 'Bash': 15}

> [2026-09-28 03:02:40]    native resolved=True tokens=787107 | prism resolved=True tokens=2060209 prism_calls=3 [FLAGGED]

> [2026-09-28 03:02:40] -- wide__zod__ZodTypeInternals_parse (ts) --

## wide__zod__ZodTypeInternals_parse (ts)

- native: resolved=True tokens=1723888 turns=32 wall_s=131.6
- prism : resolved=True tokens=1528408 turns=25 wall_s=142.7 prism_calls=7
- token ratio (prism/native): 0.89x

> [2026-09-28 03:08:09]    native resolved=True tokens=1723888 | prism resolved=True tokens=1528408 prism_calls=7

> [2026-09-28 03:08:09] -- wide__jackson-databind__ContextualSerializer_createContextual (java) --

## wide__jackson-databind__ContextualSerializer_createContextual (java)

- native: resolved=True tokens=590142 turns=15 wall_s=314.2
- prism : resolved=True tokens=109052 turns=2 wall_s=232.7 prism_calls=2
- token ratio (prism/native): 0.18x

**FLAGGED** (token ratio 0.18x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=15 tokens=590142 wall_s=314.2 cost=$0.8500230000000001
  - tools: {'Grep': 6, 'Read': 1, 'Agent': 1, 'Bash': 6}
- **prism**: resolved=True turns=2 tokens=109052 wall_s=232.7 cost=$0.6342709999999999
  - tools: {'mcp__prism__prism': 2, 'Agent': 1, 'Bash': 1}

> [2026-09-28 03:21:52]    native resolved=True tokens=590142 | prism resolved=True tokens=109052 prism_calls=2 [FLAGGED]

> [2026-09-28 03:21:52] -- wide__jackson-databind__ContextualDeserializer_createContextual (java) --

## wide__jackson-databind__ContextualDeserializer_createContextual (java)

- native: resolved=True tokens=1584681 turns=32 wall_s=256.3
- prism : resolved=True tokens=1547971 turns=42 wall_s=207.8 prism_calls=3
- token ratio (prism/native): 0.98x

> [2026-09-28 03:34:11]    native resolved=True tokens=1584681 | prism resolved=True tokens=1547971 prism_calls=3

> [2026-09-28 03:34:11] -- wide__jackson-databind__JsonSerializer_isEmpty (java) --

## wide__jackson-databind__JsonSerializer_isEmpty (java)

- native: resolved=True tokens=1277746 turns=25 wall_s=146.3
- prism : resolved=True tokens=766297 turns=21 wall_s=203.3 prism_calls=7
- token ratio (prism/native): 0.60x

**FLAGGED** (token ratio 0.60x outside [0.67, 1.5])

**Attribution: prism WAS called (7x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=25 tokens=1277746 wall_s=146.3 cost=$0.5021556
  - tools: {'Bash': 14, 'Grep': 6, 'Read': 2, 'Edit': 2}
- **prism**: resolved=True turns=21 tokens=766297 wall_s=203.3 cost=$0.5479411999999999
  - tools: {'mcp__prism__prism': 6, 'mcp__prism__read': 1, 'Read': 9, 'Bash': 4}

> [2026-09-28 03:44:36]    native resolved=True tokens=1277746 | prism resolved=True tokens=766297 prism_calls=7 [FLAGGED]

> [2026-09-28 03:44:36] -- wide__jackson-databind__JsonParser_getCurrentToken (java) --

## wide__jackson-databind__JsonParser_getCurrentToken (java)

- native: resolved=True tokens=481934 turns=13 wall_s=65.9
- prism : resolved=True tokens=823951 turns=19 wall_s=167.8 prism_calls=8
- token ratio (prism/native): 1.71x

**FLAGGED** (token ratio 1.71x outside [0.67, 1.5])

**Attribution: prism WAS called (8x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=13 tokens=481934 wall_s=65.9 cost=$0.24127859999999998
  - tools: {'Bash': 7, 'Grep': 5}
- **prism**: resolved=True turns=19 tokens=823951 wall_s=167.8 cost=$0.41059539999999994
  - tools: {'mcp__prism__prism': 8, 'Bash': 10}

> [2026-09-28 03:51:20]    native resolved=True tokens=481934 | prism resolved=True tokens=823951 prism_calls=8 [FLAGGED]


# SUMMARY

32/32 tasks completed.

- native resolved: 28/32
- prism  resolved: 27/32
- native tokens total: 32065090
- prism  tokens total: 41526195 (1.30x native)
- flagged cells: 18 (0 non-adoption, 18 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- wide__h3__EventStream_push
- wide__werkzeug__HTTPException_get_headers
- wide__rich__Highlighter_highlight
- wide__werkzeug__BaseConverter_to_url
- wide__gin__ResponseWriter_Status
- wide__click__Group_get_command
- wide__hono__SetHeadersOptions_append
- wide__rich__ProgressColumn_render
- wide__hono__Hono_basePath
- wide__cli__Flag_ValueFromContext
- wide__jackson-databind__SettableBeanProperty_set
- wide__hono__Router_match
- wide__cli__Command_Subcommands
- wide__zod__ZodRegistry_get
- wide__jackson-core__BufferRecyclerPool
- wide__jackson-databind__ContextualSerializer_createContextual
- wide__jackson-databind__JsonSerializer_isEmpty
- wide__jackson-databind__JsonParser_getCurrentToken

Completed 2026-09-28 03:51:20

> [2026-09-28 03:51:20] DONE: 32/32 tasks, 18 flagged (0 non-adoption, 18 real)
