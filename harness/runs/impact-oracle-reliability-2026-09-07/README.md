# Impact oracle and reliability audit — 2026-09-07

This run answers three separate questions:

1. Can one deterministic `prism change-impact` call recover an accurate,
   bounded Grafana impact set from an isolated pinned snapshot?
2. Do fresh Sonnet agents consistently choose and relay that operation?
3. Does the previously reported narrow JSONNode overhead survive a fresh,
   paired native-control study?

## Oracle audit

The Grafana ground truths were reviewed against source. They were not copied
from Prism's output.

- QueryData grew from 51 to 70 production sites. Added sites are 14 middleware
  implementations with the exact external SDK signature, `SimulationEngine`,
  a production fake, and three direct handler callers. Excluded same-name Prism
  results have different contracts: the proto transport, a higher-level
  `QueryDataNew` path, and two unrelated local interface declarations.
- CheckHealth grew from 41 to 59 production sites. Added sites are 12 exact
  middleware implementations and six direct callers. The proto transport and
  two unrelated health probes remain excluded.

## Deterministic gate

`impact_oracle.py` archives each task's pinned commit into a fresh repository,
indexes it, makes one call, scores with `score.py`, and enforces recall,
precision, completeness, and response-byte thresholds.

| Task | GT | Recall | Precision | F1 | Bytes | Completeness |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| grafana-querydata-impact | 70 | 1.000 | 0.946 | 0.972 | 30,175 | project-local |
| grafana-checkhealth-impact | 59 | 1.000 | 0.952 | 0.975 | 38,473 | project-local |

Artifact: `../impact-oracle/grafana-current-main.json`.

## Three fresh Grafana trials

Every attempt used a new Claude session ID, random archived snapshot, Git
repository, Prism index, and project transcript directory. No session used
`--resume`. Static global instructions and provider prompt caching were shared;
the cache does not expose another trial's answer or tool results.

| Task | Recall | Precision | Turns | Request tokens | Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| QueryData t1 | 1.000 | 0.959 | 4 | 100,372 | $0.2183 |
| QueryData t2 | 1.000 | 0.959 | 3 | 70,223 | $0.1398 |
| QueryData t3 | 1.000 | 0.933 | 5 | 128,006 | $0.1574 |
| CheckHealth t1 | 1.000 | 0.983 | 6 | 187,624 | $0.2671 |
| CheckHealth t2 | 1.000 | 0.983 | 4 | 106,854 | $0.1810 |
| CheckHealth t3 | 1.000 | 0.983 | 5 | 147,745 | $0.2396 |

All six runs made exactly one `change_impact` call. One CheckHealth run searched
symbols first. Other extra calls inspected heuristic same-name caller evidence.
The earlier severe QueryData recall failures did not reproduce.

Raw records: `../agent-reliability-grafana/` and invocation
`../agent-reliability-grafana/invocations/9c074f24f78648a98b4a93bcb9917b90.json`.

## Fresh paired JSONNode control

The native arm had grep/read/find only. The Prism arm had Prism and Read. Both
used the same prompt, pinned corpus commit, Sonnet alias, scoring contract, and
fresh-snapshot runner.

| Arm | Recall | Precision | Mean turns | Mean request tokens | Mean cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native grep/read | 0.625 | 1.000 | 30.0 | 655,998 | $0.404 |
| Prism | 1.000 | 1.000 | 8.3 | 215,463 | $0.205 |

Prism used 67% fewer request tokens and cost 49% less while recovering all
three sites that the native runs consistently missed. Its three runs still
varied from 87,257 to 390,191 request tokens, so single-run efficiency claims
remain unreliable.

Raw records: `../agent-reliability-jsonnode/` and invocation
`../agent-reliability-jsonnode/invocations/d19c814605224e9fa5932fb7eb6e86b3.json`.

No product code contains task names, corpus paths, oracle sites, or gate-specific
threshold exceptions. The audited sites live only in benchmark task JSON. A
future overload/receiver precision improvement must be general and pass
unrelated fixtures plus the complete release gate.
