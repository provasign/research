# Overnight run: native vs resident prism_init

Started 2026-09-21 06:30:20. 11 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-21 06:30:20] starting: 11 tasks, 0 already done

> [2026-09-21 06:30:20] -- apache__commons-lang__pr1631 (java) --

## apache__commons-lang__pr1631 (java)

- native: resolved=True tokens=140520 turns=4 wall_s=17.9
- prism : resolved=True tokens=271269 turns=7 wall_s=25.3 prism_calls=2
- token ratio (prism/native): 1.93x

**FLAGGED** (token ratio 1.93x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=4 tokens=140520 wall_s=17.9 cost=$0.09631239999999999
  - tools: {'Grep': 1, 'Edit': 1, 'Bash': 1}
- **prism**: resolved=True turns=7 tokens=271269 wall_s=25.3 cost=$0.21940520000000005
  - tools: {'mcp__prism__prism': 2, 'Edit': 1, 'Bash': 3}

> [2026-09-21 06:31:38]    native resolved=True tokens=140520 | prism resolved=True tokens=271269 prism_calls=2 [FLAGGED]

> [2026-09-21 06:31:38] -- apache__commons-lang__pr1670 (java) --

## apache__commons-lang__pr1670 (java)

- native: resolved=True tokens=728828 turns=17 wall_s=218.7
- prism : resolved=True tokens=1617409 turns=30 wall_s=322.9 prism_calls=4
- token ratio (prism/native): 2.22x

**FLAGGED** (token ratio 2.22x outside [0.67, 1.5])

**Attribution: prism WAS called (4x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=17 tokens=728828 wall_s=218.7 cost=$0.2844266000000001
  - tools: {'Grep': 4, 'Read': 2, 'Edit': 1, 'Bash': 9}
- **prism**: resolved=True turns=30 tokens=1617409 wall_s=322.9 cost=$0.5703815999999999
  - tools: {'mcp__prism__prism': 4, 'Read': 3, 'Edit': 3, 'Bash': 15, 'ScheduleWakeup': 4}

> [2026-09-21 06:41:17]    native resolved=True tokens=728828 | prism resolved=True tokens=1617409 prism_calls=4 [FLAGGED]

> [2026-09-21 06:41:17] -- apache__commons-lang__pr1699 (java) --

## apache__commons-lang__pr1699 (java)

- native: resolved=True tokens=240915 turns=9 wall_s=25.7
- prism : resolved=True tokens=266618 turns=7 wall_s=23.8 prism_calls=2
- token ratio (prism/native): 1.11x

> [2026-09-21 06:42:42]    native resolved=True tokens=240915 | prism resolved=True tokens=266618 prism_calls=2

> [2026-09-21 06:42:42] -- apache__commons-lang__pr1720 (java) --

## apache__commons-lang__pr1720 (java)

- native: resolved=True tokens=440516 turns=12 wall_s=42.5
- prism : resolved=True tokens=449949 turns=11 wall_s=61.6 prism_calls=3
- token ratio (prism/native): 1.02x

> [2026-09-21 06:45:07]    native resolved=True tokens=440516 | prism resolved=True tokens=449949 prism_calls=3

> [2026-09-21 06:45:07] -- apache__commons-lang__pr1713 (java) --

## apache__commons-lang__pr1713 (java)

- native: resolved=True tokens=363691 turns=10 wall_s=38.9
- prism : resolved=True tokens=354527 turns=9 wall_s=32.9 prism_calls=2
- token ratio (prism/native): 0.97x

> [2026-09-21 06:46:55]    native resolved=True tokens=363691 | prism resolved=True tokens=354527 prism_calls=2

> [2026-09-21 06:46:55] -- apache__commons-lang__pr1733 (java) --

## apache__commons-lang__pr1733 (java)

- native: resolved=True tokens=326224 turns=9 wall_s=34.7
- prism : resolved=True tokens=520838 turns=12 wall_s=50.0 prism_calls=2
- token ratio (prism/native): 1.60x

**FLAGGED** (token ratio 1.60x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=9 tokens=326224 wall_s=34.7 cost=$0.1298314
  - tools: {'Grep': 1, 'Read': 2, 'Edit': 4, 'Bash': 1}
- **prism**: resolved=True turns=12 tokens=520838 wall_s=50.0 cost=$0.20483739999999998
  - tools: {'mcp__prism__prism': 2, 'Read': 2, 'Edit': 4, 'Bash': 3}

> [2026-09-21 06:48:56]    native resolved=True tokens=326224 | prism resolved=True tokens=520838 prism_calls=2 [FLAGGED]

> [2026-09-21 06:48:56] -- apache__commons-lang__pr1703 (java) --

## apache__commons-lang__pr1703 (java)

- native: resolved=False tokens=308318 turns=8 wall_s=210.5
- prism : resolved=False tokens=573380 turns=12 wall_s=220.9 prism_calls=2
- token ratio (prism/native): 1.86x

**FLAGGED** (token ratio 1.86x outside [0.67, 1.5])

**Attribution: prism WAS called (2x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=8 tokens=308318 wall_s=210.5 cost=$0.1685874
  - tools: {'Grep': 1, 'Read': 1, 'Edit': 2, 'Bash': 3}
- **prism**: resolved=False turns=12 tokens=573380 wall_s=220.9 cost=$0.2720338
  - tools: {'mcp__prism__prism': 2, 'Read': 2, 'Edit': 2, 'Bash': 5}

> [2026-09-21 06:56:43]    native resolved=False tokens=308318 | prism resolved=False tokens=573380 prism_calls=2 [FLAGGED]

> [2026-09-21 06:56:43] -- apache__commons-lang__pr1591 (java) --

## apache__commons-lang__pr1591 (java)

- native: resolved=True tokens=388987 turns=9 wall_s=238.8
- prism : resolved=True tokens=444340 turns=10 wall_s=61.4 prism_calls=4
- token ratio (prism/native): 1.14x

> [2026-09-21 07:02:21]    native resolved=True tokens=388987 | prism resolved=True tokens=444340 prism_calls=4

> [2026-09-21 07:02:21] -- apache__commons-lang__pr1655 (java) --

## apache__commons-lang__pr1655 (java)

- native: resolved=False tokens=245751 turns=7 wall_s=46.4
- prism : resolved=False tokens=327372 turns=8 wall_s=55.5 prism_calls=4
- token ratio (prism/native): 1.33x

> [2026-09-21 07:04:38]    native resolved=False tokens=245751 | prism resolved=False tokens=327372 prism_calls=4

> [2026-09-21 07:04:38] -- apache__commons-lang__pr1709 (java) --

## apache__commons-lang__pr1709 (java)

- native: resolved=True tokens=380584 turns=9 wall_s=43.5
- prism : resolved=True tokens=401928 turns=11 wall_s=44.9 prism_calls=3
- token ratio (prism/native): 1.06x

> [2026-09-21 07:06:42]    native resolved=True tokens=380584 | prism resolved=True tokens=401928 prism_calls=3

> [2026-09-21 07:06:42] -- apache__commons-lang__pr1750 (java) --

## apache__commons-lang__pr1750 (java)

- native: resolved=False tokens=277999 turns=8 wall_s=30.2
- prism : resolved=True tokens=386662 turns=9 wall_s=34.6 prism_calls=3
- token ratio (prism/native): 1.39x

**FLAGGED** (resolve mismatch)

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=8 tokens=277999 wall_s=30.2 cost=$0.11148219999999999
  - tools: {'Grep': 3, 'Bash': 3, 'Read': 1}
- **prism**: resolved=True turns=9 tokens=386662 wall_s=34.6 cost=$0.16107660000000001
  - tools: {'mcp__prism__prism': 3, 'Grep': 1, 'Edit': 1, 'Bash': 3}

> [2026-09-21 07:08:23]    native resolved=False tokens=277999 | prism resolved=True tokens=386662 prism_calls=3 [FLAGGED]


# SUMMARY

11/11 tasks completed.

- native resolved: 8/11
- prism  resolved: 9/11
- native tokens total: 3842333
- prism  tokens total: 5614292 (1.46x native)
- flagged cells: 5 (0 non-adoption, 5 real prism signal)

## Cells needing a real look (prism was called, still flagged)

- apache__commons-lang__pr1631
- apache__commons-lang__pr1670
- apache__commons-lang__pr1733
- apache__commons-lang__pr1703
- apache__commons-lang__pr1750

Completed 2026-09-21 07:08:23

> [2026-09-21 07:08:23] DONE: 11/11 tasks, 5 flagged (0 non-adoption, 5 real)
