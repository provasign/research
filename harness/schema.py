"""Core data types for the graph-vs-grep study harness.

A *task* is a Mode-A context-quality probe derived from a real merged PR
(design §5): the repo is pinned at the PR's parent (pre-fix) commit, the
issue text is the prompt, and the set of production functions the PR changed
is the completeness ground truth ("change-sites"). The agent, under one tool
*arm* (T/G/V), must answer "list every site that must change to fix this"
without writing the patch. We score its answer set against the ground truth
(design §6).

Identifiers are normalized to a `Site` = (relpath, symbol) where `symbol` is
the bare function/method name (receiver stripped). Matching is symbol-name
plus file agreement, with a symbol-only fallback flagged as a weak match --
the same matched-universe discipline grove-eval uses for edges.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Site:
    """A change-site: a function/method that must be touched.

    `relpath` is repo-relative (e.g. "response_writer.go"); `symbol` is the
    bare name with any receiver stripped (e.g. "Hijack", not
    "responseWriter.Hijack").
    """

    relpath: str
    symbol: str

    @staticmethod
    def parse(raw: str) -> "Site":
        """Parse a loose site string from a task file or an agent answer.

        Accepts "file.go:Recv.Method", "file.go:func", "pkg.Func",
        "Recv.Method", or a bare "func". The last path-ish token before ':'
        is the file; everything after is the symbol with receiver dropped.
        """
        raw = raw.strip().strip("`").strip()
        relpath, _, sym = raw.rpartition(":")
        if not sym:  # no colon -> whole thing is the symbol spec
            sym = relpath
            relpath = ""
        sym = sym.rsplit(".", 1)[-1]  # drop receiver / package qualifier
        sym = re.sub(r"\(.*\)$", "", sym).strip()  # drop trailing "()"
        return Site(relpath=relpath.strip(), symbol=sym)

    def __str__(self) -> str:
        return f"{self.relpath}:{self.symbol}" if self.relpath else self.symbol


@dataclass
class Task:
    """A Mode-A task built from a merged PR (design §5)."""

    id: str
    repo: str  # local path to the corpus checkout
    lang: str
    pin: str  # parent (pre-fix) commit -- repo is checked out here
    pr: str  # source PR reference, for provenance
    task_type: str  # localization | impact | dead-code | test-coverage | comprehension
    prompt: str  # the issue text shown to the agent
    ground_truth: list[Site]  # production change-sites the PR touched
    workdir: str = ""  # optional: run in this existing checkout (skip git worktree)

    @staticmethod
    def load(path: str | Path) -> "Task":
        d = json.loads(Path(path).read_text())
        d["ground_truth"] = [Site.parse(s) for s in d["ground_truth"]]
        return Task(**d)

    def save(self, path: str | Path) -> None:
        d = asdict(self)
        d["ground_truth"] = [str(s) for s in self.ground_truth]
        Path(path).write_text(json.dumps(d, indent=2) + "\n")


@dataclass
class Answer:
    """The agent's structured Mode-A response (parsed from its JSON block)."""

    sites: list[Site]
    complete: bool  # agent's own claim that the list is exhaustive
    unresolved: list[str] = field(default_factory=list)  # gap-surfacing signal
    raw: str = ""  # full transcript, for audit

    @staticmethod
    def parse(text: str) -> "Answer":
        """Extract the last JSON object with a `sites` key from agent output."""
        obj = _last_json_object(text)
        if obj is None:
            return Answer(sites=[], complete=False, unresolved=[], raw=text)
        sites = [Site.parse(s) for s in obj.get("sites", []) if str(s).strip()]
        return Answer(
            sites=sites,
            complete=bool(obj.get("complete", False)),
            unresolved=[str(u) for u in obj.get("unresolved", [])],
            raw=text,
        )


@dataclass
class Scorecard:
    """Per-run scoring of an Answer against a Task's ground truth (design §6)."""

    task_id: str
    arm: str
    trial: int
    recall: float
    precision: float
    f1: float
    found: list[str]  # ground-truth sites the agent matched
    missed: list[str]  # ground-truth sites the agent did not find
    extra: list[str]  # agent sites with no ground-truth match (false positives)
    weak_matches: list[str]  # symbol-only (no file agreement) matches
    claimed_complete: bool
    overconfident: bool  # claimed complete AND recall < 1.0 -- a confident error
    surfaced_gap: bool  # agent reported any unresolved/ambiguous edge

    def to_dict(self) -> dict:
        return asdict(self)


# --- internals ---------------------------------------------------------------


def _last_json_object(text: str) -> dict | None:
    """Return the last JSON object containing a "sites" key.

    Uses raw_decode from every "{" rather than a naive brace counter: a "{" in a
    prose code snippet (e.g. `func() {`) simply fails to decode and is skipped,
    while a genuine JSON object decodes correctly regardless of surrounding text
    or braces. (The brace-counter version mis-scored answers whose prose
    contained unbalanced code braces.)
    """
    candidates: list[dict] = []
    dec = json.JSONDecoder()
    i = 0
    while True:
        idx = text.find("{", i)
        if idx < 0:
            break
        try:
            obj, _ = dec.raw_decode(text, idx)
            if isinstance(obj, dict) and "sites" in obj:
                candidates.append(obj)
        except json.JSONDecodeError:
            pass
        i = idx + 1
    return candidates[-1] if candidates else None
