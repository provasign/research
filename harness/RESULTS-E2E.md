# End-to-end benchmark — resolve rate (agent fixes the real 2026 bug, tests pass)

5 tasks · 90 cells · models: haiku, local, sonnet

Resolve rate = FAIL_TO_PASS passes and no PASS_TO_PASS regression, scored in Docker. Tasks are post-cutoff (2026), issue-text prompts (no solution leak).

## Resolve rate: model × arm

| model | baseline | prism_g | prism_gstar | codegraph | mason | prism_g_nogrep | prism_gstar_nogrep | prism_explore_nogrep | codegraph_nogrep |
|---|---|---|---|---|---|---|---|---|---|
| haiku | 0/5 | 0/5 | 0/5 | 2/5 | - | 2/5 | 3/5 | 2/5 | 2/5 |
| local | 0/2 | 0/1 | 0/1 | 0/1 | 0/5 | - | - | - | - |
| sonnet | 0/5 | 0/5 | 0/5 | 2/5 | - | 2/5 | 2/5 | 1/5 | 2/5 |

## Per-task (haiku)

| task | baseline | prism_g | prism_gstar | codegraph | mason | prism_g_nogrep | prism_gstar_nogrep | prism_explore_nogrep | codegraph_nogrep |
|---|---|---|---|---|---|---|---|---|---|
| pr3493 | · | · | · | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| pr3504 | · | · | · | · |  | · | ✓ | · | · |
| pr3534 | · | · | · | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| pr3653 | · | · | · | · |  | · | · | · | · |
| pr3678 | · | · | · | · |  | · | · | · | · |

## Per-task (local)

| task | baseline | prism_g | prism_gstar | codegraph | mason | prism_g_nogrep | prism_gstar_nogrep | prism_explore_nogrep | codegraph_nogrep |
|---|---|---|---|---|---|---|---|---|---|
| pr3493 | · | · | · | · | · |  |  |  |  |
| pr3504 | · |  |  |  | · |  |  |  |  |
| pr3534 |  |  |  |  | · |  |  |  |  |
| pr3653 |  |  |  |  | · |  |  |  |  |
| pr3678 |  |  |  |  | · |  |  |  |  |

## Per-task (sonnet)

| task | baseline | prism_g | prism_gstar | codegraph | mason | prism_g_nogrep | prism_gstar_nogrep | prism_explore_nogrep | codegraph_nogrep |
|---|---|---|---|---|---|---|---|---|---|
| pr3493 | · | · | · | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| pr3504 | · | · | · | · |  | · | · | · | · |
| pr3534 | · | · | · | ✓ |  | ✓ | ✓ | · | ✓ |
| pr3653 | · | · | · | · |  | · | · | · | · |
| pr3678 | · | · | · | · |  | · | · | · | · |
