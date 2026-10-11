"""Offset-preserving source editing helpers for seeded DEEP tasks.

The gold patch of a deep task (build_wide.py site_mode="shapes") is made
mechanically: locate every declaration/call of a method in comment- and
string-masked text (same length as the source, so offsets carry over),
edit the raw text at those offsets, then let the compiler / test suite
confirm the result. These helpers are deliberately language-agnostic and
syntax-light; per-task recipes in build_deep.py decide which matches are
sites, and the language's build is the check.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_OPEN, _CLOSE = "([{", ")]}"


def mask(text: str, path: str) -> str:
    """Same-length copy of text with comments blanked and string-literal
    bodies replaced by '0' (quotes kept), newlines preserved."""
    ext = Path(path).suffix
    py = ext == ".py"
    out = list(text)
    i, n = 0, len(text)

    def blank(a, b, ch=" "):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = ch

    while i < n:
        c = text[i]
        if py and c == "#":
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if not py and text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if not py and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue
        if c in "\"'`" and (py or c != "`" or ext not in (".py",)):
            if py and c == "`":
                i += 1
                continue
            if not py and c == "'" and ext in (".go", ".java", ".kt"):
                j = i + 1
                while j < n and text[j] != "'" and text[j] != "\n":
                    j += 2 if text[j] == "\\" else 1
                blank(i + 1, j, "0")
                i = j + 1
                continue
            if py and text[i:i + 3] in ('"""', "'''"):
                q = text[i:i + 3]
            elif not py and c == '"' and text.startswith('"""', i) and ext in (".java", ".kt"):
                q = '"""'
            else:
                q = c
            j = i + len(q)
            while j < n and not text.startswith(q, j):
                if text[j] == "\\" and not (c == "`" and ext == ".go"):
                    j += 2
                    continue
                if text[j] == "\n" and q in ('"', "'") and not py:
                    break
                if text[j] == "\n" and q in ('"', "'") and py:
                    break
                j += 1
            blank(i + len(q), min(j, n), "0")
            i = j + len(q)
            continue
        i += 1
    return "".join(out)


@dataclass
class Call:
    name_start: int
    name_end: int
    open: int          # index of "("
    close: int         # index of matching ")"
    args: list         # [(start, end)] spans of top-level args, raw offsets, stripped of whitespace

    @property
    def arity(self) -> int:
        return len(self.args)


def find_calls(raw: str, masked: str, name: str) -> list[Call]:
    res = []
    for m in re.finditer(rf"(?<![\w$]){re.escape(name)}\s*(?:<[^<>()]*(?:<[^<>()]*>[^<>()]*)*>)?\s*\(", masked):
        op = m.end() - 1
        depth, i, start, args = 1, op + 1, op + 1, []
        while i < len(masked) and depth:
            ch = masked[i]
            if ch in _OPEN:
                depth += 1
            elif ch in _CLOSE:
                depth -= 1
                if not depth:
                    break
            elif ch == "," and depth == 1:
                args.append((start, i))
                start = i + 1
            i += 1
        args.append((start, i))
        spans = []
        for a, b in args:
            seg = masked[a:b]
            if seg.strip():
                lead = len(seg) - len(seg.lstrip())
                trail = len(seg) - len(seg.rstrip())
                spans.append((a + lead, b - trail))
        res.append(Call(m.start(), m.start() + len(name), op, i, spans))
    return res


def prev_token(masked: str, pos: int) -> str:
    """The identifier/punctuation token immediately before pos (skipping spaces)."""
    j = pos - 1
    while j >= 0 and masked[j].isspace():
        j -= 1
    if j < 0:
        return ""
    if masked[j].isalnum() or masked[j] in "_$":
        k = j
        while k >= 0 and (masked[k].isalnum() or masked[k] in "_$"):
            k -= 1
        return masked[k + 1:j + 1]
    return masked[j]


def next_char(masked: str, pos: int) -> str:
    j = pos
    while j < len(masked) and masked[j].isspace():
        j += 1
    return masked[j] if j < len(masked) else ""


def apply_edits(raw: str, edits: list[tuple[int, int, str]]) -> str:
    """edits: (start, end, replacement); applied right to left; must not overlap."""
    for a, b, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        raw = raw[:a] + rep + raw[b:]
    return raw


def insert_arg(raw: str, call: Call, index: int, expr: str) -> tuple[int, int, str]:
    """An edit inserting expr as argument #index (0-based; == arity appends)."""
    if call.arity == 0:
        return (call.open + 1, call.close, expr)
    if index >= call.arity:
        end = call.args[-1][1]
        return (end, end, ", " + expr)
    start = call.args[index][0]
    return (start, start, expr + ", ")


def enclosing_text(raw: str, pos: int, back: int = 6000) -> str:
    return raw[max(0, pos - back):pos]


def git(*a, cwd=None, check=True) -> str:
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return r.stdout


def code_files(root: Path, exts: tuple[str, ...]) -> list[str]:
    return [f for f in git("-C", str(root), "ls-files").splitlines()
            if f.endswith(exts) and not re.search(r"(^|/)(node_modules|vendor|dist|build|target)/", f)]
