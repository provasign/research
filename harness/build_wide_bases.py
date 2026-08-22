#!/usr/bin/env python3
"""Synthesize sweep-only base commits for the wide-radius bed.

base = gold's TREE with the token substitution REVERTED (new->old on gold's
paired lines), committed with parent = gold^ so the gold commit stays
unreachable-by-discovery in the agent's clone. A perfect sweep reconstructs
gold's tree byte-for-byte; the falsifiability probe already proved partial
sweeps go red. Bundled non-sweep changes in the gold commit (measured:
trimesh's np.sort dtype fix) are pre-applied and can no longer contaminate
the oracle.
"""
import json, re, subprocess, sys
from pathlib import Path

H = Path(__file__).parent
SLICE = H / "runs/swebench-live/slice-wide-pilot.json"
CACHE = Path.home() / ".cache" / "prism-research" / "swebench-repos"

def sh(*a, cwd=None, check=True):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=300)
    if check and r.returncode:
        raise RuntimeError(f"{a}: {r.stderr[:200]}")
    return r

def main():
    tasks = json.load(open(SLICE))
    for t in tasks:
        repo = CACHE / t["cache"]
        wt = Path("/tmp") / f"bedbase-{t['instance_id']}"
        sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt), check=False)
        import shutil; shutil.rmtree(wt, ignore_errors=True)
        sh("git", "-C", str(repo), "worktree", "add", "--detach", "--force", str(wt), t["gold_sha"])
        # revert the substitution on gold's own -/+ paired lines, per file
        diff = sh("git", "-C", str(wt), "show", "--format=", "-U0", t["gold_sha"]).stdout
        cur, reverted = None, 0
        files = set()
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                cur = line[6:]
            elif cur and line.startswith("+") and not line.startswith("+++"):
                after = line[1:]
                before = re.sub(rf"\b{re.escape(t['new'])}\b", t["old"], after)
                if before != after and "test" not in cur.lower():
                    p = wt / cur
                    if p.exists():
                        src = p.read_text(errors="replace")
                        if after + "\n" in src or src.endswith(after):
                            p.write_text(src.replace(after, before))
                            reverted += 1
                            files.add(cur)
        assert reverted >= t.get("min_revert", 5), f"{t['instance_id']}: only {reverted} lines reverted"
        sh("git", "-C", str(wt), "add", "-A")
        # commit with parent = gold^ : gold stays out of the ancestry
        tree = sh("git", "-C", str(wt), "write-tree").stdout.strip()
        parent = sh("git", "-C", str(wt), "rev-parse", t["gold_sha"] + "^").stdout.strip()
        commit = sh("git", "-C", str(wt), "commit-tree", tree, "-p", parent,
                    "-m", "wide-bed base").stdout.strip()
        sh("git", "-C", str(repo), "update-ref", f"refs/bed/{t['instance_id']}", commit)
        t["base_commit"] = commit
        print(f"{t['instance_id']}: reverted {reverted} lines in {len(files)} files -> base {commit[:10]}")
        sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt))
    json.dump(tasks, open(SLICE, "w"), indent=1)
    print("slice updated")

main()
