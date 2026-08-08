# End-to-end benchmark — resolve rate (agent fixes the real 2026 bug, tests pass)

35 tasks · 391 cells · models: haiku, local, opus

Resolve rate = FAIL_TO_PASS passes and no PASS_TO_PASS regression, scored in Docker. Tasks are post-cutoff (2026), issue-text prompts (no solution leak).

## Resolve rate: model × arm

| model | baseline | prism_gstar | mason |
|---|---|---|---|
| haiku | 34/49 | 2/5 | - |
| local | - | - | 12/75 |
| opus | 42/60 | - | - |

## Per-task (haiku)

| task | baseline | prism_gstar | mason |
|---|---|---|---|
| pr6008 | 2/2 |  |  |
| pr6012 | 2/2 |  |  |
| pr6018 | 2/2 |  |  |
| pr6019 | 2/2 |  |  |
| pr6030 | 2/2 |  |  |
| pr6035 | 2/2 |  |  |
| pr6039 | 2/2 |  |  |
| pr6042 | 2/2 |  |  |
| pr6044 | 2/2 |  |  |
| pr6113 | 0/2 |  |  |
| pr700 |  |  |  |
| pr704 |  |  |  |
| pr705 |  |  |  |
| pr710 |  |  |  |
| pr712 |  |  |  |
| pr713 |  |  |  |
| pr714 |  |  |  |
| pr715 |  |  |  |
| pr716 |  |  |  |
| pr717 |  |  |  |
| pr718 |  |  |  |
| pr719 |  |  |  |
| pr1591 | 2/2 |  |  |
| pr1631 | 2/2 |  |  |
| pr1655 | 0/2 |  |  |
| pr1670 | 1/2 |  |  |
| pr1699 | 0/2 |  |  |
| pr1703 | 0/2 |  |  |
| pr1709 | 2/2 |  |  |
| pr1713 |  |  |  |
| pr3493 | 3/3 | ✓ |  |
| pr3504 | 1/3 | · |  |
| pr3534 | 3/3 | ✓ |  |
| pr3653 | 2/3 | · |  |
| pr3678 | 0/3 | · |  |

## Per-task (local)

| task | baseline | prism_gstar | mason |
|---|---|---|---|
| pr6008 |  |  | 0/2 |
| pr6012 |  |  | 0/2 |
| pr6018 |  |  | 0/2 |
| pr6019 |  |  | 0/2 |
| pr6030 |  |  | 0/2 |
| pr6035 |  |  | 0/2 |
| pr6039 |  |  | 1/2 |
| pr6042 |  |  | 0/2 |
| pr6044 |  |  | 0/2 |
| pr6113 |  |  | 0/2 |
| pr700 |  |  | 0/2 |
| pr704 |  |  | 2/2 |
| pr705 |  |  | 0/2 |
| pr710 |  |  | 0/2 |
| pr712 |  |  | 0/2 |
| pr713 |  |  | 0/2 |
| pr714 |  |  | 2/2 |
| pr715 |  |  | 1/2 |
| pr716 |  |  | 0/2 |
| pr717 |  |  | 2/2 |
| pr718 |  |  | 0/2 |
| pr719 |  |  | 0/2 |
| pr1591 |  |  | 0/2 |
| pr1631 |  |  | 2/2 |
| pr1655 |  |  | 0/2 |
| pr1670 |  |  | 0/2 |
| pr1699 |  |  | 0/2 |
| pr1703 |  |  | 0/2 |
| pr1709 |  |  | 0/2 |
| pr1713 |  |  | 0/2 |
| pr3493 |  |  | 2/3 |
| pr3504 |  |  | 0/3 |
| pr3534 |  |  | 0/3 |
| pr3653 |  |  | 0/3 |
| pr3678 |  |  | 0/3 |

## Per-task (opus)

| task | baseline | prism_gstar | mason |
|---|---|---|---|
| pr6008 | 2/2 |  |  |
| pr6012 | 2/2 |  |  |
| pr6018 | 0/2 |  |  |
| pr6019 | 0/2 |  |  |
| pr6030 | 0/2 |  |  |
| pr6035 | 0/2 |  |  |
| pr6039 | 2/2 |  |  |
| pr6042 | 2/2 |  |  |
| pr6044 | 1/2 |  |  |
| pr6113 | 0/2 |  |  |
| pr700 | 2/2 |  |  |
| pr704 | 2/2 |  |  |
| pr705 | 0/2 |  |  |
| pr710 | 2/2 |  |  |
| pr712 | 2/2 |  |  |
| pr713 | 2/2 |  |  |
| pr714 | 2/2 |  |  |
| pr715 | 2/2 |  |  |
| pr716 | 2/2 |  |  |
| pr717 | 2/2 |  |  |
| pr718 | 2/2 |  |  |
| pr719 | 2/2 |  |  |
| pr1591 | 2/2 |  |  |
| pr1631 | 2/2 |  |  |
| pr1655 | 1/2 |  |  |
| pr1670 | 0/2 |  |  |
| pr1699 | 2/2 |  |  |
| pr1703 | 0/2 |  |  |
| pr1709 | 2/2 |  |  |
| pr1713 | 2/2 |  |  |
| pr3493 |  |  |  |
| pr3504 |  |  |  |
| pr3534 |  |  |  |
| pr3653 |  |  |  |
| pr3678 |  |  |  |
