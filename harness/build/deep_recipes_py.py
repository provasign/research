"""Python recipes for build_deep.py (werkzeug, rich, flask).

Python has no compiler, so each recipe edits by resolved call shape
(deep_edit offsets over masked text) and the repo's own test suite is the
check; build_wide's shapes oracle is the site check.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write
import deep_edit as de

E2E = bd.CORPUS / "e2e-2026"
WERKZEUG_BASE = "1b00618e787f40dfb21eba29caf8f8be7c8e1d93"
RICH_BASE = "9d8f9a372cc5916fd4781fec207ced7ddac2f08f"
FLASK_BASE = "36e4a824f340fdee7ed50937ba8e7f6bc7d17f81"


def py_files(wt: Path) -> list[str]:
    return de.code_files(wt, (".py",))


def def_span(raw: str, name: str, cls: str | None = None) -> tuple[int, int]:
    """(start, end) offsets of a top-level (or class-level) def incl. decorators
    and the trailing blank lines."""
    tree = ast.parse(raw)
    body = tree.body
    if cls:
        body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
    node = next(n for n in body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
    lines = raw.splitlines(keepends=True)
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    start = sum(len(l) for l in lines[:first - 1])
    end_line = node.end_lineno
    while end_line < len(lines) and not lines[end_line].strip():
        end_line += 1
    end = sum(len(l) for l in lines[:end_line])
    return start, end


# ------------------------------------------------------------------ werkzeug
# remove werkzeug.test.create_environ; inline EnvironBuilder(...).get_environ()

CE_INSTR = (
    "`werkzeug.test.create_environ(*args, **kwargs)` is a thin wrapper that only builds an "
    "`EnvironBuilder` and returns its environ, and having two spellings for the same thing confuses "
    "users. Remove `create_environ` from `werkzeug.test` (delete the function; do not keep an alias "
    "or a deprecated shim) and rewrite every use in the repository, tests included, as "
    "`EnvironBuilder(<same arguments>).get_environ()`, passing exactly the arguments the call passed "
    "before (positional and keyword). Fix the imports of every module that used it: import "
    "`EnvironBuilder` from `werkzeug.test` instead, without duplicating an existing import. "
    "Test names stay as they are. Behavior must not change."
)


@recipe(instance_id="deep__werkzeug__create_environ_inline_remove",
        repo="pallets/werkzeug", lang="python", repo_dir=E2E / "pallets__werkzeug", base_commit=WERKZEUG_BASE,
        change="remove a helper function and inline its replacement at every call site (+ import fixes)",
        instruction=CE_INSTR,
        decl_files=["src/werkzeug/test.py"],
        shapes=[{"id": "create_environ", "name": "create_environ"}],
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: masked-text call finder (deep_edit) rewrites each create_environ(...) "
                  "call to EnvironBuilder(...).get_environ(); AST removes the def; import lines rewritten; "
                  "werkzeug's test suite in docker confirms",
        notes="All callers are tests; the green layer is werkzeug's full suite.")
def make_create_environ(wt: Path):
    f = "src/werkzeug/test.py"
    raw = read(wt, f)
    a, b = def_span(raw, "create_environ")
    write(wt, f, raw[:a] + raw[b:])
    n = 0
    for f in py_files(wt):
        raw = read(wt, f)
        if "create_environ" not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, "create_environ"):
            if de.prev_token(m, c.name_start) == "def":
                continue
            edits.append((c.name_start, c.name_end, "EnvironBuilder"))
            edits.append((c.close + 1, c.close + 1, ".get_environ()"))
            n += 1
        raw = de.apply_edits(raw, edits)
        has_eb = re.search(r"^from werkzeug\.test import [^\n]*\bEnvironBuilder\b", raw, re.M)
        if has_eb:
            raw = re.sub(r"^from werkzeug\.test import create_environ\n", "", raw, flags=re.M)
        else:
            raw = re.sub(r"^from werkzeug\.test import create_environ$", "from werkzeug.test import EnvironBuilder",
                         raw, flags=re.M)
        write(wt, f, raw)
        left = re.findall(r"\bcreate_environ\b", de.mask(raw, f))
        if left:
            raise RuntimeError(f"{f}: create_environ left after rewrite")
    print(f"  rewrote {n} calls")
    # import order: EnvironBuilder sorts before the other werkzeug.test imports in
    # some files; keep isort-clean ordering is not checked by tests, so leave as is.
    return {}


# ------------------------------------------------------------------ flask
# add_url_rule(rule, endpoint=None, ...) -> add_url_rule(rule, endpoint, ...)

AURU_INSTR = (
    "Flask silently derives a URL rule's endpoint from the view function's name when "
    "`add_url_rule` is called without one, which hides endpoint collisions. Make the `endpoint` "
    "parameter of `add_url_rule` required -- remove its `= None` default (keep the annotation "
    "`str | None`; `route()` still hands over `None` when its decorator was given no endpoint) -- on "
    "every declaration: `Scaffold.add_url_rule` (flask/sansio/scaffold.py), `App.add_url_rule` "
    "(flask/sansio/app.py), `Blueprint.add_url_rule` and `BlueprintSetupState.add_url_rule` "
    "(flask/sansio/blueprints.py). Then update every call of `add_url_rule` in the repository that "
    "does not pass an endpoint (tests and type-check fixtures included): pass, as the second "
    "positional argument or as `endpoint=`, the exact name Flask derived before -- the view "
    "function's `__name__`, which for `SomeView.as_view(\"name\", ...)` is that `name`. Calls that "
    "already pass an endpoint stay as they are. Do not change `route()`'s signature or anything else; "
    "behavior must not change."
)


def _flask_endpoint(raw: str, call: "de.Call") -> str | None:
    for a, b in call.args:
        arg = raw[a:b]
        mm = re.match(r"view_func\s*=\s*(.*)$", arg, re.S)
        if not mm:
            continue
        expr = mm.group(1).strip()
        av = re.match(r"[\w.]+\.as_view\(\s*([\"'])([^\"']+)\1", expr)
        if av:
            return av.group(2)
        if re.fullmatch(r"self\.\w+", expr):
            return expr.split(".")[1]
        if re.fullmatch(r"\w+", expr):
            prior = raw[:call.name_start]
            assigns = list(re.finditer(rf"^\s*{expr}\s*=\s*[\w.]+\.as_view\(\s*([\"'])([^\"']+)\1", prior, re.M))
            defs = list(re.finditer(rf"^\s*(?:async\s+)?def\s+{expr}\s*\(", prior, re.M))
            last_a = assigns[-1].start() if assigns else -1
            last_d = defs[-1].start() if defs else -1
            if last_a > last_d:
                return assigns[-1].group(2)
            if last_d >= 0:
                return expr
        return None
    return None


@recipe(instance_id="deep__flask__add_url_rule_endpoint_required",
        repo="pallets/flask", lang="python", repo_dir=E2E / "pallets__flask", base_commit=FLASK_BASE,
        change="make a defaulted parameter required (4 declarations); callers must pass the derived value",
        instruction=AURU_INSTR,
        decl_files=["src/flask/sansio/scaffold.py", "src/flask/sansio/app.py", "src/flask/sansio/blueprints.py"],
        shapes=[{"id": "auru/2", "name": "add_url_rule", "arity": 2},
                {"id": "auru/3", "name": "add_url_rule", "arity": 3},
                {"id": "endpoint=None", "regex": r"\bendpoint:\s*str\s*\|\s*None\s*=\s*None"}],
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: declarations by pattern; every add_url_rule call without an "
                  "endpoint found with the masked-text call finder (deep_edit), endpoint resolved from "
                  "view_func (def name, as_view(name), or the as_view assignment it names); flask test suite "
                  "in docker confirms",
        notes="Shapes: calls of add_url_rule by argument count (a call missing its endpoint keeps a "
              "lower count than gold), plus the `endpoint: str | None = None` default on declarations. "
              "Calls that already passed an endpoint are identical in base and gold, so they cancel.")
def make_auru(wt: Path):
    n = nd = 0
    for f in py_files(wt):
        raw = read(wt, f)
        if "add_url_rule" not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, "add_url_rule"):
            if de.prev_token(m, c.name_start) == "def":
                seg = raw[c.open:c.close]
                mm = re.search(r"\bendpoint:\s*str\s*\|\s*None\s*=\s*None", seg)
                if mm:
                    a = c.open + mm.start()
                    edits.append((a, c.open + mm.end(), "endpoint: str | None"))
                    nd += 1
                continue
            args = [raw[a:b] for a, b in c.args]
            positional = [x for x in args if not re.match(r"\*{0,2}\w+\s*=|\*\*", x) and not x.startswith("*")]
            has_kw = any(re.match(r"endpoint\s*=", x) for x in args)
            if len(positional) >= 2 or has_kw or any(x.startswith("**") for x in args) and len(positional) >= 2:
                continue
            ep = _flask_endpoint(raw, c)
            if ep is None:
                raise RuntimeError(f"{f}:{raw.count(chr(10), 0, c.name_start) + 1}: cannot resolve endpoint: "
                                   f"{raw[c.name_start:c.close + 1]}")
            edits.append(de.insert_arg(raw, c, 1, f'"{ep}"'))
            n += 1
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
    print(f"  declarations {nd}, calls {n}")
    if nd != 4:
        raise RuntimeError(f"expected 4 declarations, got {nd}")
    return {}


# ------------------------------------------------------------------ rich
# move class Measurement: rich.measure -> new module rich.measurement

MEAS_INSTR = (
    "`rich/measure.py` mixes the `Measurement` value type with the `measure_renderables` helper. Move "
    "the `Measurement` class (unchanged, with all its methods) into a new module `rich/measurement.py`, "
    "and delete it from `rich/measure.py`; `measure_renderables` stays in `rich.measure` (which may "
    "import `Measurement` from the new module for its own use). Then update every import of "
    "`Measurement` in the repository -- the `rich` package, tests, benchmarks, examples and tools -- to "
    "import it from the new module (`from .measurement import Measurement` inside the package, "
    "`from rich.measurement import Measurement` elsewhere); where one import line brings in both "
    "`Measurement` and `measure_renderables`, split it so `measure_renderables` still comes from "
    "`rich.measure`. No module may keep importing `Measurement` from `rich.measure`. Behavior must not "
    "change and no circular import may be introduced."
)

_MEAS_HEAD = '''from typing import TYPE_CHECKING, Callable, NamedTuple, Optional

from . import errors
from .protocol import is_renderable, rich_cast

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions, RenderableType


'''

_MEASURE_HEAD = '''from operator import itemgetter
from typing import TYPE_CHECKING, Sequence

from .measurement import Measurement

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions, RenderableType


'''


@recipe(instance_id="deep__rich__Measurement_move_module",
        repo="Textualize/rich", lang="python", repo_dir=E2E / "Textualize__rich", base_commit=RICH_BASE,
        change="move a class to a new module, old location removed; every import updated (some split)",
        instruction=MEAS_INSTR,
        decl_files=["rich/measure.py", "rich/measurement.py"],
        shapes=[{"id": "import-from-measure",
                 "regex": r"^[ \t]*from[ \t]+(?:rich\.|\.)measure[ \t]+import\b[^\n]*\bMeasurement\b"},
                {"id": "class-def", "regex": r"^class Measurement\b"}],
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: class body moved by source span; import lines rewritten "
                  "(split where they also import measure_renderables); rich's test suite in docker confirms",
        notes="Shapes: an import of Measurement from rich.measure (code, not strings/docstrings) and a "
              "`class Measurement` left in rich/measure.py. rich.measure still binds Measurement (it "
              "imports it for measure_renderables), so a missed import does not fail any test: the "
              "shape oracle alone catches it.")
def make_meas(wt: Path):
    raw = read(wt, "rich/measure.py")
    a = raw.index("class Measurement(NamedTuple):")
    b = raw.index("def measure_renderables(")
    write(wt, "rich/measurement.py", _MEAS_HEAD + raw[a:b].rstrip() + "\n")
    write(wt, "rich/measure.py", _MEASURE_HEAD + raw[b:])
    n = 0
    pat = re.compile(r"^([ \t]*)from[ \t]+(rich\.|\.)measure[ \t]+import[ \t]+([^\n(]+)$", re.M)
    for f in py_files(wt):
        if f == "rich/measure.py":
            continue
        raw = read(wt, f)
        if "measure" not in raw:
            continue

        def rep(m):
            nonlocal n
            ind, pfx, names = m.group(1), m.group(2), [x.strip() for x in m.group(3).split(",")]
            if "Measurement" not in names:
                return m.group(0)
            n += 1
            rest = [x for x in names if x != "Measurement"]
            out = []
            if rest:
                out.append(f"{ind}from {pfx}measure import {', '.join(rest)}")
            out.append(f"{ind}from {pfx}measurement import Measurement")
            return "\n".join(out)
        new = pat.sub(rep, raw)
        if new != raw:
            write(wt, f, new)
    print(f"  rewrote {n} imports")
    return {"partial_drop": [("rich/table.py", "Measurement"), ("tests/test_text.py", "Measurement")]}


# ------------------------------------------------------------------ rich
# loop_first/loop_last/loop_first_last (flag(s) first) -> iter_first/iter_last/
# iter_first_last (value first): a return-shape change every consumer must adapt to

LOOP_INSTR = (
    "The iteration helpers in `rich/_loop.py` put the flag before the value -- `loop_first` and "
    "`loop_last` yield `(is_first, value)` / `(is_last, value)` and `loop_first_last` yields "
    "`(is_first, is_last, value)` -- the opposite of `enumerate`-style helpers, which keeps causing "
    "unpacking mistakes. Change what they yield so the value comes first: `(value, is_first)`, "
    "`(value, is_last)` and `(value, is_first, is_last)`, and rename them to `iter_first`, `iter_last` "
    "and `iter_first_last` (no aliases under the old names) so no caller can silently keep the old "
    "order. Update every use in the repository -- every import, every `for` loop that unpacks them, "
    "and every place that consumes one of these iterators indirectly (for example an iterator pushed "
    "on a stack and unpacked later with `next(...)`) -- and the tests of the helpers themselves. "
    "Code that merely contains these names inside string literals (such as syntax-highlighting "
    "fixtures) is not a use and must not change. Behavior must not change."
)

_LOOP_RENAME = {"loop_first_last": "iter_first_last", "loop_first": "iter_first", "loop_last": "iter_last"}


def _split_top(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


@recipe(instance_id="deep__rich__loop_helpers_value_first",
        repo="Textualize/rich", lang="python", repo_dir=E2E / "Textualize__rich", base_commit=RICH_BASE,
        change="change return shape (yielded tuple order) + rename; every consumer's unpacking must adapt",
        instruction=LOOP_INSTR,
        decl_files=["rich/_loop.py"],
        shapes=[{"id": "loop_first", "name": "loop_first"}, {"id": "loop_last", "name": "loop_last"},
                {"id": "loop_first_last", "name": "loop_first_last"}],
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: masked-text rename of the three helpers; each `for` target list "
                  "that unpacks them reordered by parsing its top-level targets; the indirect consumer in "
                  "rich/tree.py and tests/test_tools.py edited by exact replacement; rich's suite in docker "
                  "confirms",
        notes="Shapes catch a call/import left under an old name. A consumer renamed but not reordered is "
              "caught only by the tests (rich's rendering tests exercise these loops heavily, but not "
              "every one is guaranteed).")
def make_loop(wt: Path):
    # the helpers themselves
    f = "rich/_loop.py"
    raw = read(wt, f)
    raw = raw.replace("def loop_first(values: Iterable[T]) -> Iterable[Tuple[bool, T]]:",
                      "def iter_first(values: Iterable[T]) -> Iterable[Tuple[T, bool]]:")
    raw = raw.replace("def loop_last(values: Iterable[T]) -> Iterable[Tuple[bool, T]]:",
                      "def iter_last(values: Iterable[T]) -> Iterable[Tuple[T, bool]]:")
    raw = raw.replace("def loop_first_last(values: Iterable[T]) -> Iterable[Tuple[bool, bool, T]]:",
                      "def iter_first_last(values: Iterable[T]) -> Iterable[Tuple[T, bool, bool]]:")
    for old, new in [("yield True, value", "yield value, True"), ("yield False, value", "yield value, False"),
                     ("yield False, previous_value", "yield previous_value, False"),
                     ("yield True, previous_value", "yield previous_value, True"),
                     ("yield first, False, previous_value", "yield previous_value, first, False"),
                     ("yield first, True, previous_value", "yield previous_value, first, True")]:
        assert old in raw, old
        raw = raw.replace(old, new)
    write(wt, f, raw)
    n_for = 0
    for f in py_files(wt):
        raw = read(wt, f)
        if not re.search(r"\bloop_(first|last|first_last)\b", raw):
            continue
        m = de.mask(raw, f)
        edits = []
        # for-loop target lists that unpack a helper directly
        for fm in re.finditer(r"\bfor\s+(.+?)\s+in\s+(enumerate\(\s*)?(loop_first_last|loop_first|loop_last)\s*\(", m):
            tgt_a, tgt_b = fm.start(1), fm.end(1)
            tgt = raw[tgt_a:tgt_b]
            fn = fm.group(3)
            if fm.group(2):  # for i, (a, b, c) in enumerate(helper(...))
                parts = _split_top(tgt)
                inner = parts[1]
                assert inner.startswith("(") and inner.endswith(")"), (f, tgt)
                ip = _split_top(inner[1:-1])
                ip = [ip[-1]] + ip[:-1]
                new_tgt = f"{parts[0]}, ({', '.join(ip)})"
            else:
                parts = _split_top(tgt)
                parts = [parts[-1]] + parts[:-1]
                new_tgt = ", ".join(parts)
            edits.append((tgt_a, tgt_b, new_tgt))
            n_for += 1
        for old, new in _LOOP_RENAME.items():
            for mm in re.finditer(rf"(?<![\w$]){old}(?![\w$])", m):
                edits.append((mm.start(), mm.end(), new))
        write(wt, f, de.apply_edits(raw, edits))
    # indirect consumer: Tree.__rich_console__ pushes iter_last(...) iterators and unpacks with next()
    f = "rich/tree.py"
    raw = read(wt, f)
    assert raw.count("last, node = next(stack_node)") == 1
    write(wt, f, raw.replace("last, node = next(stack_node)", "node, last = next(stack_node)"))
    # the helpers' own tests: expected tuples become value-first
    f = "tests/test_tools.py"
    raw = read(wt, f)

    def flip(mm):
        items = _split_top(mm.group(1))
        return "== (" + ", ".join([items[-1]] + items[:-1]) + ")"
    raw = re.sub(r"== \(((?:True|False), [^()\n]*)\)", flip, raw)
    write(wt, f, raw)
    print(f"  reordered {n_for} for-loops")
    return {}
