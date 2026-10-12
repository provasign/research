"""High-turn ("deephard") Python recipes for build_deep.py (werkzeug, click, rich).

Same conventions as deep_recipes_py.py: Python has no compiler, so each
recipe edits by resolved call/definition shape (deep_edit offsets over
masked text, plus the ast for statement-level rewrites) and the repo's own
test suite is the check; build_wide's shapes oracle is the site check.

What makes these high-turn (vs. the deep__ set): every task couples two or
more API changes, and the per-site edit depends on how each site consumes
the old API (compare vs. index vs. unpack; which argument is which; whether
an implementation body uses the dropped parameter), so one text
substitution cannot do it.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write
import deep_edit as de
from deep_recipes_py import E2E, WERKZEUG_BASE, RICH_BASE, py_files

CLICK_BASE = "b67832c2167e5b0ff6764a8c04a0a9087e697b5a"


# ------------------------------------------------------------------ shared helpers

def line_starts(raw: str) -> list[int]:
    out = [0]
    for i, ch in enumerate(raw):
        if ch == "\n":
            out.append(i + 1)
    return out


def node_span(raw: str, starts: list[int], node: ast.AST) -> tuple[int, int]:
    """Character offsets of an ast node (ast columns are UTF-8 byte offsets)."""
    def off(line, col):
        ls = starts[line - 1]
        eol = raw.find("\n", ls)
        text = raw[ls:eol if eol >= 0 else len(raw)]
        return ls + len(text.encode()[:col].decode())
    return off(node.lineno, node.col_offset), off(node.end_lineno, node.end_col_offset)


def indent_at(raw: str, pos: int) -> str:
    ls = raw.rfind("\n", 0, pos) + 1
    return re.match(r"[ \t]*", raw[ls:]).group(0)


# ================================================================== werkzeug
# MapAdapter.match(): (endpoint, args) / (rule, args) tuple + return_rule flag
#   -> a RouteMatch object (endpoint, arguments, rule); return_rule removed

WZ_INSTR = (
    "`MapAdapter.match()` (src/werkzeug/routing/map.py) returns a bare tuple whose first item is the "
    "endpoint, or the `Rule` when `return_rule=True` is passed, so callers index or unpack it and the "
    "meaning of item 0 depends on a flag. Replace the tuple with a small result object: add a frozen "
    "dataclass `RouteMatch` to `werkzeug/routing/map.py` with the fields `endpoint`, `arguments` (the "
    "converted values mapping) and `rule` (the matched `Rule`), export it from `werkzeug.routing`, and "
    "make `match()` always return a `RouteMatch`; remove the `return_rule` parameter (and the two "
    "`@t.overload` signatures that existed only for it) -- `.rule` replaces it. `RouteMatch` must not be "
    "a tuple and must not support unpacking, indexing or comparison with tuples (no `NamedTuple`, "
    "`__iter__`, `__getitem__` or custom `__eq__`). Then update every consumer of `match()` in the "
    "repository -- the library itself (e.g. `MapAdapter.dispatch`), the examples, and the tests, "
    "including results that reach a test through a helper that returns `adapter.match()` -- to use the "
    "attributes: a comparison of the result with an `(endpoint, values)` tuple must compare "
    "`endpoint`/`arguments` (or `rule`/`arguments` where `return_rule=True` was passed), `[0]`/`[1]` "
    "become `.endpoint`/`.arguments`, and tuple unpacking becomes attribute access. Calls that only check "
    "that `match()` raises stay as they are, and `Rule.match` / `StateMachineMatcher.match` (internal, "
    "different methods) do not change. Keep every test's assertions equivalent. Behavior must not change."
)

_WZ_CALL = r"\.(?:_)?match\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
WZ_SHAPES = [
    {"id": "match() == (tuple)", "regex": r"\b(?:\w+|self)" + _WZ_CALL + r"\s*==\s*\("},
    {"id": "match()[i]", "regex": r"\b(?:\w+|self)" + _WZ_CALL + r"\s*\["},
    {"id": "a, b = match()", "regex": r"(?m)^[ \t]*[\w]+[ \t]*,[ \t]*[\w]+[ \t]*=[ \t]*[\w.]*" + _WZ_CALL},
    {"id": "return_rule", "name": "return_rule"},
]

_WZ_DATACLASS = '''

@dataclass(frozen=True)
class RouteMatch:
    """The result of :meth:`MapAdapter.match`: the matched rule's
    ``endpoint``, the converted URL ``arguments`` and the ``rule`` itself.
    """

    endpoint: t.Any
    arguments: t.Mapping[str, t.Any]
    rule: Rule
'''


def _wz_is_match_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
        node.func.attr in ("match", "_match") and not (
            isinstance(node.func.value, ast.Name) and node.func.value.id in ("re", "regex"))


def _wz_return_rule(call: ast.Call) -> bool:
    return any(k.arg == "return_rule" and isinstance(k.value, ast.Constant) and k.value.value is True
               for k in call.keywords)


def _wz_drop_return_rule(raw: str, starts, call: ast.Call) -> tuple[int, int, str] | None:
    """Edit removing a `return_rule=...` keyword from the call's source."""
    for k in call.keywords:
        if k.arg == "return_rule":
            a, b = node_span(raw, starts, k)
            # swallow the preceding ", "
            j = a
            while raw[j - 1] in " \t\n":
                j -= 1
            if raw[j - 1] == ",":
                j -= 1
            return (j, b, "")
    return None


