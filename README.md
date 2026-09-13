# Provasign Research

Reproducible evaluations of code-graph assistance for coding agents: pinned tasks, independent oracles, deterministic scorers, raw run records, and full transcripts.

The central question is concrete: when an agent must identify every site affected by a code change, how do native search/read tools compare with a typed code graph exposed through task-shaped operations?

## Current evidence

The latest paired nine-task Sonnet sample covers Go, Java, TypeScript, and Python. Prism reached 0.998 mean recall and 0.955 mean precision at $1.28 total estimated cost. Native tools reached 0.683 recall and 0.770 precision at $3.23. Each cell in this sample is one fresh run, so it is evidence for the current release gate rather than a variance estimate.

See [RESULTS.md](RESULTS.md) for the full table, repeated-trial evidence, scoring corrections, and limitations.

## Running a benchmark

There is one standard runner: `harness/bench.py`. It drives Claude (default
`claude-sonnet-5`) and Codex (default `gpt-5.5`), each with Prism registered
as an MCP server or not, against a suite of tasks, and records tokens,
turns, wall time, cost, and correctness for every cell. **Do not write a new
one-off runner script** — add a flag to `bench.py` or a suite under
`harness/tasks/` instead. See [harness/docs/BENCH.md](harness/docs/BENCH.md)
for the full reference; quick start:

```sh
cd harness
python3 bench.py list-suites
python3 bench.py run --suite e2e --phase pilot --preflight-only
python3 bench.py index   # rebuild the cross-run results/index.jsonl
```

## What is in this repository

| Path | Contents |
|---|---|
| [RESULTS.md](RESULTS.md) | Current product-facing results and validity limits |
| [THESIS.md](THESIS.md) | Research claims and falsifiable predictions |
| `harness/tasks/<suite>/*.json` | Task definitions and committed ground truth, grouped by suite (`e2e`, `manual`, `wide`, ...) |
| [harness/README.md](harness/README.md) | Runner, scorer, and oracle documentation |
| `harness/results/` | Scored run records, protocols, artifacts, and transcripts |
| `harness/scoring/impact_oracle.py` | Deterministic engine scoring against a task oracle |
| [paper/paper.tex](paper/paper.tex) | Paper source |
| [LOCAL-MODEL-SETUP.md](LOCAL-MODEL-SETUP.md) | Local model setup |

Language-specific oracle implementations live under `harness/java-oracle`, `harness/ts-oracle`, and `harness/py-oracle`. Task JSON is self-contained for ordinary scoring; regenerate it only when auditing or changing the ground truth.

## Evaluation layers

The repository separates three claims that are easy to blur:

1. **Engine ceiling:** one deterministic graph call is scored directly against the oracle, without an LLM.
2. **Agent accuracy:** an isolated agent session must choose tools and return the required sites.
3. **Agent efficiency:** request tokens, turns, elapsed time, and estimated cost are compared alongside recall and precision.

An efficient incomplete answer is a failed result. Cost comparisons are interpreted only with their accuracy scores.

## Reproduce a task

Prerequisites are Python 3.11+, the relevant pinned subject repository, and the tool or model runner used by the selected arm.

```sh
cd harness

# Deterministic scorer tests
python3 -m unittest discover -s tests

# Score the current Prism engine directly, without an agent
python3 scoring/impact_oracle.py tasks/manual/grafana-querydata-impact.json

# Run fresh agent trials (legacy Mode-A tool-arm study; see harness/docs/MODE-A-STUDY.md)
python3 runners/run.py \
  --task tasks/manual/jackson-serialize.json \
  --arms T Gstar \
  --trials 3 \
  --model sonnet
```

Task files contain the authoritative upstream commit. Local absolute paths from the original machine must be repointed to your own isolated checkout. Java results require the normalization step described in [harness/README.md](harness/README.md) before aggregation.

## Validity rules

- Use isolated repository snapshots and distinct agent sessions for every cell.
- Record invocation and session identifiers so transcript reuse can be audited.
- Run repeated trials before treating an agent-level delta as stable.
- Keep deterministic engine measurements separate from agent measurements.
- Audit the oracle when precision remains unexpectedly low across unrelated engine changes.
- Preserve failed and invalid experiments with an explanation; do not cite their toplines.

Prompt caching may reuse identical static prefixes at the provider. It does not share prior answers or agent conversation state. The freshness audit in `harness/results/impact-oracle-reliability-2026-09-07/` records six distinct sessions, snapshots, and transcript directories.

## Historical studies

The repository retains dated studies and raw artifacts for auditability. Several are historical and should not be mixed with the current release gate:

- [BENCH-MATRIX.md](harness/BENCH-MATRIX.md) — multi-tier change-impact study
- [docs/AB-ENGINE-COMPARISON.md](harness/docs/AB-ENGINE-COMPARISON.md) — cross-engine comparisons
- [docs/AB-LOCAL-CLIS.md](harness/docs/AB-LOCAL-CLIS.md) — local model and CLI experiments
- [docs/SWEBENCH-AB-RESULTS.md](harness/docs/SWEBENCH-AB-RESULTS.md) — excluded because contamination made the topline non-citable
- [docs/PR-REPLAY-FINDINGS.md](harness/docs/PR-REPLAY-FINDINGS.md) — negative result on mining clean tasks from merged PRs

Read the protocol and date beside any historical result before comparing it with current numbers.

## Related repositories

- [Prism](https://github.com/provasign/prism) — agent-facing change intelligence
- [Grove](https://github.com/provasign/grove) — local semantic graph engine
- [Shale](https://github.com/provasign/shale) — local agent-session evidence for pull requests

## License

MIT. See [LICENSE](LICENSE).
