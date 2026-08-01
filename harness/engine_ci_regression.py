"""Engine-level change-impact regression check: run `prism change-impact`
(deterministic, no LLM) over the 29-task oracle bed with a candidate prism
binary and score recall/precision against ground truth. Used to verify an
unreleased grove/prism build introduces no regression to the product path.

Usage: PRISM_BIN=/tmp/prism-rip python3 engine_ci_regression.py /tmp/grid29.txt
"""
import json, os, subprocess, sys
from pathlib import Path

HARNESS = Path.home()/"Projects/provasign/research/harness"
sys.path.insert(0, str(HARNESS))
from schema import Answer, Site, Task
from score import score

PRISM = os.environ.get("PRISM_BIN", "/tmp/prism-rip")


def prism_query(task):
    fqn = task.pr.split(":", 1)[1]
    if "#" in fqn:
        type_part, mspec = fqn.split("#", 1)
        return f"{type_part.rsplit('.', 1)[-1]}.{mspec}"
    return fqn


def prism_sites(query, workdir):
    subprocess.run([PRISM, "index", "."], cwd=workdir, capture_output=True, timeout=900)
    r = subprocess.run([PRISM, "change-impact", query, "."],
                       capture_output=True, text=True, cwd=workdir, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"prism: {r.stderr[:200]}")
    data = json.loads(r.stdout)
    sites = []
    for group in ("declarations", "family", "callers", "declaringTypes"):
        for sym in data.get(group, []):
            fp = sym.get("filePath") or sym.get("file", "")
            name = sym.get("name", "")
            if name:
                sites.append(Site.parse(f"{fp}:{name}"))
    return sites


def main(task_list):
    tasks = [l.strip() for l in open(task_list) if l.strip()]
    rows, rec_sum = [], 0.0
    for tp in tasks:
        task = Task.load(HARNESS/tp)
        workdir = Path(task.workdir or task.repo)
        subprocess.run(["git", "-C", str(workdir), "checkout", "-q", task.pin], capture_output=True)
        subprocess.run(["git", "-C", str(workdir), "checkout", "-q", "--", "."], capture_output=True)
        q = prism_query(task)
        try:
            sites = prism_sites(q, workdir)
            ans = Answer(sites=sites, complete=True, unresolved=[])
            sc = score(task, ans, "engine", 1)
            rows.append((task.id, round(sc.recall, 3), round(sc.precision, 3), len(sites)))
            rec_sum += sc.recall
        except Exception as e:
            rows.append((task.id, None, None, str(e)[:80]))
    for r in rows:
        print(f"{r[0]:38} recall={r[1]}  prec={r[2]}  n={r[3]}", flush=True)
    ok = [r for r in rows if isinstance(r[1], float)]
    print(f"\nmean recall over {len(ok)} scored tasks: {rec_sum/len(ok):.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