def _wz_rewrite_consumers(raw: str, f: str) -> tuple[str, int]:
    tree = ast.parse(raw)
    starts = line_starts(raw)
    edits = []
    n = 0

    def callsrc(call):
        a, b = node_span(raw, starts, call)
        txt = raw[a:b]
        drop = _wz_drop_return_rule(raw, starts, call)
        if drop:
            txt = raw[a:drop[0]] + raw[drop[1]:b]
        return a, b, txt

    for node in ast.walk(tree):
        # assert <match-call> == (x, y)
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare) and \
                len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq) and \
                _wz_is_match_call(node.test.left) and isinstance(node.test.comparators[0], ast.Tuple):
            call = node.test.left
            first = "rule" if _wz_return_rule(call) else "endpoint"
            a, b, txt = callsrc(call)
            sa, _ = node_span(raw, starts, node)
            ind = indent_at(raw, sa)
            edits.append((sa, sa, f"matched = {txt}\n{ind}"))
            edits.append((a, b, f"(matched.{first}, matched.arguments)"))
            n += 1
        # <match-call>[0] / [1]
        elif isinstance(node, ast.Subscript) and _wz_is_match_call(node.value) and \
                isinstance(node.slice, ast.Constant) and node.slice.value in (0, 1):
            call = node.value
            first = "rule" if _wz_return_rule(call) else "endpoint"
            attr = first if node.slice.value == 0 else "arguments"
            a, b, txt = callsrc(call)
            _, sb = node_span(raw, starts, node)
            edits.append((a, sb, f"{txt}.{attr}"))
            n += 1
        # a, b = <match-call>
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                isinstance(node.targets[0], ast.Tuple) and len(node.targets[0].elts) == 2 and \
                _wz_is_match_call(node.value):
            call = node.value
            first = "rule" if _wz_return_rule(call) else "endpoint"
            x, y = node.targets[0].elts
            a, b, txt = callsrc(call)
            sa, sb = node_span(raw, starts, node)
            ind = indent_at(raw, sa)
            xs = raw[slice(*node_span(raw, starts, x))]
            ys = raw[slice(*node_span(raw, starts, y))]
            if xs == "_":
                rep = f"{ys} = {txt}.arguments"
            else:
                rep = f"matched = {txt}\n{ind}{xs}, {ys} = matched.{first}, matched.arguments"
            edits.append((sa, sb, rep))
            n += 1
    return de.apply_edits(raw, edits), n


