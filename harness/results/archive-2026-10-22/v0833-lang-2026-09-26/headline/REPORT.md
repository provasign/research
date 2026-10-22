# Overnight run: native vs resident prism_init

Started 2026-09-26 18:31:38. 71 tasks, model=sonnet, arms=baseline vs prism_init.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-26 18:31:38] starting: 71 tasks, 0 already done

> [2026-09-26 18:31:38] -- urfave__cli__pr2296 (go) --

## urfave__cli__pr2296 (go)

- native: resolved=True tokens=318797 turns=8 wall_s=45.9
- prism : resolved=True tokens=326022 turns=8 wall_s=68.8 prism_calls=1
- token ratio (prism/native): 1.02x

> [2026-09-26 18:33:49]    native resolved=True tokens=318797 | prism resolved=True tokens=326022 prism_calls=1

> [2026-09-26 18:33:49] -- urfave__cli__pr2309 (go) --

## urfave__cli__pr2309 (go)

- native: resolved=True tokens=601253 turns=14 wall_s=47.2
- prism : resolved=True tokens=958266 turns=17 wall_s=58.2 prism_calls=5
- token ratio (prism/native): 1.59x

**FLAGGED** (token ratio 1.59x outside [0.67, 1.5])

**Attribution: prism WAS called (5x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=14 tokens=601253 wall_s=47.2 cost=$0.26753760000000004
  - tools: {'Grep': 4, 'Read': 5, 'Edit': 1, 'Bash': 3}
- **prism**: resolved=True turns=17 tokens=958266 wall_s=58.2 cost=$0.38617220000000013
  - tools: {'mcp__prism__prism': 5, 'Grep': 2, 'Read': 1, 'Edit': 1, 'Bash': 7}

> [2026-09-26 18:35:48]    native resolved=True tokens=601253 | prism resolved=True tokens=958266 prism_calls=5 [FLAGGED]

> [2026-09-26 18:35:48] -- urfave__cli__pr2290 (go) --

## urfave__cli__pr2290 (go)

- native: resolved=True tokens=467595 turns=12 wall_s=50.6
- prism : resolved=True tokens=201525 turns=5 wall_s=22.2 prism_calls=1
- token ratio (prism/native): 0.43x

**FLAGGED** (token ratio 0.43x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=12 tokens=467595 wall_s=50.6 cost=$0.211971
  - tools: {'Grep': 5, 'Read': 3, 'Edit': 1, 'Bash': 2}
- **prism**: resolved=True turns=5 tokens=201525 wall_s=22.2 cost=$0.1257308
  - tools: {'mcp__prism__prism': 1, 'Edit': 1, 'Bash': 2}

> [2026-09-26 18:37:15]    native resolved=True tokens=467595 | prism resolved=True tokens=201525 prism_calls=1 [FLAGGED]

> [2026-09-26 18:37:15] -- urfave__cli__pr2419 (go) --

## urfave__cli__pr2419 (go)

- native: resolved=False tokens=1030483 turns=25 wall_s=74.5
- prism : resolved=False tokens=245499 turns=6 wall_s=35.7 prism_calls=1
- token ratio (prism/native): 0.24x

**FLAGGED** (token ratio 0.24x outside [0.67, 1.5])

**Attribution: prism WAS called (1x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=False turns=25 tokens=1030483 wall_s=74.5 cost=$0.3609068000000002
  - tools: {'Grep': 2, 'Read': 4, 'Edit': 6, 'Bash': 12}
- **prism**: resolved=False turns=6 tokens=245499 wall_s=35.7 cost=$0.13738940000000002
  - tools: {'mcp__prism__prism': 1, 'Edit': 2, 'Read': 1, 'Bash': 1}

> [2026-09-26 18:39:20]    native resolved=False tokens=1030483 | prism resolved=False tokens=245499 prism_calls=1 [FLAGGED]

> [2026-09-26 18:39:20] -- urfave__cli__pr2297 (go) --

## urfave__cli__pr2297 (go)

- native: resolved=True tokens=410733 turns=11 wall_s=42.8
- prism : resolved=True tokens=288908 turns=7 wall_s=35.5 prism_calls=1
- token ratio (prism/native): 0.70x

> [2026-09-26 18:40:53]    native resolved=True tokens=410733 | prism resolved=True tokens=288908 prism_calls=1

> [2026-09-26 18:40:53] -- google__gson__pr3067 (java) --

## google__gson__pr3067 (java)

- native: resolved=True tokens=369877 turns=10 wall_s=52.5
- prism : resolved=True tokens=245486 turns=6 wall_s=27.7 prism_calls=3
- token ratio (prism/native): 0.66x

**FLAGGED** (token ratio 0.66x outside [0.67, 1.5])

**Attribution: prism WAS called (3x) -- this is a real signal, needs manual read of the evidence below, not an adoption excuse.**

- **native**: resolved=True turns=10 tokens=369877 wall_s=52.5 cost=$0.18830819999999998
  - tools: {'Grep': 1, 'Read': 2, 'Edit': 1, 'Bash': 5}
- **prism**: resolved=True turns=6 tokens=245486 wall_s=27.7 cost=$0.1370444
  - tools: {'mcp__prism__prism': 3, 'Edit': 1, 'Bash': 1}

> [2026-09-26 18:42:32]    native resolved=True tokens=369877 | prism resolved=True tokens=245486 prism_calls=3 [FLAGGED]

> [2026-09-26 18:42:32] -- urfave__cli__pr2311 (go) --

## urfave__cli__pr2311 (go)

- native: resolved=False tokens=171163 turns=5 wall_s=15.6
- prism : resolved=False tokens=149946 turns=4 wall_s=11.9 prism_calls=1
- token ratio (prism/native): 0.88x

> [2026-09-26 18:43:15]    native resolved=False tokens=171163 | prism resolved=False tokens=149946 prism_calls=1

> [2026-09-26 18:43:15] -- apache__dubbo__pr16350 (java) --
