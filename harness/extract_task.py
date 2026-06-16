"""Derive a Mode-A task from a merged commit/PR (design §5).

Ground truth = the production (non-test) functions the merge changed. We map
each changed line back to its enclosing function in the *parent* (pre-fix)
checkout, which is also the pin the agent will see. The PR/commit message is
the prompt (the symptom, not the solution); pass --prompt to override with the
linked issue text for a cleaner symptom-only framing.

Usage:
  python extract_task.py --repo /tmp/eval-corpus/gin --commit d75fcd4 \
      --id gin-4645 --type localization --out tasks/gin-4645.json
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from schema import Site, Task

FUNC_RE = re.compile(r"^func\s+(?:\([^)]*\)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[\[(]")
TYPE_RE = re.compile(r"^type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:interface|struct)\b")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def _git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True
    ).stdout


def changed_go_files(repo: str, commit: str) -> list[str]:
    out = _git(repo, "show", "--stat", "--format=", "--name-only", commit)
    return [
        f
        for f in out.splitlines()
        if f.endswith(".go") and not f.endswith("_test.go")
    ]


def changed_old_lines(repo: str, commit: str, path: str) -> set[int]:
    """Old-side line numbers the diff touches (deletions, and addition anchors)."""
    diff = _git(repo, "show", "--format=", commit, "--", path)
    touched: set[int] = set()
    old_ln = 0
    for line in diff.splitlines():
        m = HUNK_RE.match(line)
        if m:
            # Set the old-side cursor; do NOT anchor here -- the hunk header
            # names the function *preceding* the change, which would
            # over-attribute (e.g. a rename's def lands the change on the
            # neighbour above it).
            old_ln = int(m.group(1))
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):  # deletion/modification: attribute, advance
            touched.add(old_ln)
            old_ln += 1
        elif line.startswith("+"):  # insertion: attribute at this old pos, hold
            touched.add(old_ln)
        else:  # context line
            old_ln += 1
    return touched


def func_spans(source: str) -> list[tuple[int, int, str]]:
    """(start_line, end_line, name) for every top-level func/type in `source`.

    Captures both `func`s and `type X interface/struct` decls (an interface
    signature change is a real change-site, not the neighbouring function). A
    decl's span starts at its leading doc-comment block (so a doc-comment change
    attributes to the decl it documents) and ends at its closing `}` in column 0
    (gofmt guarantees this), capped before the next decl. Lines *between* decls
    (package vars, imports) belong to no span and are dropped, rather than
    mis-attributed to the function above.
    """
    lines = source.splitlines()
    heads: list[tuple[int, int, str]] = []  # (doc_start, decl_line, name)
    for i, line in enumerate(lines, start=1):
        m = FUNC_RE.match(line) or TYPE_RE.match(line)
        if not m:
            continue
        doc = i
        j = i - 1  # walk up over the contiguous // comment block
        while j >= 1 and lines[j - 1].lstrip().startswith("//"):
            doc = j
            j -= 1
        heads.append((doc, i, m.group(1)))
    spans: list[tuple[int, int, str]] = []
    for idx, (doc, decl_line, name) in enumerate(heads):
        next_doc = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines) + 1
        end = next_doc - 1  # cap: never spill into the next decl (one-liners)
        for k in range(decl_line, next_doc):  # first column-0 closing brace
            if lines[k - 1].rstrip() == "}":
                end = k
                break
        spans.append((doc, end, name))
    return spans


def enclosing_funcs(repo: str, parent: str, path: str, touched: set[int]) -> set[str]:
    source = _git(repo, "show", f"{parent}:{path}")
    spans = func_spans(source)
    hit: set[str] = set()
    for ln in touched:
        for start, end, name in spans:
            if start <= ln <= end:
                hit.add(name)
                break
    return hit


def extract(repo: str, commit: str) -> tuple[str, list[Site]]:
    parent = _git(repo, "rev-parse", f"{commit}^").strip()
    sites: list[Site] = []
    for path in changed_go_files(repo, commit):
        touched = changed_old_lines(repo, commit, path)
        for name in sorted(enclosing_funcs(repo, parent, path, touched)):
            sites.append(Site(relpath=path, symbol=name))
    return parent, sites


def default_prompt(repo: str, commit: str) -> str:
    body = _git(repo, "log", "-1", "--format=%s%n%n%b", commit)
    # Drop signoff / co-author trailers -- keep the symptom, not the metadata.
    keep = [
        ln
        for ln in body.splitlines()
        if not re.match(r"^(Signed-off-by|Co-authored-by|---)", ln.strip())
    ]
    return "\n".join(keep).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--lang", default="go")
    ap.add_argument("--type", default="localization", dest="task_type")
    ap.add_argument("--pr", default="")
    ap.add_argument("--prompt", default="", help="override prompt (e.g. issue text)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    parent, sites = extract(args.repo, args.commit)
    prompt = args.prompt or default_prompt(args.repo, args.commit)
    task = Task(
        id=args.id,
        repo=args.repo,
        lang=args.lang,
        pin=parent,
        pr=args.pr or args.commit,
        task_type=args.task_type,
        prompt=prompt,
        ground_truth=sites,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    task.save(args.out)
    print(f"[task] {args.id}  pin={parent[:10]}  sites={[str(s) for s in sites]}")
    print(f"       -> {args.out}")


if __name__ == "__main__":
    main()
