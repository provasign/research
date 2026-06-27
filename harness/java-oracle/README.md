# Java change-impact oracle (Spoon) + jackson boundary test

Built 2026-06-27 to test the paper's #1 threat-to-validity: does the code graph
beat text where Go couldn't show it — in a polymorphic/reflection-heavy Java
framework, on *name-ambiguous* dispatch where grep over-matches?

## Why this exists
The earlier `commons-lang` tasks were invalid: bare-name `oracle:<name>` GT
conflated unrelated same-named methods (e.g. `StrBuilder.length` vs
`StringUtils.length`), and all targets were *static* (fully greppable). See the
project memory `java-tasks-gt-polluted-and-static`. This oracle replaces bare-name
matching with **Spoon type resolution**: GT = declaration + override family +
*type-resolved* call sites. No pollution (it resolved all ~500 `get`/`set` calls
and kept only the jackson ones; 0 unresolved).

## Toolchain
- JDK 26 via Homebrew (unlinked): `source env.sh` before any java/mvn command.
- `mvn -DskipTests package` → `target/oracle.jar` (Spoon 11.2, shaded).
- Corpus: `~/gvg-corpus/jackson-databind` pinned at `jackson-databind-2.18.8`
  (`0b422144`). Dep classpath: `jackson-cp.txt` (`mvn dependency:build-classpath`).

## Generate a task
```
source env.sh
python3 make_java_task.py --id jackson-settable-set \
  --display 'SettableBeanProperty.set' \
  --target 'com.fasterxml.jackson.databind.deser.SettableBeanProperty#set(Object,Object)'
```
Writes `../tasks/<id>.json` (harness format, GT from the oracle).

## The 4 tasks (grep-ambiguity gradient)
| task | GT | grep ratio | role |
|---|---|---|---|
| jackson-deserialize | 104 | 4.1× | distinctive control |
| jackson-serialize | 108 | 3.1× | distinctive control |
| jackson-settable-set | 22 | 18.5× | ambiguous (graph-favoring) |
| jackson-jsonnode-get | 8 | 63.6× | extreme ambiguity (graph-favoring) |

Hypothesis: graph recall advantage should rise with the grep ratio.

## Run the pilot
```
TRIALS=5 MODEL=haiku PRISM_BIN=~/bin/prism \
  caffeinate -dimsu bash run_jackson_pilot.sh
```
Runs T vs G over all 4 tasks. Scores land in `../runs/<task>/<model>/`.

## Preliminary (haiku, settable-set, n=1 smoke test)
T recall=1.0 (2 tools, grep+read) vs **G recall=0.86, overconfident**. Even on
the ambiguous task, text tied/beat the graph and T's perfect score validates the
GT is clean+achievable. Reinforces the negative result; full pilot in progress.

## Caveats / TODO
- Arm purity: the G arm still sometimes uses grep/find/cat (claude CLI doesn't
  hard-enforce `--allowedTools`). `run.py` flags `violation` when G never touches
  prism; exclude those when aggregating.
- `get(int)` is small (8 sites); consider `get(String)` or a richer ambiguous
  target for more N.
- For the full grid, add Sonnet+Opus after the haiku read.