@recipe(instance_id="deephard__werkzeug__MapAdapter_match_RouteMatch",
        repo="pallets/werkzeug", lang="python", repo_dir=E2E / "pallets__werkzeug", base_commit=WERKZEUG_BASE,
        change="return-shape change (tuple -> result object) + parameter removal (return_rule); every consumer "
               "adapts by how it used the tuple (compare / index / unpack / via helper)",
        instruction=WZ_INSTR,
        decl_files=["src/werkzeug/routing/map.py", "src/werkzeug/routing/__init__.py"],
        shapes=WZ_SHAPES,
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: match() rewritten by exact replacement (overloads dropped, RouteMatch "
                  "dataclass added and exported); every consumer found in the ast (assert-compare with a tuple, "
                  "[0]/[1] subscripts, 2-target unpacking; method name match/_match, regex receivers excluded) "
                  "and rewritten per form; werkzeug's suite in docker confirms",
        notes="Shapes: a match()/_match() call compared with a tuple, subscripted, or unpacked into two names, "
              "and the return_rule name. Calls inside pytest.raises / lambdas are identical in base and gold.")
def make_wz_match(wt: Path):
    f = "src/werkzeug/routing/map.py"
    raw = read(wt, f)
    # drop the two overloads
    a = raw.index("    @t.overload\n    def match(")
    b = raw.index("    def match(", raw.index("    @t.overload\n    def match(", a + 10) + 20)
    raw = raw[:a] + raw[b:]
    old_sig = ("    def match(\n        self,\n        path_info: str | None = None,\n        method: str | None = None,\n"
               "        return_rule: bool = False,\n        query_args: t.Mapping[str, t.Any] | str | None = None,\n"
               "        websocket: bool | None = None,\n    ) -> tuple[t.Any | Rule, t.Mapping[str, t.Any]]:\n")
    new_sig = ("    def match(\n        self,\n        path_info: str | None = None,\n        method: str | None = None,\n"
               "        query_args: t.Mapping[str, t.Any] | str | None = None,\n"
               "        websocket: bool | None = None,\n    ) -> RouteMatch:\n")
    assert raw.count(old_sig) == 1
    raw = raw.replace(old_sig, new_sig)
    for old, new in [
        ("        - you get a tuple in the form ``(endpoint, arguments)`` if there is\n"
         "          a match (unless `return_rule` is True, in which case you get a tuple\n"
         "          in the form ``(rule, arguments)``)\n",
         "        - you get a :class:`RouteMatch` with the matched ``endpoint``, the\n"
         "          converted ``arguments`` and the matched ``rule`` if there is a match\n"),
        ("        :param return_rule: return the rule that matched instead of just the\n"
         "                            endpoint (defaults to `False`).\n", ""),
        ("            if return_rule:\n                return rule, rv\n            else:\n"
         "                return rule.endpoint, rv\n",
         "            return RouteMatch(rule.endpoint, rv, rule)\n"),
        ("                endpoint, args = self.match(path_info, method)\n",
         "                matched = self.match(path_info, method)\n"),
        ("            return view_func(endpoint, args)\n",
         "            return view_func(matched.endpoint, matched.arguments)\n"),
    ]:
        assert raw.count(old) == 1, old
        raw = raw.replace(old, new)
    # doctest output in the docstring (not run, but keep it truthful)
    raw = raw.replace("        >>> urls.match(\"/\", \"GET\")\n        ('index', {})\n",
                      "        >>> urls.match(\"/\", \"GET\").endpoint\n        'index'\n")
    raw = raw.replace("        >>> urls.match(\"/downloads/42\")\n        ('downloads/show', {'id': 42})\n",
                      "        >>> urls.match(\"/downloads/42\").arguments\n        {'id': 42}\n")
    # the dataclass, after the imports (before class Map)
    cm = raw.index("\nclass Map:")
    raw = raw[:cm] + _WZ_DATACLASS + raw[cm:]
    if "from dataclasses import dataclass" not in raw:
        raw = raw.replace("from __future__ import annotations\n",
                          "from __future__ import annotations\n\nfrom dataclasses import dataclass\n", 1)
        raw = raw.replace("from dataclasses import dataclass\n\nimport", "from dataclasses import dataclass\nimport", 1)
    write(wt, f, raw)
    f = "src/werkzeug/routing/__init__.py"
    raw = read(wt, f)
    raw = raw.replace("from .map import MapAdapter as MapAdapter\n",
                      "from .map import MapAdapter as MapAdapter\nfrom .map import RouteMatch as RouteMatch\n")
    write(wt, f, raw)
    total = 0
    for f in py_files(wt):
        if not (f.startswith("tests/") or f.startswith("examples/")):
            continue
        raw = read(wt, f)
        if "match(" not in raw:
            continue
        new, n = _wz_rewrite_consumers(raw, f)
        if n:
            if f == "tests/test_routing.py":
                old = "    ) -> tuple[t.Any, cabc.Mapping[str, t.Any]]:\n        adapter = self._bind("
                assert new.count(old) == 1
                new = new.replace(old, "    ) -> r.RouteMatch:\n        adapter = self._bind(")
            write(wt, f, new)
            total += n
            print(f"  {f}: {n}")
    left = []
    for f in py_files(wt):
        m = de.mask(read(wt, f), f)
        if re.search(r"\breturn_rule\b", m):
            left.append(f)
    if left:
        raise RuntimeError(f"return_rule left in {left}")
    print(f"  consumers rewritten: {total}")
    return {"partial_drop": [("tests/test_routing.py", "nested_edit"), ("tests/test_routing.py", "test_match_args"),
                             ("examples/plnt/webapp.py", None)]}


# ================================================================== click
# ParamType.convert(value, param, ctx) -> convert_value(ctx, param, value)
# ParamType.fail(message, param=None, ctx=None) -> reject(ctx, param, message)
# ParamType.get_metavar / get_missing_message(param, ctx) -> (ctx, param)

CLICK_INSTR = (
    "`click.ParamType` takes its context arguments in the opposite order from the rest of its API: "
    "`shell_complete(ctx, param, incomplete)` is context-first, but `convert(value, param, ctx)`, "
    "`fail(message, param=None, ctx=None)`, `get_metavar(param, ctx)` and "
    "`get_missing_message(param, ctx)` are not, which keeps producing swapped arguments in custom types. "
    "Make all of them context-first (src/click/types.py): rename `convert` to "
    "`convert_value(self, ctx, param, value)` and `fail` to `reject(self, ctx, param, message)` (all "
    "three arguments required, no defaults; it still raises `BadParameter(message, ctx=ctx, "
    "param=param)`), and reorder `get_metavar(self, ctx, param)` and `get_missing_message(self, ctx, "
    "param)` keeping their names. Apply this to the base `ParamType` and every subclass that defines "
    "these methods -- the built-in types in src/click/types.py and every custom `ParamType` in the tests "
    "and examples -- and update every call: `self.convert(...)`/`super().convert(...)`/"
    "`SomeType().convert(...)` become `convert_value` calls and `self.fail(...)` inside a type becomes "
    "`self.reject(...)`, each with the arguments it passed before moved into the new order (pass `None` "
    "where a `fail` call relied on the old `None` defaults); positional calls of `get_metavar`/"
    "`get_missing_message` must be reordered too (this includes a bound `convert` method kept in a variable, "
    "and code a test runs in a subprocess). Do not keep the old names as aliases or wrappers. Do not "
    "change `ParamType.__call__(value, param=None, ctx=None)` (it keeps its signature and calls "
    "`convert_value`), `Context.fail(message)`, `shell_complete`, or `Parameter.type_cast_value(ctx, "
    "value)`. Behavior must not change."
)


def _click_call_args(raw: str, c) -> tuple[list, dict]:
    pos, kw = [], {}
    for a, b in c.args:
        s = raw[a:b]
        mm = re.match(r"(\w+)\s*=(?!=)\s*(.*)$", s, re.S)
        if mm:
            kw[mm.group(1)] = mm.group(2)
        else:
            pos.append(s)
    return pos, kw


def _click_new_args(raw: str, c, old_names: list[str], defaults: dict, new_order: list[str]) -> str:
    """Argument text in the new order, positional; raises on what it cannot map."""
    pos, kw = _click_call_args(raw, c)
    if any(p.startswith("*") for p in pos) or any(k.startswith("*") for k in kw):
        raise RuntimeError(f"star args: {raw[c.name_start:c.close + 1]}")
    vals = dict(zip(old_names, pos))
    vals.update(kw)
    for k, v in defaults.items():
        vals.setdefault(k, v)
    missing = [n for n in new_order if n not in vals]
    if missing:
        raise RuntimeError(f"cannot map {missing}: {raw[c.name_start:c.close + 1]}")
    items = [vals[n] for n in new_order]
    inner = raw[c.open + 1:c.close]
    if "\n" in inner:
        # keep the call's multi-line layout: one argument per line, trailing comma
        ind = indent_at(raw, c.args[0][0]) if c.args else ""
        close_ind = indent_at(raw, c.close)
        return "(\n" + "".join(f"{ind}{x},\n" for x in items) + close_ind + ")"
    return "(" + ", ".join(items) + ")"


def _click_def_params(raw: str, c, new_order: list[str]) -> str:
    """Reorder a def's parameter list (self first, then new_order by name)."""
    spans = [raw[a:b] for a, b in c.args]
    byname = {}
    for s in spans:
        byname[re.match(r"\*{0,2}(\w+)", s).group(1)] = s
    if set(byname) != {"self", *new_order}:
        raise RuntimeError(f"unexpected params {list(byname)}")
    items = [byname["self"]] + [byname[n] for n in new_order]
    # drop defaults on fail/reject parameters
    items = [re.sub(r"\s*=\s*None$", "", x) for x in items]
    inner = raw[c.open + 1:c.close]
    if "\n" in inner:
        ind = indent_at(raw, c.args[0][0])
        close_ind = indent_at(raw, c.close)
        multi_line_each = inner.count("\n") > 2
        if multi_line_each:
            return "(\n" + "".join(f"{ind}{x},\n" for x in items) + close_ind + ")"
        return "(\n" + ind + ", ".join(items) + "\n" + close_ind + ")"
    return "(" + ", ".join(items) + ")"


@recipe(instance_id="deephard__click__ParamType_context_first",
        repo="pallets/click", lang="python", repo_dir=E2E / "pallets__click", base_commit=CLICK_BASE,
        change="two renames + argument reorder (convert -> convert_value, fail -> reject) and two reorders "
               "(get_metavar, get_missing_message) across every ParamType and every call",
        instruction=CLICK_INSTR,
        decl_files=["src/click/types.py"],
        pytest_args=["-m", "not stress"],
        shapes=[{"id": "convert", "name": "convert"}, {"id": "self.fail(", "regex": r"\bself\.fail\s*\("},
                {"id": "def fail(self, message", "regex": r"\bdef fail\s*\(\s*self\s*,\s*message\b"},
                {"id": "get_metavar(param, ctx)", "regex": r"\bdef get_metavar\s*\(\s*self\s*,\s*param\b"},
                {"id": "get_missing_message(param, ctx)", "regex": r"\bdef get_missing_message\s*\(\s*self\s*,\s*param\b"}],
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: masked-text call finder (deep_edit) locates every convert/fail "
                  "definition and call on a ParamType (receiver self/super()/a type instance; Context.fail "
                  "and the nested convert() closures in core.py excluded); arguments re-emitted in the new "
                  "order from their positional/keyword spans; click's suite in docker confirms",
        notes="Shapes: the identifier `convert` (nested `def convert(value)` closures in core.py are "
              "identical in base and gold, so they cancel), ParamType fail calls/defs, and the old-order "
              "get_metavar/get_missing_message definitions. Swapped arguments are caught by click's error-"
              "message tests (BadParameter renders the param name) and by test_types' direct convert calls.")
def make_click(wt: Path):
    nconv = nfail = nmeta = 0
    for f in py_files(wt):
        if not (f.startswith("src/click/") or f.startswith("tests/") or f.startswith("examples/")):
            continue
        raw = read(wt, f)
        if not re.search(r"\b(convert|fail|get_metavar|get_missing_message)\b", raw):
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, "convert"):
            prev = de.prev_token(m, c.name_start)
            if prev == "def":
                if c.arity == 1:  # core.py closures `def convert(value)`
                    continue
                edits.append((c.name_start, c.name_end, "convert_value"))
                edits.append((c.open, c.close + 1, _click_def_params(raw, c, ["ctx", "param", "value"])))
                nconv += 1
            elif prev == ".":
                if c.arity != 3:
                    raise RuntimeError(f"{f}: convert call arity {c.arity}: {raw[c.name_start:c.close + 1]}")
                edits.append((c.name_start, c.name_end, "convert_value"))
                edits.append((c.open, c.close + 1, _click_new_args(raw, c, ["value", "param", "ctx"], {},
                                                                   ["ctx", "param", "value"])))
                nconv += 1
        for c in de.find_calls(raw, m, "fail"):
            prev = de.prev_token(m, c.name_start)
            recv = raw[max(0, c.name_start - 5):c.name_start]
            if prev == "def":
                if f == "src/click/types.py":
                    edits.append((c.name_start, c.name_end, "reject"))
                    edits.append((c.open, c.close + 1, _click_def_params(raw, c, ["ctx", "param", "message"])))
                    nfail += 1
                continue
            if recv != "self." or f == "src/click/core.py":
                continue  # ctx.fail(...) is Context.fail
            edits.append((c.name_start, c.name_end, "reject"))
            edits.append((c.open, c.close + 1, _click_new_args(raw, c, ["message", "param", "ctx"],
                                                               {"param": "None", "ctx": "None"},
                                                               ["ctx", "param", "message"])))
            nfail += 1
        for name in ("get_metavar", "get_missing_message"):
            for c in de.find_calls(raw, m, name):
                prev = de.prev_token(m, c.name_start)
                if prev == "def":
                    edits.append((c.open, c.close + 1, _click_def_params(raw, c, ["ctx", "param"])))
                    nmeta += 1
                elif prev == ".":
                    pos, kw = _click_call_args(raw, c)
                    if pos:
                        edits.append((c.open, c.close + 1, _click_new_args(raw, c, ["param", "ctx"], {},
                                                                           ["ctx", "param"])))
                        nmeta += 1
        if edits:
            raw = de.apply_edits(raw, edits)
            if f == "src/click/types.py":
                raw = raw.replace("If the value cannot be converted, call :meth:`fail` with a",
                                  "If the value cannot be converted, call :meth:`reject` with a")
            write(wt, f, raw)
    # a program run in a subprocess by a test (code inside a string literal: the masked
    # finder skips it, the test catches it)
    f = "tests/test_types.py"
    raw = read(wt, f)
    old = ('        "convert = click.Path(allow_dash=True).convert\\n"\n'
           '        "for value in (\'-\', \'\', b\'-\', b\'\'):\\n"\n'
           '        "    convert(value, None, None)\\n"\n')
    new = ('        "convert = click.Path(allow_dash=True).convert_value\\n"\n'
           '        "for value in (\'-\', \'\', b\'-\', b\'\'):\\n"\n'
           '        "    convert(None, None, value)\\n"\n')
    assert raw.count(old) == 1
    write(wt, f, raw.replace(old, new))
    print(f"  convert sites {nconv}, fail sites {nfail}, metavar/missing sites {nmeta}")
    left = []
    for f in py_files(wt):
        mm = de.mask(read(wt, f), f)
        if re.search(r"\bdef convert\(\s*self|\.convert\(|self\.fail\(", mm) and f != "src/click/core.py":
            left.append(f)
    if left:
        raise RuntimeError(f"old forms left in {left}")
    return {"partial_drop": [("tests/test_termui.py", "rejected {value!r}"), ("src/click/types.py", "class Path")]}


