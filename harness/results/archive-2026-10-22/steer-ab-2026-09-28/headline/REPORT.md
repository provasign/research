# Overnight run: native vs resident prism_init

Started 2026-09-28 16:40:42. 32 tasks, model=sonnet, arms=prism_body_baseline vs prism_body_exp.

Flag rule: resolve mismatch, OR token ratio (prism/native) outside [0.67, 1.5]. A flagged cell with 0 prism tool calls is a non-adoption artifact, not attributable to prism's engine -- flagged separately below.

> [2026-09-28 16:40:42] starting: 32 tasks, 0 already done

> [2026-09-28 16:40:42] -- wide__chi__Routes_Match (go) --

## wide__chi__Routes_Match (go)

- native: resolved=True tokens=103423 turns=5 wall_s=66.7
- prism : resolved=True tokens=131727 turns=6 wall_s=42.6 prism_calls=2
- token ratio (prism/native): 1.27x

> [2026-09-28 16:43:34]    native resolved=True tokens=103423 | prism resolved=True tokens=131727 prism_calls=2

> [2026-09-28 16:43:34] -- wide__click__Command_invoke (python) --

## wide__click__Command_invoke (python)

- native: resolved=True tokens=298153 turns=9 wall_s=34.7
- prism : resolved=True tokens=348718 turns=9 wall_s=24.5 prism_calls=1
- token ratio (prism/native): 1.17x

> [2026-09-28 16:45:02]    native resolved=True tokens=298153 | prism resolved=True tokens=348718 prism_calls=1

> [2026-09-28 16:45:02] -- wide__h3__EventStream_push (ts) --

## wide__h3__EventStream_push (ts)

- native: resolved=False tokens=266638 turns=9 wall_s=37.4
- prism : resolved=False tokens=219966 turns=8 wall_s=20.3 prism_calls=2
- token ratio (prism/native): 0.82x

> [2026-09-28 16:46:25]    native resolved=False tokens=266638 | prism resolved=False tokens=219966 prism_calls=2

> [2026-09-28 16:46:25] -- wide__werkzeug__HTTPException_get_headers (python) --

## wide__werkzeug__HTTPException_get_headers (python)

- native: resolved=True tokens=201392 turns=8 wall_s=148.4
- prism : resolved=True tokens=181144 turns=8 wall_s=27.0 prism_calls=2
- token ratio (prism/native): 0.90x

> [2026-09-28 16:49:49]    native resolved=True tokens=201392 | prism resolved=True tokens=181144 prism_calls=2

> [2026-09-28 16:49:49] -- wide__click__ClickException_format_message (python) --
