# Overnight run: native vs resident prism_init

Started 2026-09-28 17:03:15. 32 tasks, model=claude-sonnet-5-5, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-28 17:03:15] starting: 32 tasks, 0 already done

> [2026-09-28 17:03:15] -- wide__chi__Routes_Match (go) --

## wide__chi__Routes_Match (go)

- native: resolved=True tokens=84472 turns=5 wall_s=37.8
- prism : resolved=True tokens=104005 turns=6 wall_s=65.2 prism_calls=2
- token ratio (prism/native): 1.23x

> [2026-09-28 17:06:00]    native resolved=True tokens=84472 | prism resolved=True tokens=104005 prism_calls=2

> [2026-09-28 17:06:00] -- wide__click__Command_invoke (python) --

## wide__click__Command_invoke (python)

- native: resolved=True tokens=343338 turns=11 wall_s=26.4
- prism : resolved=True tokens=212670 turns=8 wall_s=30.6 prism_calls=2
- token ratio (prism/native): 0.62x

**FLAGGED** (token ratio 0.62x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=11 tokens=343338 wall_s=26.4 cost=$0.18265299999999998
  - tools: {'Grep': 2, 'Bash': 8}
- **prism**: resolved=True turns=8 tokens=212670 wall_s=30.6 cost=$0.1398402
  - tools: {'mcp__prism__prism': 2, 'Bash': 5}

> [2026-09-28 17:07:25]    native resolved=True tokens=343338 | prism resolved=True tokens=212670 prism_calls=2 [FLAGGED]

> [2026-09-28 17:07:25] -- wide__h3__EventStream_push (ts) --

## wide__h3__EventStream_push (ts)

- native: resolved=False tokens=139599 turns=5 wall_s=29.0
- prism : resolved=False tokens=213037 turns=8 wall_s=30.9 prism_calls=2
- token ratio (prism/native): 1.53x

**FLAGGED** (token ratio 1.53x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=5 tokens=139599 wall_s=29.0 cost=$0.111723
  - tools: {'Grep': 1, 'Bash': 3}
- **prism**: resolved=False turns=8 tokens=213037 wall_s=30.9 cost=$0.1381176
  - tools: {'mcp__prism__prism': 2, 'Bash': 5}

> [2026-09-28 17:08:45]    native resolved=False tokens=139599 | prism resolved=False tokens=213037 prism_calls=2 [FLAGGED]

> [2026-09-28 17:08:45] -- wide__werkzeug__HTTPException_get_headers (python) --

## wide__werkzeug__HTTPException_get_headers (python)

- native: resolved=True tokens=127257 turns=6 wall_s=15.2
- prism : resolved=True tokens=175940 turns=7 wall_s=14.3 prism_calls=1
- token ratio (prism/native): 1.38x

> [2026-09-28 17:09:42]    native resolved=True tokens=127257 | prism resolved=True tokens=175940 prism_calls=1

> [2026-09-28 17:09:42] -- wide__click__ClickException_format_message (python) --

## wide__click__ClickException_format_message (python)

- native: resolved=True tokens=146807 turns=7 wall_s=15.8
- prism : resolved=True tokens=196877 turns=8 wall_s=17.2 prism_calls=1
- token ratio (prism/native): 1.34x

> [2026-09-28 17:10:43]    native resolved=True tokens=146807 | prism resolved=True tokens=196877 prism_calls=1

> [2026-09-28 17:10:43] -- wide__rich__Highlighter_highlight (python) --

## wide__rich__Highlighter_highlight (python)

- native: resolved=True tokens=170084 turns=7 wall_s=29.5
- prism : resolved=True tokens=272964 turns=11 wall_s=34.9 prism_calls=3
- token ratio (prism/native): 1.60x

**FLAGGED** (token ratio 1.60x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=7 tokens=170084 wall_s=29.5 cost=$0.1094724
  - tools: {'Grep': 1, 'Bash': 5}
- **prism**: resolved=True turns=11 tokens=272964 wall_s=34.9 cost=$0.1436786
  - tools: {'mcp__prism__prism': 3, 'Bash': 7}

> [2026-09-28 17:12:03]    native resolved=True tokens=170084 | prism resolved=True tokens=272964 prism_calls=3 [FLAGGED]

> [2026-09-28 17:12:03] -- wide__werkzeug__BaseConverter_to_url (python) --

## wide__werkzeug__BaseConverter_to_url (python)

- native: resolved=True tokens=129624 turns=6 wall_s=22.6
- prism : resolved=True tokens=177255 turns=7 wall_s=15.8 prism_calls=1
- token ratio (prism/native): 1.37x

> [2026-09-28 17:13:11]    native resolved=True tokens=129624 | prism resolved=True tokens=177255 prism_calls=1

> [2026-09-28 17:13:11] -- wide__jackson-databind__TypeDeserializer_getTypeInclusion (java) --

## wide__jackson-databind__TypeDeserializer_getTypeInclusion (java)

- native: resolved=True tokens=270091 turns=9 wall_s=138.2
- prism : resolved=True tokens=276431 turns=8 wall_s=114.6 prism_calls=1
- token ratio (prism/native): 1.02x

> [2026-09-28 17:22:00]    native resolved=True tokens=270091 | prism resolved=True tokens=276431 prism_calls=1

> [2026-09-28 17:22:00] -- wide__gin__ResponseWriter_Status (go) --

## wide__gin__ResponseWriter_Status (go)

- native: resolved=True tokens=107895 turns=5 wall_s=19.6
- prism : resolved=True tokens=210057 turns=9 wall_s=22.3 prism_calls=2
- token ratio (prism/native): 1.95x

**FLAGGED** (token ratio 1.95x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=5 tokens=107895 wall_s=19.6 cost=$0.0740582
  - tools: {'Grep': 1, 'Bash': 3}
- **prism**: resolved=True turns=9 tokens=210057 wall_s=22.3 cost=$0.11377600000000002
  - tools: {'mcp__prism__prism': 2, 'Bash': 5, 'bash': 1}

> [2026-09-28 17:23:05]    native resolved=True tokens=107895 | prism resolved=True tokens=210057 prism_calls=2 [FLAGGED]

> [2026-09-28 17:23:05] -- wide__h3__H3Route_handler (ts) --

## wide__h3__H3Route_handler (ts)

- native: resolved=True tokens=222077 turns=7 wall_s=28.3
- prism : resolved=True tokens=331175 turns=15 wall_s=37.6 prism_calls=2
- token ratio (prism/native): 1.49x

> [2026-09-28 17:24:32]    native resolved=True tokens=222077 | prism resolved=True tokens=331175 prism_calls=2

> [2026-09-28 17:24:32] -- wide__click__Group_get_command (python) --

## wide__click__Group_get_command (python)

- native: resolved=True tokens=131116 turns=6 wall_s=17.9
- prism : resolved=True tokens=238704 turns=10 wall_s=23.7 prism_calls=2
- token ratio (prism/native): 1.82x

**FLAGGED** (token ratio 1.82x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=6 tokens=131116 wall_s=17.9 cost=$0.08120100000000001
  - tools: {'Grep': 1, 'Bash': 4}
- **prism**: resolved=True turns=10 tokens=238704 wall_s=23.7 cost=$0.12058780000000001
  - tools: {'mcp__prism__prism': 2, 'Bash': 7}

> [2026-09-28 17:25:41]    native resolved=True tokens=131116 | prism resolved=True tokens=238704 prism_calls=2 [FLAGGED]

> [2026-09-28 17:25:41] -- wide__hono__SetHeadersOptions_append (ts) --

## wide__hono__SetHeadersOptions_append (ts)

- native: resolved=True tokens=173251 turns=8 wall_s=31.4
- prism : resolved=True tokens=158224 turns=7 wall_s=23.6 prism_calls=1
- token ratio (prism/native): 0.91x

> [2026-09-28 17:27:33]    native resolved=True tokens=173251 | prism resolved=True tokens=158224 prism_calls=1

> [2026-09-28 17:27:33] -- wide__echo__HTTPStatusCoder_StatusCode (go) --

## wide__echo__HTTPStatusCoder_StatusCode (go)

- native: resolved=True tokens=128106 turns=5 wall_s=22.7
- prism : resolved=True tokens=180498 turns=6 wall_s=22.8 prism_calls=1
- token ratio (prism/native): 1.41x

> [2026-09-28 17:28:37]    native resolved=True tokens=128106 | prism resolved=True tokens=180498 prism_calls=1

> [2026-09-28 17:28:37] -- wide__rich__ProgressColumn_render (python) --

## wide__rich__ProgressColumn_render (python)

- native: resolved=True tokens=189353 turns=10 wall_s=21.3
- prism : resolved=True tokens=438503 turns=16 wall_s=43.4 prism_calls=2
- token ratio (prism/native): 2.32x

**FLAGGED** (token ratio 2.32x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=10 tokens=189353 wall_s=21.3 cost=$0.11344080000000001
  - tools: {'Grep': 4, 'Bash': 5}
- **prism**: resolved=True turns=16 tokens=438503 wall_s=43.4 cost=$0.1886722
  - tools: {'mcp__prism__prism': 2, 'Bash': 13}

> [2026-09-28 17:29:59]    native resolved=True tokens=189353 | prism resolved=True tokens=438503 prism_calls=2 [FLAGGED]

> [2026-09-28 17:29:59] -- wide__hono__Hono_basePath (ts) --

## wide__hono__Hono_basePath (ts)

- native: resolved=False tokens=170404 turns=7 wall_s=30.8
- prism : resolved=False tokens=266084 turns=11 wall_s=46.3 prism_calls=2
- token ratio (prism/native): 1.56x

**FLAGGED** (token ratio 1.56x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=7 tokens=170404 wall_s=30.8 cost=$0.11414959999999999
  - tools: {'Grep': 3, 'Bash': 3}
- **prism**: resolved=False turns=11 tokens=266084 wall_s=46.3 cost=$0.1544932
  - tools: {'mcp__prism__prism': 2, 'Bash': 8}

> [2026-09-28 17:32:06]    native resolved=False tokens=170404 | prism resolved=False tokens=266084 prism_calls=2 [FLAGGED]

> [2026-09-28 17:32:06] -- wide__werkzeug__Response_get_data (python) --

## wide__werkzeug__Response_get_data (python)

- native: resolved=True tokens=140387 turns=6 wall_s=25.7
- prism : resolved=True tokens=187187 turns=5 wall_s=685.3 prism_calls=1
- token ratio (prism/native): 1.33x

> [2026-09-28 17:44:29]    native resolved=True tokens=140387 | prism resolved=True tokens=187187 prism_calls=1

> [2026-09-28 17:44:29] -- wide__hono__ConnInfo_remote (ts) --

## wide__hono__ConnInfo_remote (ts)

- native: resolved=False tokens=208549 turns=9 wall_s=30.0
- prism : resolved=True tokens=230988 turns=9 wall_s=35.1 prism_calls=2
- token ratio (prism/native): 1.11x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=9 tokens=208549 wall_s=30.0 cost=$0.1371698
  - tools: {'Grep': 1, 'Read': 1, 'Bash': 6}
- **prism**: resolved=True turns=9 tokens=230988 wall_s=35.1 cost=$0.14305440000000003
  - tools: {'mcp__prism__prism': 2, 'Bash': 6}

> [2026-09-28 17:46:25]    native resolved=False tokens=208549 | prism resolved=True tokens=230988 prism_calls=2 [FLAGGED]

> [2026-09-28 17:46:25] -- wide__jackson-databind__TypeDeserializer_forProperty (java) --