# ================================================================== rich
# The console protocol: ConsoleOptions carries its Console; __rich_console__,
# __rich_measure__, Measurement.get and measure_renderables drop the console
# parameter.

RICH_INSTR = (
    "Every step of rich's console protocol passes the `Console` and the `ConsoleOptions` side by side, "
    "although options are always derived from one console. Make the options carry it: add a required "
    "field `console: \"Console\"` to the `ConsoleOptions` dataclass (rich/console.py; declare it right "
    "after `max_height`, with `field(repr=False, compare=False)` so repr/equality do not change) and set "
    "it in `Console.options`; options derived with `copy()`/`update*()` keep it. Then drop the `console` "
    "parameter everywhere the pair is passed: `__rich_console__(self, console, options)` becomes "
    "`__rich_console__(self, options)`, `__rich_measure__(self, console, options)` becomes "
    "`__rich_measure__(self, options)`, `Measurement.get(console, options, renderable)` becomes "
    "`Measurement.get(options, renderable)`, and `measure_renderables(console, options, renderables)` "
    "becomes `measure_renderables(options, renderables)`. Update every implementation (every renderable "
    "in the `rich` package, the protocol definitions, and renderables defined in tests) -- an "
    "implementation that uses the console now reads it from `options.console` -- and every call, "
    "including calls made through a local alias of `Measurement.get` or through a bound "
    "`__rich_measure__` looked up with `getattr`, and every `ConsoleOptions(...)` constructed directly "
    "(in tests, pass the console the test used, or `Console()`). `Console.render` and `Console.measure` "
    "must still render/measure with the console they were called on, even when handed options that were "
    "made by another console. Do not keep a console parameter, an optional console argument, or a "
    "compatibility shim. Behavior must not change."
)

