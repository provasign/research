# research

Research for the grove/prism direction — a controlled study of **code-graph
(grove/prism) vs. text-search (rg/grep + read) for agentic coding**.

- [`grove-vs-grep-paper-design.md`](grove-vs-grep-paper-design.md) — full study
  & paper design: thesis, 12-variable framework, RQs, hypotheses, threats,
  venue (ACM TOSEM + arXiv). Decisions locked at v0.1.
- [`harness/`](harness/) — the Phase-0 study harness (built + smoke-tested):
  T/G/V tool arms, real-PR task extractor, `claude`-CLI agent runner, and a
  Mode-A scorer that grades agent answers against an **independent**
  compiler-grade oracle (never grove against grove). See
  [`harness/README.md`](harness/README.md).

**Status:** Phase 0 complete. Next: the Phase-1 Grafana pilot.

Private/pre-publication. The harness, tasks, and oracle integration are
intended for release as a reproducible artifact when the paper is submitted.
