"""H1: for the 12 hard-core-failure tasks, compare the agent's diff to the gold
patch. Bucket: wrong file(s) / right file wrong region / right region (still failed
for another reason, e.g. incomplete or subtly wrong)."""
import json, re
from pathlib import Path

HARNESS = Path("/Users/tapabratapal/Projects/provasign/research/harness")
TASKS = HARNESS/"tasks/e2e"
RESULTS = HARNESS/"results/e2e"

HARD_CORE = [
    "FasterXML__jackson-databind__pr6018", "FasterXML__jackson-databind__pr6044",
    "FasterXML__jackson-databind__pr6052", "FasterXML__jackson-databind__pr6076",
    "akheron__jansson__pr740", "apache__commons-lang__pr1655",
    "apache__commons-lang__pr1703", "gin-gonic__gin__pr4535",
    "gin-gonic__gin__pr4805", "pallets__click__pr3473",
    "pallets__click__pr3504", "pallets__click__pr3678",
]

DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.M)
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)

def files_and_hunks(diff_text):
    files = {}
    blocks = re.split(r"(?=^diff --git )", diff_text, flags=re.M)
    for b in blocks:
        m = DIFF_FILE_RE.match(b)
        if not m: continue
        f = m.group(2)
        hunks = [(int(h[2]), int(h[2]) + int(h[3] or 1) - 1) for h in HUNK_RE.findall(b)]
        files[f] = hunks
    return files

def overlap(hunksA, hunksB, slack=3):
    for a0, a1 in hunksA:
        for b0, b1 in hunksB:
            if a0 - slack <= b1 and b0 <= a1 + slack:
                return True
    return False

for t in HARD_CORE:
    task = json.loads((TASKS/f"{t}.json").read_text())
    gold = files_and_hunks(task.get("patch") or "")
    diff_path = RESULTS/f"{t}.sonnet.prism_body_exp.diff"
    if not diff_path.exists():
        print(f"{t}: NO DIFF FILE"); continue
    agent = files_and_hunks(diff_path.read_text())
    gold_files = set(gold); agent_files = set(agent)
    common = gold_files & agent_files
    verdict = "EMPTY DIFF (no changes)" if not agent_files else (
        "WRONG FILE(S)" if not common else (
            "RIGHT FILE, WRONG REGION" if not any(overlap(gold[f], agent[f]) for f in common) else
            "RIGHT FILE+REGION (still failed)"
        )
    )
    print(f"\n{t}  ::  {verdict}")
    print(f"  gold touches:  {sorted(gold_files)}")
    print(f"  agent touches: {sorted(agent_files)}")
    if common:
        for f in common:
            print(f"    {f}: gold_hunks={gold[f]} agent_hunks={agent[f]} overlap={overlap(gold[f],agent[f])}")