_BAL = r"(?:[^(),]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*"
RICH_SHAPES = [
    {"id": "def __rich_console__(self, console, options)", "regex": r"\bdef __rich_console__\(\s*self\s*,[^,()]*,"},
    {"id": "def __rich_measure__(self, console, options)", "regex": r"\bdef __rich_measure__\(\s*self\s*,[^,()]*,"},
    {"id": "__rich_console__/__rich_measure__ call with console", "regex": r"\.__rich_(?:console|measure)__\(" + _BAL + ","},
    {"id": "Measurement.get(console, options, r)", "regex": r"\bMeasurement\.get\(" + _BAL + "," + _BAL + ","},
    {"id": "def get(cls, console", "regex": r"\bdef get\(\s*cls\s*,\s*console\b"},
    {"id": "measure_renderables/3", "name": "measure_renderables", "arity": 3},
    {"id": "Measurement.get alias call/3", "regex": r"\b(?:get_measurement|get_render_width|measure)\(" + _BAL + "," + _BAL + ","},
    {"id": "get_console_width(console, options)", "name": "get_console_width", "arity": 2},
    {"id": "ConsoleOptions( without console=",
     "regex": r"\bConsoleOptions\((?!(?:[^()]|\((?:[^()]|\([^()]*\))*\))*\bconsole\s*=)"},
]


