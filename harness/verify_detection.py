#!/usr/bin/env python3
"""Detection curve for `prism verify`: does the gate catch incomplete diffs?

The claim under test is NOT "the engine finds all sites" (that is measured:
13 CI-gated change-impact ceilings, recall 1.0). It is the separate claim
that verify, run on a working tree, FLAGS a diff that is missing sites.
Evidence before this script: one true exit=1 in 18 replays, in a
hand-built replay, never in a live session.

Method (deterministic, no agent tokens):
  for each gold commit that is a mechanical multi-site change:
    tree := gold's tree                          (a COMPLETE change)
    for k in 1..K:
      revert k of gold's substituted lines       (an INCOMPLETE change)
      run `prism verify --base <gold^>`
      record verdict + whether a reverted line's file:symbol is named
  Also run k=0 (complete diff) to measure FALSE POSITIVES — a gate that
  cries wolf on a complete change is worse than no gate.
"""
from __future__ import annotations
import json, re, shutil, subprocess, sys
from pathlib import Path

H = Path(__file__).parent
CACHE = Path.home() / ".cache" / "prism-research" / "swebench-repos"
PRISM = str(Path.home() / "bin" / "prism")
WORK = Path.home() / ".cache" / "prism-research" / "verifydet"
OUT = H / "runs/swebench-live/verify-detection.json"
KS = [0, 1, 2, 5]

def sh(*a, cwd=None, timeout=600):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def sub_pairs(repo: Path, sha: str, old: str, new: str):
    """gold's (+after) lines that are exactly old->new, with file."""
    diff = sh("git", "-C", str(repo), "show", "--format=", "-U0", sha).stdout
    cur, out = None, []
    minus = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]; minus = []
        elif cur and line.startswith("-") and not line.startswith("---"):
            minus.append(line[1:])
        elif cur and line.startswith("+") and not line.startswith("+++"):
            after = line[1:]
            before = re.sub(rf"\b{re.escape(new)}\b", old, after)
            if before != after and "test" not in cur.lower():
                out.append((cur, before, after))
    return out

def run_case(repo: Path, sha: str, pairs, k: int):
    wt = WORK / f"{repo.name}-{sha[:8]}-k{k}"
    sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt))
    shutil.rmtree(wt, ignore_errors=True)
    r = sh("git", "-C", str(repo), "worktree", "add", "--detach", "--force", str(wt), sha)
    if r.returncode:
        return {"error": "worktree: " + r.stderr[:100]}
    try:
        reverted = []
        for cur, before, after in pairs[:k]:
            p = wt / cur
            if not p.exists():
                continue
            src = p.read_text(errors="replace")
            if after in src:
                p.write_text(src.replace(after, before, 1))
                reverted.append(cur)
        sh(PRISM, "index", ".", cwd=str(wt), timeout=900)
        v = sh(PRISM, "verify", "--base", sha + "^", "--format", "text", cwd=str(wt), timeout=600)
        out = v.stdout + v.stderr
        verdict = "incomplete" if "MISSED SITES" in out else (
                  "review" if "review" in out else (
                  "complete" if "complete" in out or "no missed sites" in out else "unknown"))
        named = sum(1 for f in set(reverted) if Path(f).name in out)
        return {"k": k, "verdict": verdict, "exit": v.returncode,
                "reverted": reverted, "reverted_files_named": named,
                "flagged": verdict == "incomplete"}
    finally:
        sh("git", "-C", str(repo), "worktree", "remove", "--force", str(wt))

def main():
    cands = json.load(open(H / "runs/swebench-live/wide-sweep-candidates.json"))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    picked = [c for c in cands if c.get("leftover") is not None and c["sites"] >= 15][:12]
    if only:
        picked = [c for c in picked if only in c["repo"] or only in c["sha"]][:1]
    results = json.load(open(OUT)) if OUT.exists() and not only else []
    WORK.mkdir(parents=True, exist_ok=True)
    for c in picked:
        repo = CACHE / c["repo"] if (CACHE / c["repo"]).exists() else Path(c["repo_path"])
        pairs = sub_pairs(repo, c["sha"], c["old"], c["new"])
        if len(pairs) < max(KS):
            print(f"skip {c['repo']} {c['sha'][:8]}: only {len(pairs)} revertible pairs", flush=True)
            continue
        for k in KS:
            r = run_case(repo, c["sha"], pairs, k)
            r.update({"repo": c["repo"], "sha": c["sha"][:10], "sub": f"{c['old']}->{c['new']}",
                      "pairs_available": len(pairs)})
            results.append(r)
            print(f"{c['repo'][:26]:26} {c['sha'][:8]} k={k}: verdict={r.get('verdict')} "
                  f"flagged={r.get('flagged')} named={r.get('reverted_files_named')}/{k} {r.get('error','')}", flush=True)
            json.dump(results, open(OUT, "w"), indent=1)
    # summary
    byk = {}
    for r in results:
        if "k" not in r: continue
        byk.setdefault(r["k"], []).append(r)
    print("\nDETECTION CURVE:")
    for k in sorted(byk):
        rs = byk[k]; fl = sum(1 for r in rs if r["flagged"])
        label = "FALSE POSITIVE rate" if k == 0 else "detection"
        print(f"  k={k} sites missing: {fl}/{len(rs)} flagged   ({label})")

main()
