# Forced-first-call Prism isolation — 2026-09-07

## Decision

Do **not** change Prism v0.72.0 steering or tool guidance based on this study.
The release binary was not modified. The treatment existed only in temporary
benchmark prompts and required one appropriate Prism call before native tools.

The result is mixed: the treatment helped both models complete the Click coding
fix quickly with held-out-passing patches, but did not help the harder Werkzeug
fix, added no search accuracy, and caused Sonnet to exceed the requested
one-call ceiling on both search tasks. That is insufficient evidence for a
blanket product change and could compromise the release's current strengths.

## Design

- 8 new cells: two search tasks and two coding tasks, Sonnet+Prism and
  GPT-5.5+Prism only.
- Matching native and natural-Prism cells were reused from commit `c40cec8`.
- Search cap: 90 seconds. Coding cap: 180 seconds. No retries.
- Prism v0.72.0 binary and MCP tool descriptions were unchanged.
- Treatment compliance: 6/8 cells made exactly one Prism call. Sonnet made
  three and four calls on the two search tasks despite the explicit ceiling.

## Search comparison

All completed answers were exact. `JSONTag.tag` still timed out for Sonnet.

| Task / model | Native | Natural Prism | Forced first call |
|---|---:|---:|---:|
| `from_pyfile` / Sonnet | 24.9s, exact | 7.6s, exact | 17.3s, exact; 3 calls |
| `from_pyfile` / GPT-5.5 | 46.2s, exact | 46.5s, exact; unused | 38.8s, exact; 1 call |
| `JSONTag.tag` / Sonnet | 120s timeout | 120s timeout | 90s timeout; 4 calls |
| `JSONTag.tag` / GPT-5.5 | 84.9s, exact | 103.2s, exact | 89.6s, exact; 1 call |

Forced use produced no accuracy gain. GPT-5.5 improved relative to natural
Prism on both tasks, but on `JSONTag.tag` remained slower and more token-heavy
than native. Sonnet's natural routing was already best on `from_pyfile`; forcing
the first call and attempting to cap tool use made it slower.

## Coding comparison

| Task / model | Native | Natural Prism | Forced first call |
|---|---:|---:|---:|
| Click / Sonnet | 99.3s, failed patch | 120s timeout, passing patch | 88.1s, completed passing patch |
| Click / GPT-5.5 | 106.5s, passing | 112.2s, passing; Prism unused | 75.9s, passing |
| Werkzeug / Sonnet | 120s timeout, no patch | 121s timeout, no patch | 181s timeout, no patch |
| Werkzeug / GPT-5.5 | 120s timeout, no patch | 82.6s, no patch; Prism unused | 60.3s, no patch |

The Click result is a real positive signal: both forced cells completed with
passing patches in less than the original 120-second cap. It is task-specific,
however. On Werkzeug, the supplied context did not dislodge the mistaken belief
that a pre-existing partial fix already resolved the report.

## Next safe step

Preserve v0.72.0 as released. Build the balanced permanent suite—two lookup,
two usage search, two cross-file comprehension, and two coding tasks—and treat
natural Prism adoption as an outcome. The Click signal can motivate a separate,
narrow coding-routing study, but not a general steering change.

## Evidence

- `aggregate.json`: task-by-task native, natural-Prism, and forced-first-call
  comparison plus the release decision.
- `read-only/` and `code/`: manifests, frozen tasks, prompts, transcripts,
  measurements, patches, and held-out scores.
- `run_readonly.py`, `run_code.py`, and `summarize.py`: exact executed logic.