def _rich_defs(raw: str, f: str) -> tuple[list, int]:
    """Edits for every __rich_console__/__rich_measure__ def with (self, console, options)."""
    tree = ast.parse(raw)
    starts = line_starts(raw)
    edits = []
    n = 0
    for node in ast.walk(tree):
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in ("__rich_console__", "__rich_measure__")):
            continue
        args = node.args.args
        if len(args) != 3:
            raise RuntimeError(f"{f}:{node.lineno}: {node.name} has {len(args)} params")
        c_name, o_name = args[1].arg, args[2].arg
        ca, _ = node_span(raw, starts, args[1])
        oa, _ = node_span(raw, starts, args[2])
        edits.append((ca, oa, ""))
        used = any(isinstance(x, ast.Name) and x.id == c_name for b in node.body for x in ast.walk(b))
        if used:
            body = node.body
            first = body[1] if (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                                and isinstance(body[0].value.value, str) and len(body) > 1) else body[0]
            fa, _ = node_span(raw, starts, first)
            ls = raw.rfind("\n", 0, fa) + 1
            ind = raw[ls:fa]
            edits.append((ls, ls, f"{ind}{c_name} = {o_name}.console\n"))
        n += 1
    return edits, n


@recipe(instance_id="deephard__rich__ConsoleOptions_carries_console",
        repo="Textualize/rich", lang="python", repo_dir=E2E / "Textualize__rich", base_commit=RICH_BASE,
        change="protocol change: options object gains a required field; four APIs (__rich_console__, "
               "__rich_measure__, Measurement.get, measure_renderables) drop a parameter; implementations "
               "rebind it only where used; aliased/getattr call sites",
        instruction=RICH_INSTR,
        decl_files=["rich/console.py", "rich/measure.py"],
        shapes=RICH_SHAPES,
        test_modules=["tests"],
        gold_tool="build_deep.py recipe: implementations found in the ast (console parameter removed, "
                  "`console = options.console` inserted after the docstring only where the body uses it); "
                  "calls (direct, Measurement.get aliases, getattr-bound __rich_measure__) lose their first "
                  "argument via the masked-text call finder; ConsoleOptions constructions get console=; "
                  "Console.render/measure rebind foreign options; rich's suite in docker confirms",
        notes="Shapes: 3-parameter protocol defs, protocol/Measurement.get/measure_renderables calls with the "
              "old argument count (incl. the local aliases get_measurement/get_render_width/measure and "
              "get_console_width), and ConsoleOptions(...) constructions without console=.")
