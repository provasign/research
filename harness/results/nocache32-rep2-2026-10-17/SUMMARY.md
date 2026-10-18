# nocache32-rep2-2026-10-17

meta: {"manifest": "results/seeded32-manifest.json", "tasks": 32, "arms": ["native", "prism_init"], "ttls": ["nocache"], "model": "claude-sonnet-5-5", "claude_version": "2.1.302 (Claude Code)", "prism_bin": "/Users/tapabratapal/prism-ab-bins/prism-rc-0.87.32", "prism_sha256": "6f2de9e3dce88251", "order_seed": "wide-rep2-2026-10-17", "cache_mode": "no-cache (DISABLE_PROMPT_CACHING=1, repriced)", "started": "2026-10-17 22:52:37"}

| task | native task@5m | prism task@5m | p/n | native solved | prism solved |
|---|---:|---:|---:|---|---|
| seed__click__version_option_kwonly | 0.0436 | 0.0468 | 1.07 | True | True |
| seed__werkzeug__redirect_kwonly | 0.0431 | 0.0352 | 0.82 | True | True |
| wide__chi__Routes_Match | 0.0211 | 0.0199 | 0.94 | True | True |
| seed__rich__stylize_kwonly | 0.0443 | 0.0803 | 1.81 | True | True |
| wide__click__Command_invoke | 0.0652 | 0.0453 | 0.70 | True | True |
| wide__h3__EventStream_push | 0.0410 | 0.0382 | 0.93 | True | True |
| wide__werkzeug__HTTPException_get_headers | 0.0128 | 0.0209 | 1.63 | True | True |
| wide__click__ClickException_format_message | 0.0116 | 0.0211 | 1.82 | True | True |
| wide__rich__Highlighter_highlight | 0.0376 | 0.0413 | 1.10 | True | True |
| wide__werkzeug__BaseConverter_to_url | 0.0296 | 0.0299 | 1.01 | True | True |
| wide__jackson-databind__TypeDeserializer_getTypeInclusion | 0.0508 | 0.0546 | 1.08 | True | True |
| wide__gin__ResponseWriter_Status | 0.0243 | 0.0263 | 1.08 | True | True |
| wide__h3__H3Route_handler | 0.0712 | 0.1044 | 1.46 | True | True |

complete pairs: 13 of 13; prism cheaper on task cost in 4/13
solved: native 13/13, prism 13/13; model requests native 63, prism 67
TASK cost @5m: native $0.496, prism $0.564, prism/native 1.137
TASK cost @1h: native $0.593, prism $0.677, prism/native 1.143
STARTUP per cell @5m: native $0.0579, prism $0.0658 (@1h $0.0926 / $0.1053); reported apart, not a target
cells with unknown cost: 0 []
cells with unknown result (scorer failed): 0 []
