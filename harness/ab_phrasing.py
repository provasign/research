"""Phrasing-sensitivity A/B for the unified `prism` tool.

Four arms per task, same agent (Haiku), same oracle scoring:
  crisp_noterms  — crisp issue text (names the symbol), guidance forbids terms
  crisp_terms    — crisp issue text, guidance requires terms
  vague_noterms  — vague paraphrase (symbol name stripped), forbids terms
  vague_terms    — vague paraphrase, requires terms

The crisp/vague recall gap measures how much retrieval leans on the task being
phrased with the right words; the terms/noterms gap measures whether the
agent's own anchor extraction closes it. Baselines come from the crisp task's
ground truth in either case (the change set is identical; only the prompt wording
differs)."""
import json, subprocess, sys
from pathlib import Path
HARNESS = Path.home()/"Projects/provasign/research/harness"
sys.path.insert(0, str(HARNESS))
import ab_agentic_mcp as cloud
from schema import Task

CFG = Path("/tmp/ab-agentic-mcp/prism-unified.json")
CFG.write_text(json.dumps({"mcpServers": {"prism": {"type": "stdio",
    "command": "/tmp/prism-task", "args": ["mcp"]}}}))

# Vague paraphrases: same change, but the target method NAME is removed so
# retrieval cannot key on it from the task text alone.
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

NOTERMS = ("Call the prism tool ONCE: prism(task=\"<the task below>\"). Pass ONLY task — "
           "do NOT pass terms. Union every obligation site into your answer.")
TERMS   = ("Call the prism tool ONCE: prism(task=\"<the task below>\", terms=[<the identifiers "
           "you would grep for>]). You MUST pass terms with your best anchor names. "
           "Union every obligation site into your answer.")

def make_arm(guidance):
    return {"guidance": ("TOOLS: the Prism MCP server's unified `prism` tool. " + guidance +
            " Each obligation site is \"<qualified symbol> <file>\"; answer with the file path and "
            "the symbol's final name segment."),
            "allowed": ["mcp__prism"], "mcp": str(CFG)}

ARMS = {"crisp_noterms": (False, NOTERMS), "crisp_terms": (False, TERMS),
        "vague_noterms": (True, NOTERMS), "vague_terms": (True, TERMS)}

OUT = HARNESS/"runs/ab-phrasing"; OUT.mkdir(parents=True, exist_ok=True)
TASKS = ["tasks/grafana-querydata-impact.json", "tasks/jackson-serialize.json"]
TRIALS = 3

for tp in TASKS:
    task = Task.load(HARNESS/tp)
    corpus = Path(task.workdir or task.repo)
    subprocess.run(["git","-C",str(corpus),"checkout","-q",task.pin], capture_output=True)
    subprocess.run(["/tmp/prism-task","index",str(corpus)], capture_output=True, timeout=900)
    for arm,(vague,guidance) in ARMS.items():
        cloud.ARMS[arm] = make_arm(guidance)
        # swap the prompt wording for the vague arms
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
