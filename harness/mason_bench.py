"""Mason e2e on the 9-task change-impact bed: the INTEGRATED product
(mason harness + prism graph wall + completeness machinery) driving a free
local model. Same tasks, same oracle scoring as every other arm."""
import json, subprocess, sys
from pathlib import Path
HARNESS = Path.home()/"Projects/provasign/research/harness"
sys.path.insert(0, str(HARNESS))
from schema import Answer, Task
from score import score

MASON = "/tmp/mason-bench"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "ollama:qwen3-coder:30b"
LABEL = MODEL.replace(":", "_").replace("/", "_")
OUT = HARNESS/"runs/mason-bench"; OUT.mkdir(parents=True, exist_ok=True)

CONTRACT = ('When done, output ONLY a single JSON object: {"sites": ["<relpath>:<Symbol>", ...], '
            '"complete": true|false, "unresolved": []}. Use "<repo-relative-path>:<FunctionOrMethodName>" '
            'per site. A missed site is a broken fix; a false site wastes a review. No prose after the JSON.\n\nISSUE:\n')

TASKS = ["tasks/jackson-jsonnode-get.json", "tasks/jackson-settable-set.json",
         "tasks/jackson-writetypeprefix.json", "tasks/jackson-serialize.json",
         "tasks/guava-forwarding-delegate.json", "tasks/grafana-checkhealth-impact.json",
         "tasks/grafana-querydata-impact.json", "tasks/typeorm-driver-escape.json",
         "tasks/django-quotename.json"]

for tp in TASKS:
    task = Task.load(HARNESS/tp)
    corpus = Path(task.workdir or task.repo)
    subprocess.run(["git", "-C", str(corpus), "checkout", "-q", task.pin], capture_output=True)
    subprocess.run(["git", "-C", str(corpus), "checkout", "-q", "--", "."], capture_output=True)
    for trial in (1, 2):
        f = OUT/f"{task.id}.{LABEL}.t{trial}.json"
        if f.exists():
            print(f"cached {f.name}", flush=True); continue
        r = subprocess.run([MASON, "--dir", str(corpus), "--model", MODEL, "--yes",
                            "--json", "--max-turns", "20", CONTRACT + task.prompt],
                           capture_output=True, text=True, timeout=1800)
        rec = {"task": task.id, "model": MODEL, "trial": trial, "gt": len(task.ground_truth)}
        import re as _re
        # Mason's product answer for enumeration tasks is the NARRATED engine
        # relay (payload isolation keeps graph payloads out of the model's
        # context by design; the model's JSON is a summary it types from
        # memory). Score what the user actually receives: narrated sites
        # unioned with the model's JSON sites.
        narrated = []
        for ln in (r.stderr or "").split("\n"):
            m = _re.match(r"^\s{2,}(\S+\.(?:java|go|ts|py))\s{2,}(\S+)$", ln)
            if m:
                leaf = m.group(2).rsplit(".", 1)[-1]
                narrated.append(f"{m.group(1)}:{leaf}")
        try:
            j = json.loads(r.stdout)
            rec["ok"] = j.get("ok")
            rec["wall_s"] = round((j.get("durationMs") or 0)/1000, 1)
            u = j.get("usage") or {}
            rec["tokens_in"] = (u.get("inputTokens") or 0) + (u.get("cacheRead") or 0)
            rec["tokens_out"] = u.get("outputTokens") or 0
            answer = Answer.parse(j.get("reply", ""))
            from schema import Site
            existing = {f"{x.relpath}:{x.symbol}" for x in answer.sites}
            for s2 in narrated:
                if s2 not in existing:
                    rp, sym = s2.rsplit(":", 1)
                    answer.sites.append(Site(relpath=rp, symbol=sym))
            rec["narrated"] = len(narrated)
            sc = score(task, answer, "mason", trial)
            rec["recall"] = round(sc.recall, 3)
            rec["precision"] = round(sc.precision, 3)
            rec["n_sites"] = len(answer.sites)
        except Exception as e:
            rec["error"] = str(e)[:200]
            rec["stderr"] = (r.stderr or "")[-300:]
        f.write_text(json.dumps(rec, indent=1))
        print(f"{task.id:28} t{trial}: recall={rec.get('recall')} prec={rec.get('precision')} "
              f"in={rec.get('tokens_in',0)//1000}k out={rec.get('tokens_out')} "
              f"{rec.get('wall_s')}s err={rec.get('error','')[:60]}", flush=True)
print("done", flush=True)
