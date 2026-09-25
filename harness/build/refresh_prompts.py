"""Re-derive problem_statement for non-Python e2e tasks from the linked issue (2026-09-24).

java/go/js/c build_task used the PR title + body as the agent prompt until 2026-09-24; PR
bodies routinely describe the fix (23/38 guard-fix-run non-Python prompts named the gold
file). This rewrites problem_statement with build_task.problem_statement (linked issue ->
keyword/backport-linked issue -> PR title) and keeps the old text as
problem_statement_pr_body. Idempotent: tasks already carrying that field are skipped.

Usage: python3 build/refresh_prompts.py [tasks/e2e/*.json ...]
"""
import glob, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_task import problem_statement

files = sys.argv[1:] or sorted(glob.glob("tasks/e2e/*.json"))
for f in files:
    t = json.loads(Path(f).read_text())
    if not isinstance(t, dict) or not t.get("lang") or t.get("lang") == "python":
        continue
    if "problem_statement_pr_body" in t:
        print(f"  (skip) {t['instance_id']}"); continue
    r = subprocess.run(["gh", "pr", "view", str(t["pr"]), "-R", t["repo"], "--json", "title,body"],
                       capture_output=True, text=True)
    if r.returncode:
        print(f"  [ERR ] {t['instance_id']}: {r.stderr[:100]}"); continue
    meta = json.loads(r.stdout)
    new = problem_statement(t["repo"], t["pr"], meta)
    src = "issue" if new.strip() != meta["title"].strip() else "TITLE ONLY"
    t["problem_statement_pr_body"] = t["problem_statement"]
    t["problem_statement"] = new
    t["prompt_source"] = src
    Path(f).write_text(json.dumps(t, indent=2))
    print(f"  [{src:10}] {t['instance_id']:44} {len(t['problem_statement_pr_body']):5d} -> {len(new):5d} chars")
