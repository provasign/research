#!/usr/bin/env python3
"""Generate completeness-scored tasks from real commits.

The bed the e2e suite lacks: MANDATED WIDE changes where success is
"did you find every site", not "did your fix pass a held-out test".
Ground truth is free and exact — the commit's own diff IS the answer
set, so there is no PR mining and no hand-authored oracle to audit.

Two sources, both deliberate:
  dubbo      Apache Dubbo, a real production framework (8,898 commits).
             Forced-wide changes in the tractable band: a removed
             dependency, a moved Spring Boot autoconfigure module, a
             unified interface. Miss one site and the build fails — no
             partial credit, no narrow-workaround escape. A demo app
             (petclinic) was rejected for this slot: its "upgrades" are
             version bumps touching only test annotations.
  grove/prism  Capability removals in an AI-built codebase born
             2026-05-28. Private repos post-dating every model cutoff,
             so memorization cannot substitute for retrieval.

Scoring is compile/build based plus site recall against the diff.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

SRC_SUFFIX = (".java", ".go", ".py", ".ts")


def sh(*args, cwd=None) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout


def changed_files(repo: str, sha: str) -> list[str]:
    out = sh("git", "show", "--name-only", "--format=", sha, cwd=repo)
    return [l.strip() for l in out.splitlines() if l.strip()]


def files_by_status(repo: str, sha: str) -> dict[str, list[str]]:
    """Split the commit by git status letter.

    This split is the whole validity of the bed. Ground truth must be
    only what an agent could RETRIEVE: files that already exist and had
    to be found and changed (M), or found and removed (D). ADDED files
    are unmeasurable as a retrieval target — measured 2026-08-31, the
    "remove spring-context-support" commit vendored 10 library classes
    into the tree, and scoring them as sites-to-find produced a
    meaningless 0.68 recall for an arm that had actually found what
    was findable. Additions stay in the record as context, never in
    the denominator.
    """
    out = sh("git", "show", "--name-status", "--format=", sha, cwd=repo)
    by: dict[str, list[str]] = {"M": [], "A": [], "D": [], "R": []}
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0][:1]
        path = parts[-1].strip()
        if code in by and path:
            by[code].append(path)
    return by


def changed_symbols(repo: str, sha: str) -> list[str]:
    """Identifiers whose import/annotation/type lines moved in the diff.

    These are what the agent must LOCATE — the anchor a graph query
    resolves in one call and a text search has to guess at.
    """
    diff = sh("git", "show", sha, "--", "*.java", "*.go", "*.py", "*.ts", cwd=repo)
    syms: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        body = line[1:].strip()
        # Java: relocated imports and annotations.
        if body.startswith("import "):
            tail = body.rstrip(";").split(".")[-1]
            if tail and tail[0].isupper():
                syms.add(tail)
        elif body.startswith("@") and len(body) > 1 and body[1].isupper():
            syms.add(body[1:].split("(")[0].strip())
        # Go: declarations that appeared or vanished. A capability removal
        # is exactly "this func/type is gone, find everyone who used it",
        # so the DECLARED name is the anchor — without this the Go tasks
        # scored zero symbols and only file recall was measurable.
        else:
            m = re.match(r"func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*[\(\[]", body)
            if m:
                syms.add(m.group(1))
                continue
            m = re.match(r"(?:type|var|const)\s+([A-Za-z_]\w*)\s", body)
            if m:
                syms.add(m.group(1))
    # Drop noise: single letters, common keywords that survive the regexes.
    return sorted(s for s in syms if len(s) > 2 and s not in {"err", "nil", "int"})


def build_task(repo: str, sha: str, project: str, kind: str) -> dict | None:
    subject = sh("git", "log", "-1", "--format=%s", sha, cwd=repo).strip()
    body = sh("git", "log", "-1", "--format=%b", sha, cwd=repo).strip()
    files = changed_files(repo, sha)
    by = files_by_status(repo, sha)
    src = lambda xs: [f for f in xs if f.endswith(SRC_SUFFIX)]
    # Retrieval ground truth: pre-existing files the change forced you to
    # find. Additions are recorded but never scored (see files_by_status).
    gt = sorted(src(by["M"]) + src(by["D"]))
    added = sorted(src(by["A"]))
    if len(gt) < 6:
        return None  # too narrow to test completeness
    if len(added) > len(gt) / 2:
        return None  # dominated by authoring new files, not finding sites
    parent = sh("git", "rev-parse", f"{sha}^", cwd=repo).strip()
    return {
        "instance_id": f"{project}__{sha[:10]}",
        "kind": "mandated_wide",
        "project": project,
        "task_kind": kind,
        "repo_path": repo,
        "base_commit": parent,
        "gold_commit": sha,
        "subject": subject,
        "body": body[:1200],
        # scored ground truth: modified + deleted source files only
        "gt_files": gt,
        "gt_modified": sorted(src(by["M"])),
        "gt_deleted": sorted(src(by["D"])),
        # recorded, NOT scored — an agent cannot retrieve a file that
        # does not exist yet
        "unscored_added": added,
        "gt_all_files": sorted(files),
        "gt_symbols": changed_symbols(repo, sha),
    }


# Apache Dubbo — real production framework (8,898 commits), tractable
# width band (8-25 main source files). Spring-related module/dependency
# refactors plus other forced-wide changes; a missed site breaks the build.
DUBBO_COMMITS = [
    "4fb4d709",  # remove spring-context-support dependency (18 main)
    "6c6056ac",  # move observability autoconfigure to spring-boot-autoconfigure (16)
    "e826b0c2",  # remove old zookeeper (22)
    "8700256b",  # unify graceful shutdown interface (22)
    "9600dc9c",  # remove triple parameter in metadata (15)
    "86dd9889",  # upgrade to Netty HTTP/3 release versions (18)
]
# Cross-cutting capability changes in the AI-built repos.
GROVE_COMMITS = ["d34856e4", "b40b72d9", "74854a22", "803916ea", "2a949fe7", "50e438b0"]
PRISM_COMMITS = ["ac780d92", "98ed1b2b", "b402902c", "3ce40015", "a0cabbe6", "4f22f394"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tasks-wide")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True)

    home = Path.home()
    sources = [
        (str(home / "gvg-corpus/dubbo"), "dubbo", "wide_refactor", DUBBO_COMMITS),
        (str(home / "Projects/provasign/grove"), "grove", "capability_change", GROVE_COMMITS),
        (str(home / "Projects/provasign/prism"), "prism", "capability_change", PRISM_COMMITS),
    ]

    written = 0
    for repo, project, kind, shas in sources:
        for sha in shas:
            full = sh("git", "rev-parse", sha, cwd=repo).strip()
            if not full:
                print(f"  SKIP {project} {sha}: cannot resolve")
                continue
            task = build_task(repo, full, project, kind)
            if task is None:
                print(f"  SKIP {project} {sha}: <4 source files")
                continue
            path = out / f"{task['instance_id']}.json"
            path.write_text(json.dumps(task, indent=1))
            print(f"  {task['instance_id']:28} src={len(task['gt_files']):2} "
                  f"syms={len(task['gt_symbols']):2}  {task['subject'][:44]}")
            written += 1
    print(f"\n{written} tasks written to {out}/")


if __name__ == "__main__":
    main()
