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

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import json, re, subprocess, sys
from pathlib import Path

H = Path(__file__).parent.parent
SLICE = H / "results/swebench-live/slice-wide-pilot.json"
RUN = H / "results/swebench-live/widepilot"
CACHE = Path.home() / ".cache" / "prism-research" / "swebench-repos"
sys.path.insert(0, str(H))
import validate_wide_bed as V  # era env + repair machinery

def sh(*a, cwd=None, timeout=600):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def _diff_file(line, cur):
    """Track the current file across a unified diff (b/ path; a/ for deletions)."""
    if line.startswith("+++ "):
        p = line[4:].split("\t")[0]
        return cur if p == "/dev/null" else p[2:]
    if line.startswith("--- "):
        p = line[4:].split("\t")[0]
        return cur if p == "/dev/null" else p[2:]
    return cur

def gold_pairs(repo, task):
    """The sweep's (file, -before, +after) line triples: the base->gold delta,
    which the synthetic base construction guarantees is EXACTLY the
    substitution (bundled non-sweep changes live in the base already).
    File-keyed since 2026-09-05: a substitution counted only where gold made
    it — the same line text substituted in some other file is not a hit."""
    old, new = task["old"], task["new"]
    diff = sh("git", "-C", str(repo), "diff", "-U0",
              task["base_commit"], task["gold_sha"]).stdout
    pairs = []
    minus = []
    cur = None
    for line in diff.splitlines():
        nxt = _diff_file(line, cur)
        if nxt != cur:
            cur, minus = nxt, []
            continue
        if line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            if minus:
                b = minus.pop(0)
                if re.sub(rf"\b{re.escape(old)}\b", new, b) == line[1:]:
                    pairs.append((cur, b.strip(), line[1:].strip()))
    return pairs

def agent_lines(diff):
    """{file: (set of +line bodies, list of -line bodies)} from the agent diff."""
    out, cur = {}, None
    for line in diff.splitlines():
        nxt = _diff_file(line, cur)
        if nxt != cur:
            cur = nxt; out.setdefault(cur, (set(), [])); continue
        if cur is None: continue
        if line.startswith("+") and not line.startswith("+++"):
            out[cur][0].add(line[1:].strip())
        elif line.startswith("-") and not line.startswith("---"):
            out[cur][1].append(line[1:].strip())
    return out

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
        by_file = agent_lines(agent_diff)
        hit = sum(1 for f, _, a in pairs if a in by_file.get(f, (set(), []))[0])
        out["sites_gold"] = len(pairs)
        out["sites_hit"] = hit
        # false edits: agent changed lines gold did NOT change in that file
        # (agent minus-lines containing the old token that are not gold
        # minus-lines OF THE SAME FILE)
        gold_minus = {(f, b) for f, b, _ in pairs}
        false_edits = sum(1 for f, (_, minus) in by_file.items() for l in minus
                          if re.search(rf"\b{re.escape(task['old'])}\b", l)
                          and (f, l) not in gold_minus)
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
