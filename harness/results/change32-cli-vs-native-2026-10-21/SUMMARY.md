# change32-cli-vs-native-2026-10-21

meta: {"manifest": "results/seeded32-manifest.json", "tasks": 32, "arms": ["native", "prism_cli"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "/Users/tapabratapal/prism-ab-bins/prism-v0.87.38", "prism_sha256": "2d1514c55ffd243a", "order_seed": "change32-cli", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-21 18:35:19"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| seed__click__version_option_kwonly | 0.0433 | 0.0370 | 0.85 | True | True |
| seed__werkzeug__redirect_kwonly | 0.0303 | 0.0487 | 1.61 | True | True |
| wide__chi__Routes_Match | 0.0295 | 0.0259 | 0.88 | True | True |
| seed__rich__stylize_kwonly | 0.0831 | 0.0410 | 0.49 | True | True |
| wide__click__Command_invoke | 0.0705 | 0.0302 | 0.43 | True | True |
| wide__h3__EventStream_push | 0.0697 | 0.0427 | 0.61 | True | True |
| wide__werkzeug__HTTPException_get_headers | 0.0143 | 0.0181 | 1.27 | True | False |
| wide__click__ClickException_format_message | 0.0116 | 0.0284 | 2.44 | True | True |
| wide__rich__Highlighter_highlight | 0.0388 | 0.0363 | 0.93 | True | True |
| wide__werkzeug__BaseConverter_to_url | 0.0274 | 0.0329 | 1.20 | True | True |
| wide__jackson-databind__TypeDeserializer_getTypeInclusion | 0.0469 | 0.0531 | 1.13 | True | True |
| wide__gin__ResponseWriter_Status | 0.0298 | 0.0311 | 1.04 | True | True |
| wide__h3__H3Route_handler | 0.0857 | 0.0484 | 0.56 | True | True |
| wide__click__Group_get_command | 0.0270 | 0.0284 | 1.05 | True | True |
| seed__werkzeug__run_simple_app_first | 0.0649 | 0.0666 | 1.02 | True | True |
| wide__hono__SetHeadersOptions_append | 0.0358 | 0.0432 | 1.21 | True | True |
| wide__echo__HTTPStatusCoder_StatusCode | 0.0391 | 0.0467 | 1.19 | True | True |
| wide__rich__ProgressColumn_render | 0.0693 | 0.0379 | 0.55 | True | True |
| wide__hono__Hono_basePath | 0.0503 | 0.0321 | 0.64 | True | True |
| wide__werkzeug__Response_get_data | 0.0499 | 0.0573 | 1.15 | True | True |
| wide__hono__ConnInfo_remote | 0.0678 | 0.0469 | 0.69 | True | True |
| wide__jackson-databind__TypeDeserializer_forProperty | 0.0891 | 0.0695 | 0.78 | True | True |
| wide__jackson-databind__ResolvableDeserializer_resolve | 0.0841 | 0.0673 | 0.80 | True | True |
| wide__jackson-databind__SettableBeanProperty_set | 0.1083 | 0.1059 | 0.98 | True | True |
| wide__hono__Router_match | 0.1196 | 0.0614 | 0.51 | False | True |
| wide__gin__Binding_Name | 0.0539 | 0.0329 | 0.61 | True | True |
| wide__zod__ZodRegistry_get | 0.0973 | 0.1019 | 1.05 | True | True |
| wide__echo__Router_Route | 0.0317 | 0.0370 | 1.17 | True | True |
| wide__zod__ZodTypeInternals_parse | 0.1030 | 0.1176 | 1.14 | True | True |
| wide__jackson-databind__ContextualSerializer_createContextual | 0.1277 | 0.1864 | 1.46 | True | True |
| wide__jackson-databind__ContextualDeserializer_createContextual | 0.1365 | 0.0725 | 0.53 | True | True |
| wide__jackson-databind__JsonSerializer_isEmpty | 0.1297 | 0.0777 | 0.60 | True | True |

complete pairs: 32 of 32; prism cheaper on task cost in 17/32
solved: native 31/32, prism 31/32; model requests native 215, prism 181
TASK cost @5m: native $2.066, prism $1.763, prism/native 0.853
TASK cost @1h: native $2.512, prism $2.186, prism/native 0.870
STARTUP per cell @5m: native $0.0607, prism $0.0625 (@1h $0.0971 / $0.1000); reported apart, not a target

## Adjudicated resolve losses (user ruling after reading both transcripts)

- wide__werkzeug__HTTPException_get_headers: agent-command-error — prism change-impact listed the right sites; the agent's BSD sed 's/\bget_headers\b/.../' matched nothing on macOS (no \b in BSD sed), so no rename happened. Native's sed had no \b. Not caused by prism's answer. (task cost native $None, prism $None; prism calls None; ruled by claude 2026-10-21T18:35:19)

resolve losses ruled a prism success: 0/1; prism solved + ruled-success: 31/32
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
