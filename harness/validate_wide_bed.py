#!/usr/bin/env python3
"""Gold-validation for the mandated-wide-radius bed draft (audit before launch).

Per task (repo, sha, old->new):
  1. worktree at the gold commit
  2. era venv: pip install -e . (timeboxed)
  3. covering tests: test files mentioning the NEW token at the commit;
     run pytest on them -> must PASS (gold green)
  4. falsifiability probe: revert the substitution (new->old) in ~20% of the
     gold-touched code files, rerun the same tests -> must FAIL (red under
     partial sweep). An oracle that stays green when sites are missing
     cannot score completeness.
Outcomes: valid | gold-tests-fail | probe-stays-green | no-covering-tests |
          env-fail | env-too-heavy | timeout
"""
from __future__ import annotations
import json, re, shutil, subprocess, sys, time
from pathlib import Path

DRAFT = Path(__file__).parent / "runs/swebench-live/wide-bed-draft.json"
OUT = Path(__file__).parent / "runs/swebench-live/wide-bed-validation.json"
WORK = Path.home() / ".cache" / "prism-research" / "wide-bed-wt"
TASK_TIMEOUT = 15 * 60
HEAVY = {"pytorch__torchtune"}  # torch install: multi-GB; validate separately
NONPY = {"jackson-databind", "netty", "commons-lang", "gin", "grafana"}

def sh(*a, cwd=None, timeout=600, env=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)

