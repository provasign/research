# nocache-issue42-2026-10-17

meta: {"manifest": "results/issue42-manifest.json", "tasks": 41, "arms": ["native", "prism_init"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "/Users/tapabratapal/prism-ab-bins/prism-main-6aa4400", "prism_sha256": "a1ad26325bb668f6", "order_seed": "ttl-2026-10-17", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-17 14:29:19"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| gin-gonic__gin__pr4698 | 0.0378 | 0.0172 | 0.46 | True | True |
| urfave__cli__pr2419 | 0.0155 | 0.0196 | 1.26 | False | False |
| google__gson__pr3067 | 0.0222 | 0.0187 | 0.84 | True | True |
| apache__dubbo__pr16350 | 0.0222 | 0.0126 | 0.57 | True | True |
| colinhacks__zod__pr6439 | 0.0216 | 0.0227 | 1.05 | True | True |
| labstack__echo__pr3006 | 0.0177 | 0.0169 | 0.95 | True | True |
| honojs__hono__pr5373 | 0.0196 | 0.0227 | 1.16 | True | True |
| urfave__cli__pr2440 | 0.0373 | 0.0446 | 1.20 | True | True |
| colinhacks__zod__pr6129 | 0.0486 | 0.0480 | 0.99 | True | False |
| FasterXML__jackson-databind__pr6186 | 0.0152 | 0.0201 | 1.32 | True | True |
| honojs__hono__pr5366 | 0.0299 | 0.0265 | 0.89 | True | True |
| go-chi__chi__pr1029 | 0.0205 | 0.0359 | 1.75 | True | True |
| apache__dubbo__pr16391 | 0.0158 | 0.0164 | 1.04 | True | True |
| FasterXML__jackson-databind__pr6030 | 0.0482 | 0.0432 | 0.90 | False | False |
| FasterXML__jackson-databind__pr6102 | 0.0344 | 0.0401 | 1.16 | True | True |
| go-chi__chi__pr1158 | 0.0283 | 0.0400 | 1.41 | True | True |
| urfave__cli__pr2355 | 0.0434 | 0.0472 | 1.09 | True | True |
| FasterXML__jackson-databind__pr6056 | 0.0610 | 0.0516 | 0.84 | True | True |
| FasterXML__jackson-databind__pr6039 | 0.0384 | 0.0391 | 1.02 | True | True |
| FasterXML__jackson-databind__pr6155 | 0.0305 | 0.0175 | 0.57 | True | True |
| FasterXML__jackson-databind__pr6042 | 0.1294 | 0.2887 | 2.23 | False | True |
| FasterXML__jackson-databind__pr6138 | 0.0384 | 0.0457 | 1.19 | True | True |
| gin-gonic__gin__pr4702 | 0.0168 | 0.0161 | 0.96 | True | True |
| honojs__hono__pr5164 | 0.0313 | 0.0486 | 1.55 | True | True |
| colinhacks__zod__pr6144 | 0.0391 | 0.0408 | 1.04 | True | True |
| honojs__hono__pr5199 | 0.0239 | 0.0272 | 1.14 | True | True |
| google__gson__pr3116 | 0.0627 | 0.0311 | 0.50 | False | False |
| google__gson__pr3112 | 0.0408 | 0.0328 | 0.81 | False | False |
| apache__dubbo__pr16395 | 0.0491 | 0.0258 | 0.52 | False | False |
| FasterXML__jackson-databind__pr6061 | 0.0369 | 0.0397 | 1.08 | False | False |
| google__gson__pr3059 | 0.0388 | 0.0245 | 0.63 | False | False |
| urllib3__urllib3__pr3786 | 0.0796 | 0.1240 | 1.56 | False | False |
| FasterXML__jackson-databind__pr6044 | 0.2792 | 0.2028 | 0.73 | False | False |
| colinhacks__zod__pr6500 | 0.0846 | 0.1358 | 1.60 | False | False |
| pydantic__pydantic__pr13516 | 0.0361 | 0.0298 | 0.83 | False | False |
| google__gson__pr3098 | 0.1764 | 0.1344 | 0.76 | False | False |
| FasterXML__jackson-dataformat-xml__pr885 | 0.0209 | 0.0165 | 0.79 | False | False |
| FasterXML__jackson-databind__pr6076 | 0.0758 | 0.1357 | 1.79 | False | False |
| urllib3__urllib3__pr5093 | 0.0441 | 0.0516 | 1.17 | False | False |
| FasterXML__jackson-databind__pr6215 | 0.0290 | 0.0235 | 0.81 | False | False |
| apache__dubbo__pr16325 | 0.0917 | 0.1754 | 1.91 | False | False |

complete pairs: 41 of 41; prism cheaper on task cost in 19/41
solved: native 23/41, prism 23/41; model requests native 248, prism 243
TASK cost @5m: native $2.033, prism $2.251, prism/native 1.107
TASK cost @1h: native $2.380, prism $2.668, prism/native 1.121
STARTUP per cell @5m: native $0.0609, prism $0.0688 (@1h $0.0975 / $0.1100); reported apart, not a target

## Adjudicated resolve losses (user ruling after reading both transcripts)

- colinhacks__zod__pr6129: prism success (model judgment, not a prism failure) — both prism answers were correct and complete (ZodDate in classic+mini schemas; both core check constructors in checks.ts); the agent then Read checks.ts itself and chose to fix the classic wrapper (schemas.ts min/max wrap in new Date) instead of the shared core origin (gold, which native chose today). Same task split the other way on 2026-10-11. (task cost native $0.0486, prism $0.048; prism calls 2; ruled by Topo 2026-10-17 14:35)

resolve losses ruled a prism success: 1/1; prism solved + ruled-success: 24/41
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
