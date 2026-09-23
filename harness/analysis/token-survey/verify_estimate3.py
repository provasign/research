"""(a) how many 'test' turns are toolchain wrangling; (b) did the agent ever run the
oracle test module (task['test_modules']) — split by resolved/failed."""
import json, re, datetime, time
from pathlib import Path
from collections import Counter, defaultdict
ROOT = Path.home() / ".claude" / "projects"
RESDIR = Path("/Users/tapabratapal/Projects/provasign/research/harness/results/guard-fix-run")
TASKS = Path("/Users/tapabratapal/Projects/provasign/research/harness/tasks/e2e")
start = time.mktime(datetime.datetime(2026,9,21,16,48,0).timetuple())
end = time.mktime(datetime.datetime(2026,9,21,21,10,0).timetuple())
files = sorted((f.stat().st_mtime, f) for d in ROOT.iterdir() if d.is_dir() and "e2e-run" in d.name
               for f in d.glob("*.jsonl") if start <= f.stat().st_mtime <= end)
results = json.loads((RESDIR/"results.json").read_text())
RUN = re.compile(r"\b(mvn|gradlew?|go test|pytest|python3? -m pytest|npm test|npm run test|cargo test|make (test|check)|ctest|tox|unittest|jest|mocha|go build|go vet|npm run build|cargo build)\b")
ENV = re.compile(r"(python3? -m venv|pip install|npm (ci|install)|apt-get|brew install|git stash|source .*activate|export \w+=|mvn .*-Djacoco|mvn .*-DskipTests|mvn .*dependency:|mvn .*-o\b|chmod|mkdir /tmp)")
def cmds(f):
    out=[]
    for line in f.read_text(errors="ignore").splitlines():
        try: j=json.loads(line)
        except Exception: continue
        if j.get("type")!="assistant": continue
        for c in ((j.get("message") or {}).get("content") or []):
            if isinstance(c,dict) and c.get("type")=="tool_use" and c.get("name")=="Bash":
                out.append(str((c.get("input") or {}).get("command","")))
    return out
for arm,idx in (("PRISM",1),("NATIVE",0)):
    kinds=Counter(); oracle=defaultdict(Counter)
    for i,task in enumerate(results):
        cs=cmds(files[2*i+idx][1])
        resolved=(task["prism"] if idx else task["native"])["resolved"]; o="resolved" if resolved else "FAILED"
        tj=json.loads((TASKS/f"{task['task']}.json").read_text())
        mods=tj.get("test_modules") or []
        stems=set()
        for m in mods:
            b=Path(m).name; stems.add(b); stems.add(b.rsplit(".",1)[0])
            if b.rsplit(".",1)[0].startswith("test_"): stems.add(b.rsplit(".",1)[0][5:])
        ran_oracle=False; ran_any_test=False; full_suite=False
        for c in cs:
            if not RUN.search(c): continue
            if ENV.search(c) and not re.search(r"(pytest|mvn .*test|go test)\b.*(::|-Dtest=|-run|tests?/)", c): kinds["env/toolchain wrangling"]+=1
            elif re.search(r"(-Dtest=|-run\s|::|tests?/\S+\.(py|js|ts|java)\b|\s-k\s|--tests\s)", c): kinds["targeted test"]+=1
            elif re.search(r"(go build|go vet|mvn\s+(-q\s+)?(compile|test-compile)|npm run build|cargo build)", c) and "test" not in c.split("&&")[-1]: kinds["compile only"]+=1
            else: kinds["full suite / broad"]+=1; full_suite=True
            ran_any_test=True
            if any(s and s in c for s in stems): ran_oracle=True
        oracle[o]["n"]+=1; oracle[o]["ran_oracle_module"]+=ran_oracle; oracle[o]["ran_any_test"]+=ran_any_test; oracle[o]["ran_full_suite"]+=full_suite
    tot=sum(kinds.values())
    print(f"\n=== {arm} arm ===")
    print(f"build/test-ish Bash turns: {tot}  " + ", ".join(f"{k}={v} ({100*v/tot:.0f}%)" for k,v in kinds.most_common()))
    for o,c in oracle.items():
        n=c["n"]; print(f"  {o:8s} n={n:2d}: ran ANY test {c['ran_any_test']}/{n}, ran the ORACLE test module {c['ran_oracle_module']}/{n}, ran a full/broad suite {c['ran_full_suite']}/{n}")
