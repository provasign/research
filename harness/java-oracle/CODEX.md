# GPT (Codex) arm — cross-model-family test

Goal: run the **same** jackson change-impact tasks the Claude tiers ran, but with
**GPT models via Codex**, and score them with the **same** independent oracle — so
the numbers slot straight into the paper's tables and answer the obvious reviewer
question: *is the code-graph effect Claude-specific?*

Design parallel: Claude Code was the agent for Claude; **Codex (`codex exec`) is
the agent for GPT**. Same prompts (`arms.py`), same scoring (`rescore_java.py` +
`agg_jackson.py`), same per-run record format.

## Prerequisites (already true on this machine)
- `codex` CLI installed and authenticated (OpenAI).
- `prism` on `PATH` (the G arm calls it) — `which prism`.
- jackson corpus indexed at the pin: `~/gvg-corpus/jackson-databind/.grove` exists
  (rebuild with `prism index ~/gvg-corpus/jackson-databind` if missing).
- Tasks: `tasks/jackson-*.json` (6, sizes 8/22/38/58/104/108).

## Step 1 — smoke test ONE cell, then inspect (important)
Codex's `--json` event schema can differ by version, and the GPT tier's
`graph_used`/tool trace is parsed best-effort from it. Verify on one cell first:
```bash
cd harness
MODEL=gpt-5-codex TRIALS=1 TASKS=jackson-settable-set bash java-oracle/run_codex_pilot.sh
# inspect:
cat runs/jackson-settable-set/gpt-5-codex/G.t1.lastmsg.txt      # should be the JSON answer
head runs/jackson-settable-set/gpt-5-codex/G.t1.events.jsonl    # raw event stream
python3 -c "import json;d=json.load(open('runs/jackson-settable-set/gpt-5-codex/G.t1.json'));print('recall',d['recall'],'graph_used',d['graph_used'],'tools',d['tools_used'])"
```
- If `graph_used` is wrong (e.g. False on a G run that clearly called prism), the
  event-parser needs tuning to your Codex schema: look at `.events.jsonl` and
  adjust `_find_command()` in `run_codex.py` (it scans for command strings).
- If `.lastmsg.txt` isn't clean JSON, the `--output-schema` enforcement isn't
  taking; the scorer still parses the last JSON object, so it usually works
  anyway.

## Step 2 — full grid
```bash
cd harness
MODEL=gpt-5-codex TRIALS=5 bash java-oracle/run_codex_pilot.sh
# (large-first to get the decisive cells early:)
# MODEL=gpt-5-codex TRIALS=5 TASKS="jackson-serialize jackson-deserialize jackson-serializewithtype jackson-writetypeprefix jackson-settable-set jackson-jsonnode-get" bash java-oracle/run_codex_pilot.sh
```
Try whichever GPT model ids you want to compare as tiers (e.g. a frontier and a
smaller/cheaper one); each `--model` value gets its own `runs/<task>/<model>/`
dir and shows up automatically in the aggregator.

## Step 3 — score + aggregate (identical to the Claude path)
```bash
cd harness
for t in jackson-jsonnode-get jackson-settable-set jackson-writetypeprefix \
         jackson-serializewithtype jackson-deserialize jackson-serialize; do
  python3 rescore_java.py --task tasks/$t.json     # MANDATORY: line->method fix
done
python3 agg_jackson.py                             # prints every model incl. GPT
```
`rescore_java.py` is required: prism reports `file:line`, so the GPT graph arm
will answer in line numbers too; without normalization the graph arm is scored ~0.

## What to expect / what it tests
The Claude result: graph ties text on small tasks, wins big on large tasks for
weak models, narrowing to a reliability/cost edge at the frontier (capability ×
blast radius). The GPT arm tests whether that pattern reproduces across model
*families*. Report GPT as additional tiers alongside Haiku/Sonnet/Opus.

## Honest caveats (note these in the paper)
- **Harness confound.** Claude ran under Claude Code; GPT runs under Codex — two
  different agent scaffolds. So a Claude-vs-GPT *level* difference partly reflects
  the harness, not the model. The within-family, within-harness comparison that
  matters — **T vs G at a fixed (model, task)** — is clean, because only the arm's
  tool guidance changes. Frame the GPT arm as "does graph>text-on-large reproduce
  in another (model, harness) family," not "GPT vs Claude."
- **Soft tool gate.** Codex has no per-binary allowlist like Claude's
  `--allowedTools`; T-vs-G is enforced by prompt + post-hoc trace check
  (`violation` flags a G run that never called prism / a T run that did). For a
  hard gate, add `--hide-prism-from-T` (strips prism's dir from PATH on T runs).
- **Sandbox.** Runs use `-s workspace-write` so `prism`'s sqlite/.grove WAL works;
  `--reset-corpus` does `git checkout` between runs to undo any stray edits (Mode
  A forbids edits and we never read the tree, so this is just hygiene).
- **Cost.** Token/USD capture is best-effort from Codex `--json` events. If your
  installed Codex emits `usage`/`token_usage`, `total_cost_usd`/`cost_usd`,
  `duration_ms`, or turn-count fields, `run_codex.py` writes them into the same
  `cost` object used by the Claude runs. If those fields are absent, recall and
  wall-clock remain the cross-family signal.
- **Usage caps.** Codex usage-limit/rate-limit errors are treated like the Claude
  path: `run_codex.py` writes `.usage_wait.json`, sleeps until the reported reset
  time when available (or polls every 15 minutes), then retries the same cell
  instead of scoring the cap as a failed answer.
