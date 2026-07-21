"""A/B: unified `prism` task tool (branch task-compiler) vs cached grep baseline.
Arm 'unified' uses the branch binary /tmp/prism-task; baseline cells come from
runs/bench-matrix (already measured, zero new spend)."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path.home()/"Projects/provasign/research/harness"))
import ab_agentic_mcp as cloud
MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"
from schema import Task

CFG = Path("/tmp/ab-agentic-mcp/prism-unified.json")
CFG.write_text(json.dumps({"mcpServers": {"prism": {"type": "stdio",
    "command": "/tmp/prism-task", "args": ["mcp"]}}}))

cloud.ARMS["unified"] = {
    "guidance": ("TOOLS: the Prism MCP server's unified `prism` tool. Call it ONCE with the "
                 "complete task: prism(task=\"<the issue text>\"). It returns change OBLIGATIONS — "
                 "every site that must change, each with a qualified symbol name and file. Union "
                 "every obligation site (plus the obligation's own anchor symbol) into your answer, "
                 "using the site's file path and the symbol's final name segment. If an obligation "
                 "reports completeness other than closed, note it in unresolved. You may pass "
                 "terms=[\"<method name>\"] to seed if the first call misses the anchor."),
    "allowed": ["mcp__prism"],
    "mcp": str(CFG),
}

OUT = Path.home()/"Projects/provasign/research/harness/runs/ab-unified"
OUT.mkdir(parents=True, exist_ok=True)
TASKS = ["tasks/jackson-jsonnode-get.json", "tasks/jackson-settable-set.json",
         "tasks/jackson-writetypeprefix.json", "tasks/jackson-serialize.json",
         "tasks/guava-forwarding-delegate.json", "tasks/grafana-checkhealth-impact.json",
         "tasks/grafana-querydata-impact.json", "tasks/typeorm-driver-escape.json",
         "tasks/django-quotename.json"]
for tp in TASKS:
    task = Task.load(Path.home()/"Projects/provasign/research/harness"/tp)
    corpus = Path(task.workdir or task.repo)
    subprocess.run(["git", "-C", str(corpus), "checkout", "-q", task.pin], capture_output=True)
    subprocess.run(["/tmp/prism-task", "index", str(corpus)], capture_output=True, timeout=900)
    for trial in (1, 2, 3):
        f = OUT/f"{task.id}.{MODEL}.unified.t{trial}.json"
        if f.exists():
            print(f"cached {f.name}"); continue
        rec = cloud.run_arm("unified", task, corpus, MODEL)
        rec.update(task=task.id, model="haiku", trial=trial, gt=len(task.ground_truth))
        f.write_text(json.dumps(rec, indent=2))
        print(f"{task.id} t{trial}: recall={rec.get('recall')} prec={rec.get('precision')} "
              f"turns={rec.get('turns')} in={ (rec.get('tokens_in') or 0)//1000 }k "
              f"out={rec.get('tokens_out')} wall={rec.get('wall_s')}s err={rec.get('error','')[:80]}")
print("done")
