# nocache-issue42-grepshape-2026-10-17

meta: {"manifest": "results/issue42-manifest.json", "tasks": 41, "arms": ["native", "prism_init"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "/Users/tapabratapal/prism-ab-bins/prism-grepshape-e5c62de", "prism_sha256": "313d2c0708d3f578", "order_seed": "ttl-2026-10-17", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-17 19:15:43", "note": "prism cells only; native cells copied from nocache-issue42-2026-10-17 (same isolated method, same day)", "search_shape": "grep (PRISM_SEARCH_SHAPE via ldflags)"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| gin-gonic__gin__pr4698 | 0.0378 | 0.0225 | 0.59 | True | True |
| urfave__cli__pr2419 | 0.0155 | 0.0176 | 1.13 | False | False |
| google__gson__pr3067 | 0.0222 | 0.0195 | 0.88 | True | True |
| apache__dubbo__pr16350 | 0.0222 | 0.0133 | 0.60 | True | True |
| colinhacks__zod__pr6439 | 0.0216 | 0.0227 | 1.05 | True | True |
| labstack__echo__pr3006 | 0.0177 | 0.0175 | 0.99 | True | True |
| honojs__hono__pr5373 | 0.0196 | 0.0191 | 0.97 | True | True |
| urfave__cli__pr2440 | 0.0373 | 0.0331 | 0.89 | True | True |
| colinhacks__zod__pr6129 | 0.0486 | 0.0509 | 1.05 | True | True |
| FasterXML__jackson-databind__pr6186 | 0.0152 | 0.0206 | 1.35 | True | True |
| honojs__hono__pr5366 | 0.0299 | 0.0273 | 0.91 | True | True |
| go-chi__chi__pr1029 | 0.0205 | 0.0234 | 1.15 | True | True |
| apache__dubbo__pr16391 | 0.0158 | 0.0162 | 1.03 | True | True |
| FasterXML__jackson-databind__pr6030 | 0.0482 | 0.0606 | 1.26 | False | False |
| FasterXML__jackson-databind__pr6102 | 0.0344 | 0.0396 | 1.15 | True | True |
| go-chi__chi__pr1158 | 0.0283 | 0.0261 | 0.92 | True | True |
| urfave__cli__pr2355 | 0.0434 | 0.0306 | 0.70 | True | True |
| FasterXML__jackson-databind__pr6056 | 0.0610 | 0.0461 | 0.76 | True | True |
| FasterXML__jackson-databind__pr6039 | 0.0384 | 0.0368 | 0.96 | True | True |
| FasterXML__jackson-databind__pr6155 | 0.0305 | 0.0338 | 1.11 | True | True |
| FasterXML__jackson-databind__pr6042 | 0.1294 | 0.1127 | 0.87 | False | False |
| FasterXML__jackson-databind__pr6138 | 0.0384 | 0.0389 | 1.01 | True | True |
| gin-gonic__gin__pr4702 | 0.0168 | 0.0164 | 0.98 | True | True |
| honojs__hono__pr5164 | 0.0313 | 0.0298 | 0.95 | True | True |
| colinhacks__zod__pr6144 | 0.0391 | 0.0402 | 1.03 | True | True |
| honojs__hono__pr5199 | 0.0239 | 0.0302 | 1.26 | True | True |
| google__gson__pr3116 | 0.0627 | 0.0314 | 0.50 | False | False |
| google__gson__pr3112 | 0.0408 | 0.0296 | 0.73 | False | False |
| apache__dubbo__pr16395 | 0.0491 | 0.0785 | 1.60 | False | False |
| FasterXML__jackson-databind__pr6061 | 0.0369 | 0.0342 | 0.93 | False | False |
| google__gson__pr3059 | 0.0388 | 0.0329 | 0.85 | False | False |
| urllib3__urllib3__pr3786 | 0.0796 | 0.0991 | 1.25 | False | False |
| FasterXML__jackson-databind__pr6044 | 0.2792 | 0.2931 | 1.05 | False | False |
| colinhacks__zod__pr6500 | 0.0846 | 0.1187 | 1.40 | False | True |
| pydantic__pydantic__pr13516 | 0.0361 | 0.0281 | 0.78 | False | False |
| google__gson__pr3098 | 0.1764 | 0.1613 | 0.91 | False | True |
| FasterXML__jackson-dataformat-xml__pr885 | 0.0209 | 0.0208 | 1.00 | False | False |
| FasterXML__jackson-databind__pr6076 | 0.0758 | 0.1497 | 1.98 | False | False |
| urllib3__urllib3__pr5093 | 0.0441 | 0.0471 | 1.07 | False | False |
| FasterXML__jackson-databind__pr6215 | 0.0290 | 0.0236 | 0.81 | False | False |
| apache__dubbo__pr16325 | 0.0917 | 0.1625 | 1.77 | False | False |

complete pairs: 41 of 41; prism cheaper on task cost in 22/41
solved: native 23/41, prism 25/41; model requests native 248, prism 242
TASK cost @5m: native $2.033, prism $2.156, prism/native 1.061
TASK cost @1h: native $2.380, prism $2.558, prism/native 1.075
STARTUP per cell @5m: native $0.0609, prism $0.0688 (@1h $0.0975 / $0.1100); reported apart, not a target
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