def make_rich_console(wt: Path):
    # 1. ConsoleOptions field + Console.options/render/measure
    f = "rich/console.py"
    raw = read(wt, f)
    for old, new in [
        ('    max_height: int\n    """Height of container (starts as terminal)"""\n',
         '    max_height: int\n    """Height of container (starts as terminal)"""\n'
         '    console: "Console" = field(repr=False, compare=False)\n    """The console these options belong to."""\n'),
        ("            encoding=self.encoding,\n            is_terminal=self.is_terminal,\n        )\n",
         "            encoding=self.encoding,\n            is_terminal=self.is_terminal,\n            console=self,\n        )\n"),
        ("        measurement = Measurement.get(self, options or self.options, renderable)\n",
         "        _options = options or self.options\n        if _options.console is not self:\n"
         "            _options = replace(_options, console=self)\n"
         "        measurement = Measurement.get(_options, renderable)\n"),
        ("        _options = options or self.options\n        if _options.max_width < 1:\n",
         "        _options = options or self.options\n        if _options.console is not self:\n"
         "            _options = replace(_options, console=self)\n        if _options.max_width < 1:\n"),
        ("from dataclasses import dataclass, field\n", "from dataclasses import dataclass, field, replace\n"),
    ]:
        assert raw.count(old) == 1, old
        raw = raw.replace(old, new)
    write(wt, f, raw)
    # 2. Measurement.get / measure_renderables definitions
    f = "rich/measure.py"
    raw = read(wt, f)
    for old, new in [
        ('        cls, console: "Console", options: "ConsoleOptions", renderable: "RenderableType"\n'
         '    ) -> "Measurement":\n',
         '        cls, options: "ConsoleOptions", renderable: "RenderableType"\n    ) -> "Measurement":\n'),
        ("            console (~rich.console.Console): Console instance.\n"
         "            options (~rich.console.ConsoleOptions): Console options.\n"
         "            renderable (RenderableType): An object that may be rendered with Rich.\n",
         "            options (~rich.console.ConsoleOptions): Console options (carrying the console).\n"
         "            renderable (RenderableType): An object that may be rendered with Rich.\n"),
        ("        _max_width = options.max_width\n        if _max_width < 1:\n",
         "        console = options.console\n        _max_width = options.max_width\n        if _max_width < 1:\n"),
        ('                Callable[["Console", "ConsoleOptions"], "Measurement"]\n',
         '                Callable[["ConsoleOptions"], "Measurement"]\n'),
        ('def measure_renderables(\n    console: "Console",\n    options: "ConsoleOptions",\n',
         'def measure_renderables(\n    options: "ConsoleOptions",\n'),
        ("        console (~rich.console.Console): Console instance.\n"
         "        options (~rich.console.ConsoleOptions): Console options.\n"
         "        renderables (Iterable[RenderableType]): One or more renderable objects.\n",
         "        options (~rich.console.ConsoleOptions): Console options (carrying the console).\n"
         "        renderables (Iterable[RenderableType]): One or more renderable objects.\n"),
    ]:
        assert raw.count(old) == 1, old
        raw = raw.replace(old, new)
    write(wt, f, raw)
    # 3. implementations, calls, constructions
    nd = nc = no = 0
    for f in py_files(wt):
        raw = read(wt, f)
        if not re.search(r"__rich_(console|measure)__|Measurement\.get|measure_renderables|ConsoleOptions\(", raw):
            continue
        edits, k = _rich_defs(raw, f)
        nd += k
        m = de.mask(raw, f)
        aliases = set(re.findall(r"\b(\w+)\s*=\s*Measurement\.get\b(?!\s*\()", m))
        if f == "rich/measure.py":
            aliases.add("get_console_width")
        drop_first = []
        for name in ("__rich_console__", "__rich_measure__"):
            drop_first += [c for c in de.find_calls(raw, m, name) if de.prev_token(m, c.name_start) == "."]
        drop_first += [c for c in de.find_calls(raw, m, "get")
                       if m[max(0, c.name_start - 12):c.name_start] == "Measurement."]
        drop_first += [c for c in de.find_calls(raw, m, "measure_renderables")
                       if de.prev_token(m, c.name_start) != "def"]
        for a in aliases:
            drop_first += [c for c in de.find_calls(raw, m, a) if de.prev_token(m, c.name_start) != "def"]
        for c in drop_first:
            want = 3 if raw[c.name_start:c.name_end] in ("get", "measure_renderables") or \
                raw[c.name_start:c.name_end] in aliases - {"get_console_width"} else 2
            if c.arity == want - 1 and f in ("rich/console.py", "rich/measure.py"):
                continue  # rewritten by the exact replacements above
            if c.arity != want:
                raise RuntimeError(f"{f}:{raw.count(chr(10), 0, c.name_start) + 1}: arity {c.arity} != {want}: "
                                   f"{raw[c.name_start:c.close + 1]}")
            edits.append((c.args[0][0], c.args[1][0], ""))
            nc += 1
        for c in de.find_calls(raw, m, "ConsoleOptions"):
            if de.prev_token(m, c.name_start) in ("class", "def") or c.arity == 0:
                continue
            if f == "rich/console.py":
                continue  # Console.options handled above
            if any(re.match(r"console\s*=", raw[a:b]) for a, b in c.args):
                continue
            edits.append(de.insert_arg(raw, c, c.arity, "console=Console()"))
            no += 1
        if edits:
            raw = de.apply_edits(raw, edits)
            has_console = any(isinstance(x, ast.ImportFrom) and x.module == "rich.console"
                              and any(a.name == "Console" for a in x.names) for x in ast.walk(ast.parse(raw)))
            if no and f.startswith("tests/") and "console=Console()" in raw and not has_console:
                raw = re.sub(r"^(from rich\.console import )", r"\1Console, ", raw, count=1, flags=re.M)
            write(wt, f, raw)
    print(f"  implementations {nd}, calls {nc}, ConsoleOptions constructions {no}")
    return {"partial_drop": [("rich/tree.py", None), ("tests/test_syntax.py", None), ("rich/columns.py", None)]}
