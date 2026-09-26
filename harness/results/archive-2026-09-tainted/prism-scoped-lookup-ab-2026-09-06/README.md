# Scoped Lookup: Eight-Cell Binary Comparison

Run `prism-scoped-ab-1_9slfbq`, 2026-09-06. **FAIL** on both frozen efficiency
targets. All eight cells are valid; no retries, exclusions or setup failures.

| Metric | Before Prism | Scoped-lookup Prism |
| --- | ---: | ---: |
| Total input + output tokens | 250,078 | 273,667 |
| Input tokens, including cache reads | 245,737 | 269,030 |
| Cached input tokens (subset) | 192,000 | 213,504 |
| Output tokens | 4,341 | 4,637 |
| Fixed-rate API-equivalent cost | $0.494915 | $0.523492 |
| Mean exact-site recall / precision | 100% / 100% | 100% / 100% |
| False-complete answers | 0 | 0 |
| Tool calls, including errors | 19 | 18 |
| Post-impact searches / lookups | 3 / 5 | 5 / 3 |

Candidate: **9.4% more aggregate tokens, 11.5% more median-paired tokens,
5.8% higher estimated cost**. Targets were >=25% median-paired token savings
and >=30% aggregate cost savings, without quality loss. Neither passed.
This invocation's total estimated cost is **$1.018407**, not historical spend.

| Pair | Before tokens | After tokens | Token change | Before cost | After cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gin r1 | 73,187 | 77,834 | +6.3% | $0.135520 | $0.131012 |
| Gin r2 | 83,650 | 97,510 | +16.6% | $0.174220 | $0.154043 |
| Django r1 | 53,736 | 41,742 | -22.3% | $0.108723 | $0.085537 |
| Django r2 | 39,505 | 56,581 | +43.2% | $0.076452 | $0.152900 |

## What Happened

Both Django candidate cells autonomously requested eight exact file-scoped
objects in one successful batch; all eight response identities are present,
without scoped errors, misses or omissions. Gin used no scoped objects.
The schema was discoverable without candidate-specific prompting.

Django r1 replaced five lookup requests with one and saved 22.3% of tokens.
But r2's before agent used only impact plus exhaustive text search. The after
agent added a full eight-body lookup before the same search; cost almost doubled.
Gin used more tokens in both repeats. Fewer lookup requests did not reliably
remove evidence acquisition or repeated context processing.

These traces support a next hypothesis, not a proved causal decomposition:
choose evidence depth by task, and avoid loading bodies for pure site enumeration
when contracts and call expressions suffice. Audit remaining coverage gaps
before telling agents to stop earlier. No threshold, scorer or product code
changed during this study. Scoped lookup's correctness/capability proof remains
useful, but this experiment does not establish a token-saving product benefit.

One before/Gin r1 lookup supplied unsupported `context_used`; Prism rejected it,
and the agent recovered. Its usage remains included. All cells emitted the
expected skills-budget notice removing model-visible skill descriptions.
All tool activity was through Prism; no native commands, network/delegation
tool calls, or source edits were observed. These are transcript observations,
not a claim that the harness enforces perfect OS-level read confinement.

Additional coverage question, not a scored failure: after/Gin r1 impact reports
`completeness: closed` with declarations only for `responseWriter.Hijack` and
`responseWriter.CloseNotify`. Its subsequent text search exposes interface-call
sites, including `Context.Stream`. Investigate the Go interface/coverage contract
before classifying all such follow-up searches as redundant. Gin's gold is a
two-function bug-localization answer, not an exhaustive impact oracle.

## Controls, Scope And Verification

See [PROTOCOL.md](PROTOCOL.md) and [manifest](results/manifest.json). Both arms
used Codex CLI 0.153.4, GPT-5.5 medium, identical direct-routing guidance and
fresh pinned archive cells without git history. Only the Prism binary differed.
Two familiar tasks and two repeats are diagnostic, not held-out product proof;
provider caching and stochastic behavior are not controlled. No native or
Sonnet arm ran. Do not pool or compound savings with earlier experiments.
Accuracy here is strict site-set agreement, not executable patch success.

Free preparation verified all eight cells and both MCP preflights. Eight new
wrapper tests, four portable-verifier tests, six frozen analyzer tests and nine
frozen runner tests pass (27 total). The portable verifier was added alongside
execution and does not participate in arm configuration or frozen scoring.
The archive audit reproduces every raw answer/site set and CLI usage total;
all 111 archived checksum checks pass. The older evidence archive also passes
its 638-file/594-check verification unchanged.

```sh
python3 -I -B harness/runs/prism-scoped-lookup-ab-2026-09-06/verify_results.py
python3 -B -m unittest discover -s harness/runs/prism-scoped-lookup-ab-2026-09-06 -p 'test_*.py' -v
```

The first command is read-only and needs no live binary, original checkout or
model access. The wrapper tests exercise the launch wrapper and need its pinned
legacy imports. Re-execution requires a new protocol/run directory and model
authorization; `run` refuses reuse of this completed invocation. Temporary
binaries, corpus copies and indexes are deliberately not in this archive.
Cost is the frozen fixed-rate estimate, not subscription/invoice billing;
long-context premiums are excluded as documented in the protocol.

Next: remain in context-sufficiency work. Audit follow-ups against evidence
already delivered, add free task-depth and coverage fixtures, then compare a
separately frozen candidate. Broad four-way/native acceptance remains unproven.
