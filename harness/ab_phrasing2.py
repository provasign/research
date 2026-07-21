"""Follow-up to ab_phrasing.py: does letting the agent write its OWN task
string (natural tool-calling — the way it already forms grep queries)
recover the vague-prompt collapse, versus being forced to paste the raw
prompt verbatim?

Reuses the same VAGUE prompts and task set. Three arms per task:
  vague_forced   — repeat of the prior test's guidance: paste the prompt
                   verbatim into task=, no rephrasing. (control, should
                   reproduce the ~0.007 / low numbers from ab_phrasing.py)
  vague_natural  — agent is given the raw vague ask as background and told
                   to call prism the way it normally would: form its OWN
                   task description of what it's investigating, informed by
                   whatever it can infer, and pass confirmed terms if it
                   finds them via grep first.
  crisp_natural  — same natural-formulation guidance, crisp prompt, as a
                   ceiling check (should track the original crisp_terms
                   numbers from ab_phrasing.py).
"""
import json, subprocess, sys
from pathlib import Path
HARNESS = Path.home()/"Projects/provasign/research/harness"
sys.path.insert(0, str(HARNESS))
import ab_agentic_mcp as cloud
from schema import Task

CFG = Path("/tmp/ab-agentic-mcp/prism-unified.json")
CFG.write_text(json.dumps({"mcpServers": {"prism": {"type": "stdio",
    "command": "/tmp/prism-task", "args": ["mcp"]}}}))

VAGUE = {
  "grafana-querydata-impact":
    "The datasource query handler is gaining a new field on its request path. "
    "List every site that must change: every implementation of that handler and "
    "every call site that invokes it.",
  "jackson-serialize":
    "The core serializer's main serialize entry point is changing its signature. "
    "List every site that must change: the declaration, every override/implementation, "
    "and every call site.",
}

FORCED = ("Call the prism tool ONCE: prism(task=\"<the task below>\"). Pass ONLY task — "
          "do NOT pass terms, do not rephrase, paste the task text verbatim.")

NATURAL = ("You are investigating the ISSUE below. Before calling the prism tool, "
           "spend a moment (grep/search if needed) to identify what part of the codebase "
           "this concerns. Then call prism ONCE: prism(task=\"<your own description of what "
           "you are investigating, in your own words, informed by what you found>\", "
           "terms=[<any identifiers you have CONFIRMED — leave empty if you found none>]). "
           "This is exactly how you would normally start any codebase task.")

def make_arm(guidance):
    return {"guidance": ("TOOLS: the Prism MCP server's unified `prism` tool, plus grep/read for "
            "discovery. " + guidance +
            " Each obligation site is \"<qualified symbol> <file>\"; answer with the file path and "
            "the symbol's final name segment."),
            "allowed": ["Read", "Grep", "Glob", "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)", "mcp__prism"],
            "mcp": str(CFG)}

ARMS = {
    "vague_forced":  (True,  FORCED),
    "vague_natural": (True,  NATURAL),
    "crisp_natural": (False, NATURAL),
}

OUT = HARNESS/"runs/ab-phrasing2"; OUT.mkdir(parents=True, exist_ok=True)
TASKS = ["tasks/grafana-querydata-impact.json", "tasks/jackson-serialize.json"]
TRIALS = 3

for tp in TASKS:
    task = Task.load(HARNESS/tp)
    corpus = Path(task.workdir or task.repo)
    subprocess.run(["git","-C",str(corpus),"checkout","-q",task.pin], capture_output=True)
    subprocess.run(["/tmp/prism-task","index",str(corpus)], capture_output=True, timeout=900)
    for arm,(vague,guidance) in ARMS.items():
        cloud.ARMS[arm] = make_arm(guidance)
        orig = task.prompt
        if vague:
            task.prompt = VAGUE[task.id]
        for trial in range(1, TRIALS+1):
            f = OUT/f"{task.id}.haiku.{arm}.t{trial}.json"
            if f.exists():
                print(f"cached {f.name}"); continue
            rec = cloud.run_arm(arm, task, corpus, "haiku")
            rec.update(task=task.id, arm=arm, trial=trial, gt=len(task.ground_truth))
            f.write_text(json.dumps(rec, indent=2))
            print(f"{task.id[:22]:22} {arm:14} t{trial}: recall={rec.get('recall')} "
                  f"prec={rec.get('precision')} turns={rec.get('turns')} "
                  f"in={(rec.get('tokens_in') or 0)//1000}k err={rec.get('error','')[:60]}")
        task.prompt = orig
print("done")
