#!/usr/bin/env python3
"""Warm the agent's Maven seed repo and prove each Java task builds offline.

run_e2e gives every Java cell a fresh local repository chained onto two
read-only tails: the scorer's cache (~/.m2-eval/repository) and a
harness-owned seed (~/.m2-agent-seed). The seed holds what the HOST build
needs beyond the scorer's cache (host maven / mvnw default plugin versions,
compile-only plugins). Per task, exactly as the agent gets it (run_e2e
_worktree + _pin_java_worktree + _agent_env):

  warm    online, head = the seed:   mvn -q test -Dtest=<F2P class>
  verify  offline, fresh empty head: mvn -q -o -DskipTests compile
                                     ./mvnw -o test -Dtest=<F2P class> (mvn if no wrapper)

test_patch is applied first so the F2P class exists. A task passes when
neither offline step fails on resolution and the F2P class runs (its tests
are expected to fail: no fix is applied). Maven jobs run
one at a time.

  python3 build/warm_agent_m2.py results/v0831-lang-manifest.json [more manifests]
  python3 build/warm_agent_m2.py --verify-only --ids A,B manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

H = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(H / "runners"))
_argv, sys.argv = sys.argv, sys.argv[:1]
import run_e2e  # noqa: E402
sys.argv = _argv

RESOLUTION_ERR = re.compile(
    r"Non-resolvable|Could not resolve|could not be resolved|Cannot access .* in offline mode|"
    r"was not found in .* during a previous attempt|Unresolveable build extension|"
    r"Plugin .* or one of its dependencies could not be resolved|UnresolvableModelException|"
    r"Could not transfer|Could not find artifact|offline mode and the artifact|"
    r"Unknown host|Failed to read artifact descriptor|Could not download")


def _module(task) -> str | None:
    """Reactor module of the first test file (dubbo is multi-module)."""
    f = task["test_modules"][0]
    return f.split("/src/test/")[0] if "/src/test/" in f else None


def _mvn(wt: Path, env: dict, args: str, wrapper: bool = False, timeout: int = 1800) -> tuple[int, str, float]:
    exe = "./mvnw" if wrapper and (wt / "mvnw").exists() else "mvn"
    t0 = time.monotonic()
    r = subprocess.run(["bash", "-c", f"{exe} {args} 2>&1 | tail -60; exit ${{PIPESTATUS[0]}}"],
                       cwd=wt, env=env, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr, round(time.monotonic() - t0, 1)


def run_task(task: dict, warm: bool) -> dict:
    rec = {"task": task["instance_id"]}
    _, wt = run_e2e._worktree(task)
    try:
        rec["pinned"] = run_e2e._pin_java_worktree(wt, task)
        # the F2P class usually arrives with test_patch; apply it so the test
        # step runs it (it should fail -- no fix applied)
        subprocess.run(["git", "-C", str(wt), "apply", "--whitespace=nowarn"],
                       input=task["test_patch"], text=True, check=True, capture_output=True)
        env, rt = run_e2e._agent_env(wt, task)
        rec["jdk"] = rt["java"]
        cls = task["fail_to_pass"][0].split("::")[0].split(":", 1)[-1].rsplit(".", 1)[-1]
        mod = _module(task)
        pl = f"-pl {mod} -am " if mod else ""
        test = (f"{pl}test -Dtest={cls} -Dsurefire.failIfNoSpecifiedTests=false "
                "-DfailIfNoTests=false")
        if warm:
            wenv = dict(env)
            wenv["MAVEN_OPTS"] = re.sub(r"-Dmaven\.repo\.local=\S+",
                                        f"-Dmaven.repo.local={run_e2e.AGENT_M2_SEED}", env["MAVEN_OPTS"])
            wenv["MAVEN_OPTS"] = re.sub(r"-Dmaven\.repo\.local\.tail=\S+",
                                        f"-Dmaven.repo.local.tail={run_e2e.SCORER_M2_REPO}", wenv["MAVEN_OPTS"])
            rc, out, s = _mvn(wt, wenv, "-q " + test)
            rc2, out2, s2 = _mvn(wt, wenv, "-q " + test, wrapper=True)
            rec["warm"] = {"rc": rc, "s": s, "wrapper_rc": rc2, "wrapper_s": s2}
            subprocess.run(["git", "-C", str(wt), "clean", "-qfdX"], check=False)  # build output only
        # offline, with the per-cell head exactly as the agent gets it (empty)
        rc, out, s = _mvn(wt, env, f"-q -o -DskipTests {pl}compile")
        rec["compile"] = {"rc": rc, "s": s, "resolution_error": bool(RESOLUTION_ERR.search(out))}
        if rc:
            rec["compile"]["tail"] = out[-1500:]
        rc, out, s = _mvn(wt, env, f"-o {test}", wrapper=True)
        m = re.findall(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)", out)
        # once surefire reports a run, resolution succeeded; the pattern can
        # otherwise match a test's own exception text (xml pr829)
        rec["test"] = {"rc": rc, "s": s, "resolution_error": bool(RESOLUTION_ERR.search(out)) and not m,
                       "wrapper": (wt / "mvnw").exists(), "tests_run": m[-1] if m else None}
        if rec["test"]["resolution_error"] or not m:
            rec["test"]["tail"] = out[-1500:]
        # compile may fail for reasons of the repo's own (dubbo: `compile` alone
        # never builds the in-reactor dubbo-maven-plugin's descriptor); what
        # must hold is: nothing fails to resolve, and the F2P class runs
        rec["ok"] = (not rec["compile"]["resolution_error"]
                     and not rec["test"]["resolution_error"] and bool(m))
    except Exception as e:  # noqa: BLE001
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {str(e)[:400]}"
    finally:
        run_e2e._remove_worktree(wt)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifests", nargs="+")
    ap.add_argument("--ids", default="", help="comma-separated subset")
    ap.add_argument("--verify-only", action="store_true", help="skip the online warm pass")
    ap.add_argument("--out", default="results/warm_agent_m2.jsonl")
    a = ap.parse_args()
    os.chdir(H)
    ids = []
    for m in a.manifests:
        ids += [i for i in json.loads(Path(m).read_text()) if i not in ids]
    if a.ids:
        ids = [i for i in ids if i in a.ids.split(",")]
    tasks = [json.loads((H / "tasks/e2e" / f"{i}.json").read_text()) for i in ids]
    tasks = [t for t in tasks if t.get("lang") == "java"]
    print(f"# {len(tasks)} java tasks", flush=True)
    bad = []
    with open(a.out, "a") as fh:
        for t in tasks:
            rec = run_task(t, warm=not a.verify_only)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if not rec["ok"]:
                bad.append(t["instance_id"])
            print(f"{'OK  ' if rec['ok'] else 'FAIL'} {t['instance_id']:44} jdk={rec.get('jdk')} "
                  f"compile={rec.get('compile', {}).get('rc')}/{rec.get('compile', {}).get('s')}s "
                  f"test={rec.get('test', {}).get('tests_run')}/{rec.get('test', {}).get('s')}s "
                  f"{rec.get('error', '')}", flush=True)
    print(f"# {len(tasks) - len(bad)}/{len(tasks)} build offline; failing: {bad}", flush=True)


if __name__ == "__main__":
    main()
