"""Mode B: does Mode A completeness convert to compile success?

Protocol (per scored run): simulate an agent that completes the signature
change by editing exactly the sites it listed. The Spoon oracle emits the
exact line positions of every occurrence that must change (family declaration
name tokens + family-resolving call/method-ref lines), each attributed to its
containing method — java-oracle/occ/<task>.json. Mode B renames the target
identifier at the occurrences whose containing site is in the run's *found*
set. Sites the agent missed keep the old name. Then `mvn compile` — every
remaining old-name reference the compiler can see is a build break caused by
a missed site.

Validity notes baked into the design:
- Edit gating is at the same granularity the scorer credits (file +
  containing method), so Mode B consumes the exact answer Mode A scored.
  Occurrence positions come from the oracle because textual rename inside a
  whole method span hits same-named calls of OTHER contracts (e.g.
  JsonSerializable.serializeWithType inside a JsonSerializer.serializeWithType
  override) — edit application must be type-resolved even when the answer
  being simulated is not.
- GT is built from src/main/java only, so Mode B compiles main sources only.
- A missed *override declaration* only breaks the build if it carries
  @Override (otherwise it silently stops overriding — a semantic bug the
  compiler cannot see). Mode B measures compile breakage, a LOWER BOUND on
  the damage of a missed site.

Protocol validation: --validate applies the full oracle GT as the found set;
the build must pass, or the task is excluded from Mode B.

Claim framing (post-review): the empirical half of the result is
missed>0 -> build FAILS (compiler-audited, 81 runs). The recall=1.0 -> PASS
half is true by construction: `found` stores GT site strings (score.py
credits by appending the GT site), so a recall-1.0 run replays --validate.
Weak-match credited sites (agent named the symbol but not the right file)
make the simulated edit MORE accurate than the agent's literal answer;
bias direction favors PASS, and the missed>0 runs all failed despite it.
A degenerate all-miss answer or a fully-missed closed subgraph
(declaration + all its callers missed together) would trivially compile;
neither occurred (min recall 0.433) but the metric does not guard it.

Usage:
  python mode_b.py --validate                      # all tasks, GT as answer
  python mode_b.py                                 # all validated tasks x all runs
  python mode_b.py --task tasks/jackson-serialize.json --models sonnet,haiku
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
RUNS_DIR = HARNESS / "runs"
OCC_DIR = HARNESS / "java-oracle" / "occ"

# Scratch worktree of the corpus at the pinned tag (created by the runner).
WORKTREE = Path(
    "/private/tmp/claude-501/-Users-tapabratapal-Projects-provasign-research/"
    "9a056275-72e9-42f8-8afe-b5106886e1bc/scratchpad/modeb-wt"
)

# The renamed method per task. Derived from each task prompt; explicit because
# GT entries name *containing* methods, not the change target.
TARGETS = {
    "jackson-writetypeprefix": "writeTypePrefix",
    "jackson-serializewithtype": "serializeWithType",
    "jackson-serialize": "serialize",
    "jackson-deserialize": "deserialize",
    "jackson-settable-set": "set",
    "jackson-jsonnode-get": "get",
}

# jsonnode-get targets the get(int) OVERLOAD; line-level rename cannot separate
# it from get(String) calls sharing a line (validated: 32 errors on full GT).
# It is also the 8-site greppable control where every arm is at ceiling, so
# Mode B adds no information. Excluded.
EXCLUDED = {"jackson-jsonnode-get"}

ARMS = ("T", "G", "Gstar", "L")  # L = local-tier G* runs (run_local_gstar.py)


def load_occurrences(task_id: str) -> dict[str, list[tuple[str, int, int]]]:
    """site -> [(relpath, startLine, endLine), ...] from the oracle occ file."""
    res = json.loads((OCC_DIR / f"{task_id}.json").read_text())
    by_site: dict[str, list[tuple[str, int, int]]] = {}
    for o in res["occurrences"]:
        relpath, l1, l2, site = o.split("|", 3)
        by_site.setdefault(site, []).append((relpath, int(l1), int(l2)))
    return by_site


def apply_rename(found: list[str], target: str,
                 occ: dict[str, list[tuple[str, int, int]]]) -> tuple[int, int]:
    """Rename target->targetX2 at the oracle occurrences of every found site.

    Returns (sites_edited, occurrences_renamed).
    """
    # call or declaration position: identifier followed by '(' (decl and call
    # share this shape in Java), or a method reference '::target'.
    pat = re.compile(rf"\b{target}\b(?=\s*\()|(?<=::){target}\b")

    by_file: dict[str, list[tuple[int, int]]] = {}
    edited_sites = 0
    for site in found:
        ranges = occ.get(site)
        if not ranges:
            continue
        edited_sites += 1
        for relpath, s, e in ranges:
            by_file.setdefault(relpath, []).append((s, e))

    renamed = 0
    for relpath, ranges in by_file.items():
        fp = WORKTREE / relpath
        if not fp.exists():
            continue
        lines = fp.read_text().splitlines(keepends=True)
        for s, e in ranges:
            for i in range(max(s - 1, 0), min(e, len(lines))):
                new, n = pat.subn(f"{target}X2", lines[i])
                if n:
                    lines[i] = new
                    renamed += n
        fp.write_text("".join(lines))
    return edited_sites, renamed


def compile_worktree() -> tuple[bool, int, list[str]]:
    """Compile main sources. Returns (ok, distinct_error_count, samples)."""
    r = subprocess.run(
        ["mvn", "-q", "-DskipTests", "compile"],
        cwd=WORKTREE, capture_output=True, text=True, timeout=600,
    )
    # Maven prints every compiler error twice (compiler-plugin section and
    # reactor failure summary) — deduplicate, or every count is exactly 2x.
    errs = sorted({
        ln.strip() for ln in (r.stdout + r.stderr).splitlines()
        if "ERROR" in ln and ".java:[" in ln
    })
    return r.returncode == 0, len(errs), errs[:5]


def restore_worktree() -> None:
    subprocess.run(["git", "checkout", "--", "."], cwd=WORKTREE, check=True)


def run_one(found: list[str], target: str,
            occ: dict[str, list[tuple[str, int, int]]]) -> dict:
    restore_worktree()
    sites, nocc = apply_rename(found, target, occ)
    ok, nerr, sample = compile_worktree()
    restore_worktree()
    return {
        "sites_edited": sites, "occurrences": nocc,
        "build_pass": ok, "compile_errors": nerr, "error_sample": sample,
    }


def validate(task_file: Path) -> dict:
    task = json.loads(task_file.read_text())
    target = TARGETS[task["id"]]
    occ = load_occurrences(task["id"])
    res = run_one(task["ground_truth"], target, occ)
    res["task"] = task["id"]
    return res


def runs_for(task_id: str, models: list[str] | None) -> list[Path]:
    d = RUNS_DIR / task_id
    if not d.is_dir():
        return []
    out = []
    for mdir in sorted(d.iterdir()):
        if not mdir.is_dir():
            continue
        if models and mdir.name not in models:
            continue
        for arm in ARMS:
            out.extend(sorted(mdir.glob(f"{arm}.t*.json")))
    return [p for p in out if not p.name.endswith("transcript.txt")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=Path, default=None)
    ap.add_argument("--models", type=str, default=None,
                    help="comma-separated model dir names; default all")
    ap.add_argument("--validate", action="store_true",
                    help="apply full GT per task; build must pass")
    ap.add_argument("--out", type=Path, default=HARNESS / "runs" / "mode_b.json")
    args = ap.parse_args()

    if not WORKTREE.is_dir():
        print(f"worktree missing: {WORKTREE}", file=sys.stderr)
        return 1
    tasks = [args.task] if args.task else sorted(HARNESS.glob("tasks/jackson-*.json"))
    models = args.models.split(",") if args.models else None

    if args.validate:
        ok = True
        for tf in tasks:
            r = validate(tf)
            status = "PASS" if r["build_pass"] else f"FAIL ({r['compile_errors']} errors)"
            print(f"{r['task']:32s} GT n={r['sites_edited']:3d} occ={r['occurrences']:4d}  {status}")
            for e in (r["error_sample"] if not r["build_pass"] else []):
                print(f"    {e[:160]}")
            ok = ok and r["build_pass"]
        return 0 if ok else 1

    results = []
    for tf in tasks:
        task = json.loads(tf.read_text())
        if task["id"] in EXCLUDED:
            print(f"skip {task['id']} (excluded — see EXCLUDED note)")
            continue
        target = TARGETS[task["id"]]
        occ = load_occurrences(task["id"])
        for rf in runs_for(task["id"], models):
            run = json.loads(rf.read_text())
            if run.get("status") != "ok":
                continue
            found = run.get("found") or []
            r = run_one(found, target, occ)
            rec = {
                "task": task["id"], "model": rf.parent.name,
                "arm": rf.name.split(".")[0], "trial": rf.name.split(".")[1],
                "recall": run.get("recall"), "missed": len(run.get("missed") or []),
                **{k: r[k] for k in ("sites_edited", "build_pass", "compile_errors")},
            }
            results.append(rec)
            print(f"{rec['task']:26s} {rec['model']:22s} {rec['arm']:5s} {rec['trial']:3s} "
                  f"recall={rec['recall']:.3f} missed={rec['missed']:3d} "
                  f"-> {'PASS' if rec['build_pass'] else 'FAIL':4s} errors={rec['compile_errors']}")
        args.out.write_text(json.dumps(results, indent=1))
    print(f"\nwrote {args.out} ({len(results)} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
