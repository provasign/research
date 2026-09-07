# Stopped four-head impact panel — trial 1 snapshot

The user stopped the 108-cell run after one complete nine-task trial plus one
completed trial-2 cell. No model processes remain. This is a one-trial snapshot,
not a variance estimate or replacement for a repeated panel.

| Arm | n | Mean recall | Mean precision | Mean F1 | Mean tokens | Mean wall time | Mean turns | Sonnet cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sonnet native | 9 | .9545 | .8394 | .8633 | 742,595 | 177.7 s | 22.6 | $4.296 |
| Sonnet + Prism | 9 | .9964 | .9801 | .9876 | 75,397 | 63.1 s | 4.2 | $1.343 |
| GPT-5.6 native | 9 | .8915 | .9143 | .8679 | 406,151 | 229.3 s | 1.0 | unavailable |
| GPT-5.6 + Prism | 9 | .9964 | .9166 | .9350 | 49,868 | 128.0 s | 1.0 | unavailable |

For Sonnet, Prism used 10.2% of native tokens, 35.5% of native wall time, and
31.3% of the recorded CLI cost. For GPT-5.6, Prism used 12.3% of native tokens
and 55.9% of native wall time. GPT-5.6 cost is intentionally unreported because
no official pricing basis was established.

The low GPT-5.6 + Prism mean precision is concentrated in Django: that cell
made three distinct Prism calls and scored .2936 precision, whereas the
deterministic one-call ceiling is .8889. This is useful steering/assembly
evidence, but one trial cannot estimate its frequency.

Twelve Django/Grafana cells were initially marked invalid solely because the
runner treated committed symlinks as newly created regular files after archive
extraction. `git ls-tree` confirms mode 120000 for every listed path at the task
pins; no source hashes changed and all other validity checks passed. All 36
trial-1 cells are therefore usable after this audit correction.

The evidence, commands, full JSONL transcripts, prompts, task snapshots,
binary/hash manifest, and three interrupted trial-2 attempt directories remain
under this run directory.
