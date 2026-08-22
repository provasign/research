#!/usr/bin/env python3
"""Score wide-radius pilot cells: completeness against a proven oracle.

Per (task, arm):
  1. worktree at base (gold's parent), apply the agent's model_patch
  2. restore GOLD's test files (checkout gold_sha -- <test paths>) so the
     oracle is the merged human change's own tests
  3. era venv + repair loop (same machinery gold-validation proved out)
  4. covering tests -> resolved true/false
  5. site coverage: of gold's substituted lines, how many does the agent's
     patch also substitute (findability metric), plus false edits on
     non-sites (the sed-error metric)
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

H = Path(__file__).parent
SLICE = H / "runs/swebench-live/slice-wide-pilot.json"
RUN = H / "runs/swebench-live/widepilot"
CACHE = Path.home() / ".cache" / "prism-research" / "swebench-repos"
sys.path.insert(0, str(H))
import validate_wide_bed as V  # era env + repair machinery

def sh(*a, cwd=None, timeout=600):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def gold_pairs(repo, task):
    """The sweep's (-before,+after) line pairs: the base->gold delta, which
    the synthetic base construction guarantees is EXACTLY the substitution
    (bundled non-sweep changes live in the base already)."""
    old, new = task["old"], task["new"]
    diff = sh("git", "-C", str(repo), "diff", "-U0",
              task["base_commit"], task["gold_sha"]).stdout
    pairs = []
    minus = []
    for line in diff.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            if minus:
                b = minus.pop(0)
                if re.sub(rf"\b{re.escape(old)}\b", new, b) == line[1:]:
                    pairs.append((b.strip(), line[1:].strip()))
    return pairs

def score_cell(task, arm):
    rec_p = RUN / f"{task['instance_id']}.{arm}.json"
    if not rec_p.exists():
        return None
    rec = json.load(open(rec_p))
    repo = CACHE / task["cache"]
    wt = Path.home() / ".cache" / "prism-research" / "wide-pilot-score" / f"{task['instance_id']}__{arm}"
    wt.parent.mkdir(parents=True, exist_ok=True)
    sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt))
    import shutil; shutil.rmtree(wt, ignore_errors=True)
    r = sh("git", "-C", str(repo), "worktree", "add", "--detach", "--force", str(wt), task["base_commit"])
    assert not r.returncode, r.stderr
    out = {"instance_id": task["instance_id"], "arm": arm,
           "turns": rec["turns"], "cost": rec["cost_usd"], "prism_used": rec["prism_used"]}
    try:
        patch = rec["model_patch"]
        if not patch.strip():
            out.update(resolved=False, note="empty patch"); return out
        (wt / ".agent.patch").write_text(patch)
        ap = sh("git", "-C", str(wt), "apply", "--whitespace=nowarn", ".agent.patch")
        if ap.returncode:
            out.update(resolved=False, note="patch failed: " + ap.stderr[:120]); return out
        (wt / ".agent.patch").unlink()
        # gold's TEST files become the oracle
        names = sh("git", "-C", str(repo), "show", "--format=", "--name-only", task["gold_sha"]).stdout.split()
        testfiles = [f for f in names if "test" in f.lower()]
        for f in testfiles:
            sh("git", "-C", str(wt), "checkout", task["gold_sha"], "--", f)
        # --- era env + covering tests via the validated machinery ---
        fake = dict(task); fake["repo_path"] = str(repo); fake["sha"] = task["gold_sha"]
        rc, detail = V.run_covering_tests(wt, fake)
        out["resolved"] = (rc == 0)
        out["oracle_detail"] = detail[-160:]
        # site coverage vs gold
        pairs = gold_pairs(repo, task)
        agent_diff = sh("git", "-C", str(wt), "diff", task["base_commit"], "--", ".").stdout
        agent_plus = {l[1:].strip() for l in agent_diff.splitlines()
                      if l.startswith("+") and not l.startswith("+++")}
        hit = sum(1 for _, a in pairs if a in agent_plus)
        out["sites_gold"] = len(pairs)
        out["sites_hit"] = hit
        # false edits: agent changed lines gold did NOT change (rough: agent
        # minus-lines containing old token that are not gold minus-lines)
        gold_minus = {b for b, _ in pairs}
        agent_minus = [l[1:].strip() for l in agent_diff.splitlines()
                       if l.startswith("-") and not l.startswith("---")]
        false_edits = sum(1 for l in agent_minus
                          if re.search(rf"\b{re.escape(task['old'])}\b", l) and l not in gold_minus)
        out["false_edits"] = false_edits
        return out
    finally:
        sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt))

def main():
    tasks = {t["instance_id"]: t for t in json.load(open(SLICE))}
    results = []
    for tid, t in tasks.items():
        for arm in ("baseline", "prism"):
            r = score_cell(t, arm)
            if r:
                results.append(r)
                print(f"{tid:36} {arm:9} sites {r.get('sites_hit')}/{r.get('sites_gold')} "
                      f"false_edits={r.get('false_edits')} turns={r['turns']} cost={r['cost']:.2f}", flush=True)
    json.dump(results, open(RUN / "pilot-scored.json", "w"), indent=1)

if __name__ == "__main__":
    main()
