# nocache-issue42-rep2-2026-10-17

meta: {"manifest": "results/issue42-manifest.json", "tasks": 41, "arms": ["native", "prism_init"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "/Users/tapabratapal/prism-ab-bins/prism-rc-0.87.32", "prism_sha256": "6f2de9e3dce88251", "order_seed": "rep2-2026-10-17", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-17 21:36:56"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| gin-gonic__gin__pr4698 | 0.0263 | 0.0172 | 0.66 | True | True |
| urfave__cli__pr2419 | 0.0207 | 0.0198 | 0.95 | False | False |
| google__gson__pr3067 | 0.0245 | 0.0197 | 0.80 | True | True |
| apache__dubbo__pr16350 | 0.0219 | 0.0196 | 0.90 | True | True |
| colinhacks__zod__pr6439 | 0.0204 | 0.0212 | 1.04 | True | True |
| labstack__echo__pr3006 | 0.0234 | 0.0179 | 0.77 | True | True |
| honojs__hono__pr5373 | 0.0198 | 0.0233 | 1.17 | True | True |
| urfave__cli__pr2440 | 0.0274 | 0.0431 | 1.57 | True | True |
| colinhacks__zod__pr6129 | 0.0791 | 0.0521 | 0.66 | True | True |
| FasterXML__jackson-databind__pr6186 | 0.0148 | 0.0217 | 1.47 | True | True |
| honojs__hono__pr5366 | 0.0283 | 0.0294 | 1.04 | True | True |
| go-chi__chi__pr1029 | 0.0264 | 0.0207 | 0.78 | True | True |
| apache__dubbo__pr16391 | 0.0157 | 0.0165 | 1.05 | True | True |
| FasterXML__jackson-databind__pr6030 | 0.0703 | 0.0595 | 0.85 | False | False |
| FasterXML__jackson-databind__pr6102 | 0.0391 | 0.0386 | 0.99 | True | True |
| go-chi__chi__pr1158 | 0.0372 | 0.0275 | 0.74 | True | True |
| urfave__cli__pr2355 | 0.0596 | 0.0588 | 0.99 | True | True |
| FasterXML__jackson-databind__pr6056 | 0.0518 | 0.0739 | 1.43 | True | True |
| FasterXML__jackson-databind__pr6039 | 0.0405 | 0.0392 | 0.97 | True | True |
| FasterXML__jackson-databind__pr6155 | 0.0147 | 0.0234 | 1.59 | True | True |
| FasterXML__jackson-databind__pr6042 | 0.1103 | 0.1249 | 1.13 | True | False |
| FasterXML__jackson-databind__pr6138 | 0.0529 | 0.0497 | 0.94 | True | True |
| gin-gonic__gin__pr4702 | 0.0172 | 0.0166 | 0.96 | True | True |
| honojs__hono__pr5164 | 0.0513 | 0.0486 | 0.95 | True | True |
| colinhacks__zod__pr6144 | 0.0240 | 0.0445 | 1.85 | True | True |
| honojs__hono__pr5199 | 0.0208 | 0.0299 | 1.44 | True | True |
| google__gson__pr3116 | 0.0553 | 0.0475 | 0.86 | False | False |
| google__gson__pr3112 | 0.0332 | 0.0413 | 1.25 | False | False |
| apache__dubbo__pr16395 | 0.0666 | 0.1094 | 1.64 | False | False |
| FasterXML__jackson-databind__pr6061 | 0.0305 | 0.0361 | 1.18 | False | False |
| google__gson__pr3059 | 0.0280 | 0.0299 | 1.07 | False | False |
| urllib3__urllib3__pr3786 | 0.0791 | 0.0689 | 0.87 | False | False |
| FasterXML__jackson-databind__pr6044 | 0.1979 | 0.2973 | 1.50 | False | False |

complete pairs: 33 of 33; prism cheaper on task cost in 17/33
solved: native 24/33, prism 23/33; model requests native 189, prism 188
TASK cost @5m: native $1.429, prism $1.588, prism/native 1.111
TASK cost @1h: native $1.672, prism $1.887, prism/native 1.129
STARTUP per cell @5m: native $0.0598, prism $0.0677 (@1h $0.0958 / $0.1084); reported apart, not a target

## Adjudicated resolve losses (user ruling after reading both transcripts)

- FasterXML__jackson-databind__pr6042: reviewed, run continues (not a prism success claim) — native solved, prism did not. Both edited the gold file StringCollectionDeserializer.java; prism's first read located it. Prism's final edit delegated to _parseString while native's reported the original START_ARRAY via MismatchedInputException, which the hidden tests require. A model-judgment difference, not a retrieval miss. Trend check at pair 21: cumulative task ratio 0.995 (stop above 1.15), prism one solve behind native (stop at three). (task cost native $0.1103, prism $0.1249; prism calls None; ruled by Claude, applying Topo's trend rule 2026-10-17 21:40)

resolve losses ruled a prism success: 0/1; prism solved + ruled-success: 23/33
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
