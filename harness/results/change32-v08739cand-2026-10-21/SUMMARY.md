# change32-v08739cand-2026-10-21

meta: {"manifest": "results/seeded32-manifest.json", "tasks": 32, "arms": ["prism_cli", "prism_cli_b"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "/Users/tapabratapal/prism-ab-bins/prism-v0.87.38", "prism_sha256": "2d1514c55ffd243a", "order_seed": "change32-v08739cand", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-21 20:20:58"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| seed__click__version_option_kwonly | 0.0447 | 0.0380 | 0.85 | True | True |
| seed__werkzeug__redirect_kwonly | 0.0371 | 0.0329 | 0.88 | True | True |
| wide__chi__Routes_Match | 0.0273 | 0.0194 | 0.71 | True | True |
| seed__rich__stylize_kwonly | 0.0619 | 0.0346 | 0.56 | True | True |
| wide__click__Command_invoke | 0.0341 | 0.0301 | 0.88 | True | True |
| wide__h3__EventStream_push | 0.0393 | 0.0361 | 0.92 | True | True |
| wide__werkzeug__HTTPException_get_headers | 0.0295 | 0.0295 | 1.00 | True | True |
| wide__click__ClickException_format_message | 0.0357 | 0.0288 | 0.81 | True | True |
| wide__rich__Highlighter_highlight | 0.0353 | 0.0271 | 0.77 | True | True |
| wide__werkzeug__BaseConverter_to_url | 0.0294 | 0.0231 | 0.79 | True | True |
| wide__jackson-databind__TypeDeserializer_getTypeInclusion | 0.0582 | 0.0534 | 0.92 | True | True |
| wide__gin__ResponseWriter_Status | 0.0364 | 0.0290 | 0.80 | True | True |
| wide__h3__H3Route_handler | 0.0767 | 0.0619 | 0.81 | True | True |
| wide__click__Group_get_command | 0.0221 | 0.0341 | 1.55 | False | True |
| seed__werkzeug__run_simple_app_first | 0.0767 | 0.0830 | 1.08 | True | True |
| wide__hono__SetHeadersOptions_append | 0.0402 | 0.0483 | 1.20 | True | True |
| wide__echo__HTTPStatusCoder_StatusCode | 0.0407 | 0.0333 | 0.82 | True | True |
| wide__rich__ProgressColumn_render | 0.0428 | 0.0288 | 0.67 | True | True |
| wide__hono__Hono_basePath | 0.0374 | 0.0398 | 1.07 | True | True |
| wide__werkzeug__Response_get_data | 0.0450 | 0.0373 | 0.83 | True | True |
| wide__hono__ConnInfo_remote | 0.0566 | 0.0423 | 0.75 | True | True |
| wide__jackson-databind__TypeDeserializer_forProperty | 0.0617 | 0.0598 | 0.97 | True | True |
| wide__jackson-databind__ResolvableDeserializer_resolve | 0.0805 | 0.0663 | 0.82 | True | True |
| wide__jackson-databind__SettableBeanProperty_set | 0.0782 | 0.0856 | 1.10 | True | True |
| wide__hono__Router_match | 0.0552 | 0.0514 | 0.93 | True | True |
| wide__gin__Binding_Name | 0.0465 | 0.0305 | 0.66 | True | True |
| wide__zod__ZodRegistry_get | 0.0736 | 0.0716 | 0.97 | True | True |
| wide__echo__Router_Route | 0.0460 | 0.0313 | 0.68 | True | True |
| wide__zod__ZodTypeInternals_parse | 0.1223 | 0.1159 | 0.95 | True | True |
| wide__jackson-databind__ContextualSerializer_createContextual | 0.0859 | 0.0703 | 0.82 | True | True |
| wide__jackson-databind__ContextualDeserializer_createContextual | 0.0860 | 0.1259 | 1.46 | True | True |
| wide__jackson-databind__JsonSerializer_isEmpty | 0.0891 | 0.0757 | 0.85 | True | True |

complete pairs: 32 of 32; prism cheaper on task cost in 25/32
solved: native 31/32, prism 32/32; model requests native 181, prism 168
TASK cost @5m: native $1.732, prism $1.575, prism/native 0.909
TASK cost @1h: native $2.160, prism $1.945, prism/native 0.900
STARTUP per cell @5m: native $0.0625, prism $0.0626 (@1h $0.1000 / $0.1001); reported apart, not a target
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
