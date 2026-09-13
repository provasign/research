# Prism first-result investigation — 2026-09-12/13

Curated evidence from the single-cell runs behind the "Prism found the location, the model used native tools for every follow-up" finding.
Task: `pallets__click__pr3244` (e2e coding suite), Claude Sonnet (`claude-sonnet-5`), effort medium, 5-min budget.
Each run dir holds `manifest.json` (Prism version + binary sha256, models, flags), `summary.json`, `tasks/`, and `evidence/<cell>/`
(`stdout.jsonl` transcript, `measurement.json`, `agent.diff`, `command.json`, `mcp.json`, `prompt.txt`).
Scratch (`work/`, venvs, template clones, copied binaries) was deliberately not kept; the manifest hashes pin the binaries.

| run | prism version | prism binary sha256 | thinking captured | network block | cells |
|---|---|---|---|---|---|
| `old-v0.74.1` | prism v0.74.1 | `eea4ee42dd2fb286…` | no | no | pallets__click__pr3244.r1.sonnet_codegraph, pallets__click__pr3244.r1.sonnet_native, pallets__click__pr3244.r1.sonnet_prism |
| `wording-rebuild` | prism dev | `21bd1ac0d642a1d2…` | no | no | pallets__click__pr3244.r1.sonnet_prism |
| `wording-thinking` | prism dev | `21bd1ac0d642a1d2…` | summarized | no | pallets__click__pr3244.r1.sonnet_native, pallets__click__pr3244.r1.sonnet_prism |
| `codex-first-result` | prism dev | `680df17d2371f875…` | summarized | yes | pallets__click__pr3244.r1.sonnet_prism |

## Cross-cell table (from measurement.json + transcripts)

| cell | turns | edits | Prism result B | Prism calls | native reads | read KB | cost | resolved |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| old-v0.74.1 / sonnet_prism | 39 | 3 | 4076 | 1 | 9 | 24.3 | $0.67 | yes — 2× `pip download` (pre-audit) |
| wording-rebuild / sonnet_prism | 28 | 4 | 1401 | 1 | 6 | 22.1 | $0.45 | yes |
| wording-thinking / sonnet_prism | 20 | 3 | 819 | 1 | 5 | 11.3 | $0.26 | yes |
| codex-first-result / sonnet_prism | 12 | 1 | 3832 | 1 | 1 (whole file) | 22.8 | $0.23 | yes |
| old-v0.74.1 / sonnet_native | 26 | 3 | — | — | 6 | 12.9 | $0.38 | yes |
| wording-thinking / sonnet_native | 14 | 1 | — | — | 2 | 4.1 | $0.24 | yes |
| old-v0.74.1 / sonnet_codegraph | 20 | 4 | — | 0 (tool never called) | 2 | — | $0.39 | yes, audit-invalid |

Finding (click task): exactly one Prism call in every Prism cell across three Prism builds; every follow-up went to native Read/grep.
(On urllib3 the old build already made 1–3 calls per cell — the "one call" pattern is task-specific, not universal.)
Turns/cost track the number of edit→test cycles, not the tool. n=1 per cell; the before/after batch below is the attribution run.

## Before/after batch (2026-09-13) — `../batch-old-v0.74.1/`, `../batch-codex-fix/`

Same pilot pair (`pallets__click__pr3244`, `urllib3__urllib3__pr3786`), Prism arm only, 3 trials per task per build,
Claude Sonnet, thinking captured, network blocked (`--disallowedTools` + `GIT_ALLOW_PROTOCOL=file`). Run B crashed after 5 of 6
cells on a `permission_denied` system event with a string `message` (the deny list refusing `pip download` in click r3);
`bench.py rescore` rebuilt that cell from its transcript and scored all five. urllib3 r3 on the new build never ran.
Valid cells only:

| | OLD v0.74.1 (n=6) | NEW Codex first-result build (n=5) |
|---|---:|---:|
| resolved | 2/6 (click 2/3, urllib3 0/3) | 3/5 (click 3/3, urllib3 0/2) |
| cells with a follow-up op (`read`/`lookup`) | 1/6 | 2/5 |
| mean Prism calls | 1.7 | 2.2 |
| mean native reads (discovery / edit-prerequisite) | 5.5 (4.5 / 1.0) | 5.8 (4.6 / 1.2) |
| mean KB read | 19.6 | 23.9 |
| mean edits / turns | 2.7 / 22.8 | 2.4 / 22.2 |
| mean cost | $0.39 | $0.39 |
| network: executed / blocked attempts | 0 / 0 | 0 / 1 |

Read: the first-result change is behaviorally neutral at this size — turns, cost and discovery reads unchanged, bytes read
slightly up; follow-up-op use 1/6 → 2/5 is direction-consistent but not a signal at n≈6. urllib3 resolved 0/5 across both
builds (at or past the model's ceiling here). The block held on the one live attempt. Discovery reads (~4.5/cell) go native
regardless of first-result content — the instruction-level lever is the untried one.

"discovery" vs "edit-prerequisite": a native Read immediately followed by an Edit of the same file is counted as the
prerequisite Claude Code's Edit tool requires; every other Read is discovery. Recovered cell: `batch-codex-fix/…click…r3`
(`recovered: true`, CLI exit code unknown; validity rests on a complete result event, no agent error, no violations).
