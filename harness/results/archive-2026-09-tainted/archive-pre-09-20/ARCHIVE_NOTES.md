# Archive notes — 2026-09 pre-09-20 results

These are one-off benchmark run directories from 2026-09-12 through
2026-09-19, superseded or made obsolete by later reruns and the 2026-09-20
codex/gpt-5.5 measurement (`java-resolved-*`, `resolved-cases-prism-grove0581-2026-09-20`,
kept live in `harness/results/`, not archived).

Each directory here is slimmed: `work/`, `bin/`, `prism-bin`, `templates/`,
and `environments/` (repo checkouts, built binaries, docker/venv scaffolding —
all regenerable, none of it signal) were deleted before archiving. What
remains is the durable record: `manifest.json`, `summary.json`, `evidence/`,
`tasks/`. Original sizes ranged 12M-3.7G per directory (≈19GB total);
archived size is ≈36MB.

If a result set here needs to be reproduced, re-run the harness against the
task/pin recorded in its `manifest.json` — don't expect the stripped `work/`
or binaries to still be present.