def validate(task):
    repo, sha, old, new = task["repo_path"], task["sha"], task["old"], task["new"]
    name = f'{task["repo"]}-{sha[:8]}'
    wt = WORK / name
    t0 = time.time()
    if task["repo"] in HEAVY:
        return {"outcome": "env-too-heavy"}
    if task["repo"] in NONPY:
        return {"outcome": "non-python-todo"}
    try:
        shutil.rmtree(wt, ignore_errors=True)
        r = sh("git", "-C", repo, "worktree", "add", "--detach", "--force", str(wt), sha)
        if r.returncode:
            return {"outcome": "env-fail", "detail": "worktree: " + r.stderr[:120]}
        # covering tests: test files that mention the NEW token
        g = sh("git", "-C", str(wt), "grep", "-lw", new, "--", "test*", "tests", "*test*")
        tests = [l for l in g.stdout.splitlines() if l.endswith(".py")][:6]
        if not tests:
            return {"outcome": "no-covering-tests"}
        # ERA venv: commit-dated dependency resolution via uv --exclude-newer,
        # and an era-plausible interpreter. Round 1 ran 2019-2024 commits on
        # today's python+deps and every gold failed on environment, not code
        # (pkgutil removals, pydantic v2, conftest rot) — the exact failure
        # class SWE-bench needs per-instance images for; uv's dated resolver
        # is the lightweight version of the same idea.
        cdate = sh("git", "-C", str(wt), "show", "-s", "--format=%cI", sha).stdout.strip()[:10]
        year = int(cdate[:4]) if cdate[:4].isdigit() else 2024
        pyver = "3.9" if year <= 2021 else ("3.10" if year <= 2022 else ("3.11" if year <= 2023 else "3.12"))
        vd = wt / ".venv"
        r = sh("uv", "venv", "--python", pyver, str(vd), timeout=180, cwd=str(wt))
        if r.returncode:
            return {"outcome": "env-fail", "detail": "uv venv: " + r.stderr[-120:]}
        py = str(vd / "bin" / "python")
        uvpip = lambda *pkgs: sh("uv", "pip", "install", "-q", "--python", py,
                                 f"--exclude-newer={cdate}T23:59:59Z", *pkgs,
                                 timeout=420, cwd=str(wt))
        ins = uvpip("-e", ".")
        if ins.returncode:
            ins = uvpip(".")
        if ins.returncode and "exclude-newer" in (ins.stderr or ""):
            # build backend pinned newer than the commit date (Kinto shape):
            # relax the date filter for the install only.
            ins = sh("uv", "pip", "install", "-q", "--python", py, "-e", ".",
                     timeout=420, cwd=str(wt))
        # pytest resolved era-dated too (a 2020 repo + pytest 8 = plugin rot)
        tp = uvpip("pytest")
        if ins.returncode or tp.returncode:
            return {"outcome": "env-fail", "detail": (ins.stderr or tp.stderr).strip().splitlines()[-1][:150] if (ins.stderr or tp.stderr) else "install failed"}
        # test extras / dev requirements, best-effort: round 2 failures were
        # dominated by missing TEST deps, not project deps.
        for extra in ("-e .[dev]", "-e .[test]", "-e .[tests]", "-e .[easy]"):
            uvpip(*extra.split())
        for reqf in list(wt.glob("requirements*test*.txt")) + list(wt.glob("requirements*dev*.txt")) + list(wt.glob("*requirements*/test*.txt")):
            uvpip("-r", str(reqf))
        ignores: list[str] = []
        def run():
            args = [py, "-m", "pytest", "-x", "-q", "--continue-on-collection-errors"]
            for ig in ignores:
                args += ["--ignore", ig]
            return sh(*args, *tests, cwd=str(wt), timeout=420)
        # Iterative env repair: missing test module -> era-dated install and
        # retry; a foreign conftest that fails collection -> ignore its dir.
        base = None
        for _ in range(4):
            base = run()
            if base.returncode == 0:
                break
            blob = base.stdout + base.stderr
            m = re.search(r"No module named '([\w.]+)'", blob)
            if m:
                pkg = m.group(1).split(".")[0]
                if uvpip(pkg).returncode == 0:
                    continue
            m = re.search(r"ERROR ([\w./-]+/conftest\.py)", blob) or                 re.search(r"([\w./-]+/conftest\.py)'?[.:]", blob)
            if m and m.group(1) not in ignores:
                ignores.append(str(Path(m.group(1)).parent))
                continue
            break
        if base is None or base.returncode != 0:
            return {"outcome": "gold-tests-fail", "detail": (base.stdout + base.stderr)[-180:] if base else ""}
        # falsifiability probe: revert new->old in ~20% of gold-touched code files
        show = sh("git", "-C", str(wt), "show", "--format=", "--name-only", sha)
        touched = [f for f in show.stdout.split() if f.endswith(".py") and "test" not in f.lower()]
        # Round-3 lesson (probe-stays-green on conan/trimesh/pipecat): an
        # arbitrary 20% of touched files may not intersect what the covering
        # tests exercise. Rank touched files by whether their MODULE NAME
        # appears in the covering tests' text; revert the exercised ones.
        testtext = ""
        for tf in tests:
            try:
                testtext += (wt / tf).read_text(errors="replace")
            except OSError:
                pass
        def exercised(f):
            stem = Path(f).stem
            return stem != "__init__" and stem in testtext
        touched.sort(key=lambda f: (not exercised(f), f))
        nrev = max(1, len(touched) // 5)
        if any(exercised(f) for f in touched):
            nrev = max(nrev, sum(1 for f in touched if exercised(f)))
        reverted = []
        for f in touched[:nrev]:
            p = wt / f
            if not p.exists():
                continue
            src = p.read_text(errors="replace")
            back = re.sub(rf"\b{re.escape(new)}\b", old, src)
            if back != src:
                p.write_text(back)
                reverted.append(f)
        if not reverted:
            return {"outcome": "probe-impossible", "detail": "no revertible files"}
        probe = run()
        if probe.returncode == 0:
            return {"outcome": "probe-stays-green", "reverted": reverted,
                    "tests": tests, "detail": "oracle does not punish incompleteness"}
        return {"outcome": "valid", "tests": tests, "reverted": reverted,
                "wall_s": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"outcome": "timeout"}
    finally:
        sh("git", "-C", repo, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)

def main():
    draft = json.load(open(DRAFT))
    WORK.mkdir(parents=True, exist_ok=True)
    results = []
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for t in draft["graph"]:
        if only and only not in f"{t['repo']}-{t['sha']}":
            continue
        print(f"== {t['repo']} {t['sha'][:8]} {t['old']}->{t['new']}", flush=True)
        r = validate(t)
        r.update({k: t[k] for k in ("repo", "sha", "old", "new", "sites", "leftover", "subject")})
        results.append(r)
        print(f"   -> {r['outcome']} {r.get('detail','')[:100]}", flush=True)
        json.dump(results, open(OUT if not only else OUT.with_suffix(".probe.json"), "w"), indent=1)
    from collections import Counter
    print("\n", dict(Counter(r["outcome"] for r in results)))

main()
