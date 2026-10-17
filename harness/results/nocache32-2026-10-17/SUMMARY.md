# nocache32-2026-10-17

meta: {"manifest": "results/seeded32-manifest.json", "tasks": 32, "arms": ["native", "prism_init"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "~/prism-ab-bins/prism-cand30 (= v0.87.30)", "order_seed": "ttl-2026-10-17", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-17 12:03 (5 pairs) / 12:16 (rest)"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| seed__click__version_option_kwonly | 0.0391 | 0.0393 | 1.00 | True | True |
| seed__werkzeug__redirect_kwonly | 0.0511 | 0.0424 | 0.83 | True | True |
| wide__chi__Routes_Match | 0.0247 | 0.0189 | 0.76 | True | True |
| seed__rich__stylize_kwonly | 0.0553 | 0.0741 | 1.34 | True | True |
| wide__click__Command_invoke | 0.0497 | 0.0330 | 0.66 | True | True |
| wide__h3__EventStream_push | 0.0341 | 0.0419 | 1.23 | True | True |
| wide__werkzeug__HTTPException_get_headers | 0.0187 | 0.0205 | 1.09 | True | True |
| wide__click__ClickException_format_message | 0.0117 | 0.0227 | 1.94 | True | True |
| wide__rich__Highlighter_highlight | 0.0362 | 0.0342 | 0.95 | True | True |
| wide__werkzeug__BaseConverter_to_url | 0.0270 | 0.0233 | 0.86 | True | True |
| wide__jackson-databind__TypeDeserializer_getTypeInclusion | 0.0523 | 0.0472 | 0.90 | True | True |
| wide__gin__ResponseWriter_Status | 0.0402 | 0.0251 | 0.62 | True | True |
| wide__h3__H3Route_handler | 0.1299 | 0.1026 | 0.79 | True | True |
| wide__click__Group_get_command | 0.0304 | 0.0208 | 0.68 | True | True |
| seed__werkzeug__run_simple_app_first | 0.0780 | 0.1066 | 1.37 | True | True |
| wide__hono__SetHeadersOptions_append | 0.0437 | 0.0446 | 1.02 | True | True |
| wide__echo__HTTPStatusCoder_StatusCode | 0.0515 | 0.0401 | 0.78 | True | True |
| wide__rich__ProgressColumn_render | 0.0400 | 0.0428 | 1.07 | True | True |
| wide__hono__Hono_basePath | 0.0509 | 0.0397 | 0.78 | True | True |
| wide__werkzeug__Response_get_data | 0.0358 | 0.0363 | 1.02 | True | True |
| wide__hono__ConnInfo_remote | 0.0444 | 0.0581 | 1.31 | True | True |
| wide__jackson-databind__TypeDeserializer_forProperty | 0.0741 | 0.0724 | 0.98 | True | True |
| wide__jackson-databind__ResolvableDeserializer_resolve | 0.0951 | 0.0799 | 0.84 | True | True |
| wide__jackson-databind__SettableBeanProperty_set | 0.1005 | 0.0762 | 0.76 | True | True |
| wide__hono__Router_match | 0.1492 | 0.0656 | 0.44 | True | True |
| wide__gin__Binding_Name | 0.0478 | 0.0649 | 1.36 | True | True |
| wide__zod__ZodRegistry_get | 0.1155 | 0.0623 | 0.54 | True | True |
| wide__echo__Router_Route | 0.0338 | 0.0267 | 0.79 | True | True |
| wide__zod__ZodTypeInternals_parse | 0.1482 | 0.1240 | 0.84 | True | True |
| wide__jackson-databind__ContextualSerializer_createContextual | 0.1105 | 0.0883 | 0.80 | True | True |
| wide__jackson-databind__ContextualDeserializer_createContextual | 0.0876 | 0.0996 | 1.14 | True | True |
| wide__jackson-databind__JsonSerializer_isEmpty | 0.0924 | 0.1037 | 1.12 | True | True |

complete pairs: 32 of 32; prism cheaper on task cost in 19/32
solved: native 32/32, prism 32/32; model requests native 216, prism 172
TASK cost @5m: native $1.999, prism $1.778, prism/native 0.889
TASK cost @1h: native $2.409, prism $2.197, prism/native 0.912
STARTUP per cell @5m: native $0.0607, prism $0.0684 (@1h $0.0971 / $0.1094); reported apart, not a target
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
