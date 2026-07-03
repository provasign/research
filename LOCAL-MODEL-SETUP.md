# Local model setup (Apple M5 Pro, 24 GB) — one engine, many frontends

A stable local-LLM setup that serves **both** everyday coding (VS Code, Codex,
Claude Code) **and** the research harness. One always-on engine (Ollama); every
tool reuses the same models in `~/.ollama/models` (global, not tied to any repo).

```
                 ┌─ VS Code (Continue.dev)   → Ollama  (chat + autocomplete)
   Ollama  ──────┼─ Codex   → codex --oss --local-provider ollama
 (autostart      ├─ Claude Code → LiteLLM (Anthropic-compat shim) → Ollama
  service)       └─ Research   → harness/run_local.py (hard-gated agent loop)
```

## What's installed
- **Ollama** as a login service: `brew services start ollama` (flags set:
  `OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`). API on
  `http://localhost:11434` (native `/api/*` and OpenAI-compatible `/v1/*`).
- Models (`ollama list`):
  - `qwen2.5-coder:14b` — chat / edits / agent (daily driver, ~9 GB).
  - `qwen2.5-coder:1.5b-base` — fast FIM autocomplete (~1 GB).
  - (optional) `qwen3-coder:30b` — stronger agent, ~17 GB, tight on 24 GB.

## Reality check (what local is good at on 24 GB)
- **Excellent:** inline autocomplete, chat/explain, single/whole-file edits,
  offline + privacy-sensitive work.
- **Flaky:** long-horizon *agentic tool use* (driving many tool calls). Local
  models here emit tool calls as freeform text, sometimes malformed — Codex-style
  agent loops work but are unreliable. Escalate the hard 20% to Claude/GPT.
- Rule of thumb: **local for the fast 80%, cloud for the hard 20%.**

## 1) VS Code — Continue.dev (recommended daily driver)
Install the **Continue** extension, then `~/.continue/config.yaml`:
```yaml
name: local
version: 0.0.1
models:
  - name: Qwen2.5 Coder 14B (chat/edit)
    provider: ollama
    model: qwen2.5-coder:14b
    roles: [chat, edit, apply]
  - name: Qwen2.5 Coder 1.5B (autocomplete)
    provider: ollama
    model: qwen2.5-coder:1.5b-base
    roles: [autocomplete]
```
Chat + edits use the 14B; tab-autocomplete uses the 1.5B. No API keys, fully
offline. (Cline/Roo also work if you prefer an in-IDE *agent*; expect the tool-use
flakiness above.)

## 2) Codex CLI — local mode
```bash
codex --oss --local-provider ollama -m qwen2.5-coder:14b       # interactive
codex exec --oss --local-provider ollama -m qwen2.5-coder:14b "…"   # one-shot
```
Handy alias (add to `~/.zshrc`):
```bash
alias lcodex='codex --oss --local-provider ollama -m qwen2.5-coder:14b'
```

## 3) Claude Code CLI — via an Anthropic-compatible shim
Claude Code speaks Anthropic's Messages API, so point it at a local proxy that
translates to Ollama. LiteLLM is the simplest:
```bash
pip install 'litellm[proxy]'
litellm --model ollama/qwen2.5-coder:14b   # serves http://localhost:4000
# then, in another shell:
ANTHROPIC_BASE_URL=http://localhost:4000 ANTHROPIC_API_KEY=sk-local claude
```
Optional/advanced (Claude Code assumes Anthropic-shaped models; behavior with a
14B local model is best-effort). For daily local use, Continue.dev or Codex-`--oss`
are smoother; the shim exists so you *can* keep the Claude Code UX offline.

## 4) Research harness — hard-gated local tier
For the study we do **not** reuse a coding-agent CLI (their tool gate is soft and
their scaffolds differ). `harness/run_local.py` is a minimal neutral agent loop
that talks straight to Ollama with a **hard** arm gate (the T arm is never given
the graph tool) and writes the same run records as the Claude/GPT tiers:
```bash
cd harness
python3 run_local.py --task tasks/jackson-settable-set.json --arms T G --trials 1 \
    --model qwen2.5-coder:14b --workdir ~/gvg-corpus/jackson-databind   # smoke test
# then the full grid + scoring, identical to the other tiers:
python3 run_local.py --task tasks/jackson-serialize.json --arms T G --trials 5 \
    --model qwen2.5-coder:14b --workdir ~/gvg-corpus/jackson-databind
python3 rescore_java.py --task tasks/jackson-serialize.json
python3 agg_jackson.py     # local tier auto-appears next to haiku/sonnet/opus
```
See `harness/run_local.py` header for the tool protocol and caveats. Expect lower
task completion than the cloud tiers (the local model is a genuinely weak tier —
which is exactly the low-capability end the paper's capability-equalizer predicts
the graph should help most, *if* the model can drive the graph at all).

## Managing the service
```bash
brew services list                 # status
brew services restart ollama       # after changing env flags
ollama ps                          # what's loaded in memory now
ollama pull qwen3-coder:30b        # add the stronger model when you want it
```
