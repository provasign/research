"""Measure the Grove engine ceiling on Mode-A tasks — no LLM in the loop.

For each task JSON, derive the prism change-impact query from the oracle
target (pr: "oracle-spoon:FQN#method[(params)]"), run `prism change-impact`
in the task workdir, and score the returned sites against the task GT with
the SAME scorer the agent arms use (score.py). This is the recall any G* arm
is bounded by: the tool property the paper's tier-invariance claim rests on.

Usage:
  python engine_ceiling.py tasks/jackson-*.json tasks/commons-collections-*.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from schema import Answer, Site, Task
from score import score

PRISM = Path.home() / "bin" / "prism"


def prism_query(task: Task) -> str:
    fqn = task.pr.split("oracle-spoon:", 1)[1]
    type_part, mspec = fqn.split("#", 1)
    simple = type_part.rsplit(".", 1)[-1]
    return f"{simple}.{mspec}"


def engine_sites(query: str, workdir: Path) -> tuple[list[str], dict]:
    result = subprocess.run(
        [str(PRISM), "change-impact", query, "."],
        capture_output=True, text=True, cwd=workdir, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prism change-impact failed: {result.stderr[:400]}")
    data = json.loads(result.stdout)
    sites: list[str] = []
    for group in ("declarations", "family", "callers"):
        for sym in data.get(group, []):
            fp = sym.get("filePath") or sym.get("file", "")
            name = sym.get("name", "")
            if fp and name:
                sites.append(f"{fp}:{name}")
    flags = {k: data.get(k) for k in ("completeness", "externalSupers", "overridesExternal")
             if data.get(k)}
    return sites, flags


def main() -> None:
    task_files = sys.argv[1:]
    if not task_files:
        raise SystemExit(__doc__)
    print(f"{'task':<44}{'GT':>5}{'rec':>7}{'prec':>7}{'sites':>7}  flags")
    for tf in task_files:
        task = Task.load(tf)
        query = prism_query(task)
        raw, flags = engine_sites(query, Path(task.workdir))
        answer = Answer(sites=[Site.parse(s) for s in raw], complete=True, unresolved=[])
        card = score(task, answer, "ENGINE", 0)
        flag_s = ""
        if flags.get("completeness") == "project-local":
            flag_s = f"project-local ({', '.join(flags.get('overridesExternal', []))})"
        print(f"{task.id:<44}{len(task.ground_truth):>5}{card.recall:>7.3f}"
              f"{card.precision:>7.3f}{len(raw):>7}  {flag_s}")


if __name__ == "__main__":
    main()
