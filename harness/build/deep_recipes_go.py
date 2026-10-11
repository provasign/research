"""Go recipes for build_deep.py (gin, echo, urfave/cli ...).

Gold = declarations by pattern, then the Go compiler's own errors
(`go build` + `go test -run ^$` compile of every package, -gcflags=-e so
every error prints, once per build-tag set) drive the call-site edits,
iterated to a clean build; gofmt on changed files."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write
import deep_edit as de

GO = "/opt/homebrew/opt/go@1.25/bin/go"
GOFMT = "/opt/homebrew/opt/go@1.25/bin/gofmt"

GIN = bd.CORPUS / "gin"
GIN_BASE = "d75fcd4c9ab260e5225de590f1f0f8c0e0e12d11"
ECHO = bd.CORPUS / "echo"
ECHO_BASE = "3d084be9022432c5a5257924c7d74bfc3444b456"
CLI = bd.CORPUS / "cli"
CLI_BASE = "58ec406eff149315193d8632c08317f70f6deee1"

GO_ERR = re.compile(r"^(?:\.\/)?([\w./-]+\.go):(\d+):(\d+): (.*)$", re.M)


def go_env():
    env = dict(os.environ, GOTOOLCHAIN="local", GOFLAGS="-mod=mod")
    env["PATH"] = str(Path(GO).parent) + ":" + env["PATH"]
    return env


def go_compile(wt: Path, tags: list[str]) -> tuple[bool, list, str]:
    """Compile every package and every test binary; (ok, [(file, line, col, msg)], output)."""
    errs, outs, ok = [], [], True
    for tag in tags:
        tg = ["-tags", tag] if tag else []
        for cmd in ([GO, "build", "-gcflags=-e", *tg, "./..."],
                    [GO, "test", "-count=1", "-run", "^$", "-gcflags=-e", "-vet=off", *tg, "./..."]):
            r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, env=go_env(), timeout=1800)
            out = r.stdout + r.stderr
            outs.append(out)
            if r.returncode != 0:
                ok = False
            for m in GO_ERR.finditer(out):
                f = m.group(1)
                if not (wt / f).exists():
                    continue  # paths are cwd-relative for ./... builds
                errs.append((f, int(m.group(2)), int(m.group(3)), m.group(4)))
    seen, uniq = set(), []
    for e in errs:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return ok, uniq, "\n".join(outs)[-4000:]


def gofmt(wt: Path) -> None:
    changed = [l[3:] for l in de.git("-C", str(wt), "status", "--porcelain").splitlines()
               if l[3:].endswith(".go")]
    if changed:
        subprocess.run([GOFMT, "-w", *changed], cwd=wt, check=True)


def go_files(wt: Path) -> list[str]:
    return de.code_files(wt, (".go",))


def call_at(wt: Path, f: str, name: str, line: int, col: int, arity: int | None = None):
    """The innermost call of `name` whose span contains (line, col), or whose
    name starts on that line."""
    raw = read(wt, f)
    off = bd.line_offset(raw, line, col)
    m = de.mask(raw, f)
    best = None
    after = None
    for c in de.find_calls(raw, m, name):
        if arity is not None and c.arity != arity:
            continue
        if c.name_start <= off <= c.close or raw.count("\n", 0, c.name_start) + 1 == line:
            if best is None or c.name_start > best.name_start:
                best = c
        elif c.name_start > off and (after is None or c.name_start < after.name_start):
            after = c  # go reports a call at the start of its receiver expression
    best = best or after
    return raw, m, best


def compile_until_clean(wt: Path, tags: list[str], fix_error, rounds: int = 10) -> None:
    last = None
    for i in range(rounds):
        ok, errs, tail = go_compile(wt, tags)
        print(f"  go compile round {i}: ok={ok} errors={len(errs)}", flush=True)
        if ok:
            return
        if not errs:
            raise RuntimeError("build failed without parsable errors:\n" + tail)
        if sorted(errs) == last:
            raise RuntimeError("no progress:\n" + "\n".join(map(str, errs[:30])))
        last = sorted(errs)
        handled = 0
        done_files_lines = set()
        for e in sorted(errs, key=lambda e: (e[0], -e[1], -e[2])):
            if (e[0], e[1], e[2]) in done_files_lines:
                continue
            if fix_error(*e):
                handled += 1
                done_files_lines.add((e[0], e[1], e[2]))
        if not handled:
            raise RuntimeError("unhandled errors:\n" + "\n".join(map(str, errs[:40])))
    raise RuntimeError("did not converge")


def enclosing_go_func(masked: str, pos: int) -> int:
    """Offset of the `func` keyword of the innermost top-level func declaration before pos."""
    starts = [m.start() for m in re.finditer(r"(?m)^func\b", masked[:pos])]
    return starts[-1] if starts else 0


def add_param_to_decls(wt: Path, name: str, old_arity: int, is_decl, param: str,
                       files_filter=lambda f: True) -> int:
    """Append `param` to every declaration (is_decl(raw, masked, call, file) True)."""
    n = 0
    for f in go_files(wt):
        if not files_filter(f):
            continue
        raw = read(wt, f)
        if name not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, name):
            if c.arity == old_arity and is_decl(raw, m, c, f):
                first = raw[c.args[0][0]:c.args[0][1]] if c.args else "x T"
                unnamed = " " not in first.strip()  # `Bind(*http.Request, any)`
                edits.append(de.insert_arg(raw, c, old_arity, param.split()[-1] if unnamed else param))
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
            n += len(edits)
    return n


def is_method_decl(raw: str, masked: str, c, f: str) -> bool:
    """`func (recv) Name(` or an interface method line `\tName(`."""
    line_start = masked.rfind("\n", 0, c.name_start) + 1
    head = masked[line_start:c.name_start]
    return bool(re.fullmatch(r"func\s*\([^()]*\)\s*", head) or re.fullmatch(r"\s+", head))


# ------------------------------------------------------------------ G1 gin Binding.Bind

GIN_BIND_INSTR = (
    "Request bindings always validate with the package-level `binding.Validator`, so a caller cannot "
    "choose another validator per call. Make the validator explicit: add a third, required parameter "
    "`v StructValidator` to the `Bind` method of the `binding.Binding` interface (binding/binding.go and "
    "its `nomsgpack` twin binding/binding_nomsgpack.go), so it becomes "
    "`Bind(req *http.Request, obj any, v StructValidator) error`. Change every implementation "
    "(jsonBinding, xmlBinding, formBinding, formPostBinding, formMultipartBinding, queryBinding, "
    "headerBinding, plainBinding, protobufBinding, msgpackBinding, yamlBinding, tomlBinding, "
    "bsonBinding, and any implementation in tests) and every call of `Binding.Bind`, in source and in "
    "tests (including tests built only with the `nomsgpack` tag). Every existing call must pass the "
    "package-level validator, so behavior does not change: `binding.Validator` outside package "
    "binding (e.g. `Context.ShouldBindWith`), `Validator` inside it. Implementations do not have to "
    "use the new parameter yet. Do not add a two-argument variant. Do not change `Context.Bind(obj)`, "
    "the `gin.Bind` helper, `BindingBody.BindBody`, `BindingUri.BindUri` or any other `Bind*` method."
)


@recipe(instance_id="deep__gin__Binding_Bind_add_validator",
        repo="gin-gonic/gin", lang="go", repo_dir=GIN, base_commit=GIN_BASE,
        change="add required parameter (interface method: 13 implementations + callers, two build-tag variants)",
        instruction=GIN_BIND_INSTR,
        decl_files=["binding/binding.go", "binding/binding_nomsgpack.go"],
        shapes=[{"id": "Bind/2", "name": "Bind", "arity": 2}],
        gold_tool="build_deep.py go recipe: declarations by pattern (func (recv) Bind(req *http.Request, obj any) "
                  "and the interface lines), call sites from go build/go test compile errors (-gcflags=-e, default "
                  "tags and -tags nomsgpack), iterated to a clean build; gofmt (go1.25.14 GOTOOLCHAIN=local)",
        notes="Look-alikes: Context.Bind(obj), gin.Bind(val) (arity 1), BindBody/BindUri (other names).")
def make_gin_bind(wt: Path):
    def is_decl(raw, m, c, f):
        if not f.startswith("binding/") or f.endswith("_test.go"):
            return is_method_decl(raw, m, c, f) and "*http.Request" in raw[c.open:c.close]
        return is_method_decl(raw, m, c, f)
    n = add_param_to_decls(wt, "Bind", 2, is_decl, "v StructValidator")
    print(f"  declarations: {n}")

    def fix(f, line, col, msg):
        if not re.search(r"(not enough arguments in call to .*\bBind\b)", msg):
            return False
        raw, m, c = call_at(wt, f, "Bind", line, col, arity=2)
        if c is None:
            return False
        pkg = re.search(r"(?m)^package\s+(\w+)", raw).group(1)
        val = "Validator" if pkg == "binding" else "binding.Validator"
        write(wt, f, de.apply_edits(raw, [de.insert_arg(raw, c, 2, val)]))
        return True

    compile_until_clean(wt, ["", "nomsgpack"], fix)
    gofmt(wt)


# ------------------------------------------------------------------ G2 echo MiddlewareConfigurator.ToMiddleware

ECHO_TOMW_INSTR = (
    "Middleware configurations are turned into middleware without knowing which Echo instance they will "
    "serve. Add a required parameter `e *Echo` to the `ToMiddleware` method of the "
    "`echo.MiddlewareConfigurator` interface (echo.go), so it becomes "
    "`ToMiddleware(e *Echo) (MiddlewareFunc, error)`, and change every configuration type that "
    "implements it (every `XxxConfig.ToMiddleware` in the middleware package, as "
    "`ToMiddleware(e *echo.Echo) (echo.MiddlewareFunc, error)`) and every call of `ToMiddleware`, in "
    "source and in tests. At each call pass the `*echo.Echo` the middleware is being built for when the "
    "calling function has one in scope (in tests this is usually the `e := echo.New()` instance); where "
    "there is none (e.g. `toMiddlewareOrPanic`, used by the `XxxWithConfig` constructors, and tests "
    "that build middleware without an Echo instance) pass `nil`. Implementations do not have to use the "
    "parameter yet and must accept `nil`. Do not keep a parameterless variant. Behavior must not change."
)


@recipe(instance_id="deep__echo__MiddlewareConfigurator_ToMiddleware_add_echo",
        repo="labstack/echo", lang="go", repo_dir=ECHO, base_commit=ECHO_BASE,
        change="add required parameter (interface method: 22 middleware config implementations + callers)",
        instruction=ECHO_TOMW_INSTR,
        decl_files=["echo.go"],
        shapes=[{"id": "ToMiddleware/0", "name": "ToMiddleware", "arity": 0}],
        gold_tool="build_deep.py go recipe: declarations by pattern (func (config XxxConfig) ToMiddleware() and the "
                  "interface line), call sites from go build/go test compile errors (-gcflags=-e), "
                  "iterated to a clean build; gofmt (go1.25.14 GOTOOLCHAIN=local)",
        notes="Call-site value: the enclosing function's `e := echo.New()` when present, else nil.")
def make_echo_tomw(wt: Path):
    def param_for(f):
        return "e *Echo" if not f.startswith("middleware/") else "e *echo.Echo"
    n = 0
    for f in go_files(wt):
        raw = read(wt, f)
        if "ToMiddleware" not in raw:
            continue
        m = de.mask(raw, f)
        edits = [de.insert_arg(raw, c, 0, param_for(f)) for c in de.find_calls(raw, m, "ToMiddleware")
                 if c.arity == 0 and is_method_decl(raw, m, c, f)]
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
            n += len(edits)
    print(f"  declarations: {n}")

    def fix(f, line, col, msg):
        if not re.search(r"not enough arguments in call to .*\bToMiddleware\b", msg):
            return False
        raw, m, c = call_at(wt, f, "ToMiddleware", line, col, arity=0)
        if c is None:
            return False
        body = m[enclosing_go_func(m, c.name_start):c.name_start]
        val = "e" if re.search(r"(?m)^\s*e\s*:?=\s*echo\.New\(\)", body) or \
            re.search(r"(?m)^\s*e\s*:?=\s*New\(\)", body) else "nil"
        write(wt, f, de.apply_edits(raw, [de.insert_arg(raw, c, 0, val)]))
        return True

    compile_until_clean(wt, [""], fix)
    gofmt(wt)


# ------------------------------------------------------------------ G3 urfave/cli ValueCreator.Create -> (Value, error)

CLI_CREATE_INSTR = (
    "`ValueCreator.Create` (flag_impl.go) cannot report a bad default or config: it returns only a "
    "`Value`. Change its return type to `(Value, error)`, so the interface method becomes "
    "`Create(T, *T, C) (Value, error)`. Change every implementation (boolValue, durationValue, "
    "floatValue, genericValue, intValue, uintValue, stringValue, textValue, timestampValue, MapBase, "
    "SliceBase and any other) to the new signature; the existing implementations never fail and return "
    "a nil error. Update every caller, in source and in tests, to handle the error: where the calling "
    "function returns an error, return it (`ArgumentBase.Parse`, `ArgumentsBase.Parse`, "
    "`FlagBase.PreParse`, and `MapBase.Create` / `SliceBase.Create`, which call the element creator); "
    "in tests, fail the test on a non-nil error (`require.NoError`/`t.Fatal`), or panic inside helper "
    "closures that have no `*testing.T`. Do not keep a single-result variant or wrapper. Do not touch "
    "unrelated `Create` functions such as `os.Create`. Behavior must not change."
)

CLI_SINGLE_USE = r"(?m)^\s*[\w.]+\s*:?=\s*[\w.]+\.Create\(|\b\w+:\s*[\w.]+\.Create\("


@recipe(instance_id="deep__cli__ValueCreator_Create_return_error",
        repo="urfave/cli", lang="go", repo_dir=CLI, base_commit=CLI_BASE,
        change="change return type T -> (T, error) (generic interface method: 12 implementations + callers "
               "that must restructure expression uses into error handling)",
        instruction=CLI_CREATE_INSTR,
        decl_files=["flag_impl.go"],
        shapes=[{"id": "Create/returns-Value", "regex": r"\bCreate\s*\([^()]*\)\s*Value\b"},
                {"id": "Create/single-value-use", "regex": CLI_SINGLE_USE}],
        gold_tool="build_deep.py go recipe: declarations by pattern (return type Value -> (Value, error), "
                  "`return x` -> `return x, nil` in their bodies), callers rewritten by explicit per-site edits, "
                  "go build + go test compile clean (go1.25.14 GOTOOLCHAIN=local); gofmt",
        notes="Call sites are guarded by the compiler (a two-result call in single-value context does not "
              "compile) and by the single-value-use regex shape.")
def make_cli_create(wt: Path):
    # 1. callers inside the element-wrapping creators, before their own returns change
    for f, typ in (("flag_map_impl.go", "MapBase"), ("flag_slice_base.go", "SliceBase")):
        raw = read(wt, f)
        pat = rf"\treturn &{typ}\[T, C, VC\]\{{(?=[^}}]*vc\.Create)"
        raw, k = re.subn(pat, lambda mm: "\tvalue, err := vc.Create(t, np, c)\n\tif err != nil {\n\t\treturn nil, err\n\t}\n"
                         + mm.group(0), raw)
        assert k == 1, (f, k)
        raw = re.sub(r"(value:\s*)vc\.Create\(t, np, c\),", r"\1value,", raw)
        write(wt, f, raw)
    # 2. interface + implementations
    n = 0
    for f in go_files(wt):
        raw = read(wt, f)
        if "Create" not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for dm in re.finditer(r"(?m)^func\s*\([^()]*\)\s*Create\s*\([^()]*\)\s*(Value)\s*\{", m):
            edits.append((dm.start(1), dm.end(1), "(Value, error)"))
            # body: from the "{" to its match
            i, depth = dm.end() - 1, 0
            while True:
                depth += m[i] == "{"
                depth -= m[i] == "}"
                if depth == 0:
                    break
                i += 1
            body_s, body_e = dm.end(), i
            assert "func(" not in m[body_s:body_e], f
            for rm in re.finditer(r"\breturn\b", m[body_s:body_e]):
                j, d = body_s + rm.end(), 0
                while j < body_e:
                    ch = m[j]
                    if ch in "([{":
                        d += 1
                    elif ch in ")]}":
                        d -= 1
                    elif ch == "\n" and d == 0 and m[body_s + rm.end():j].strip() and m[j - 1] not in ",(":
                        break
                    j += 1
                expr = raw[body_s + rm.end():j].rstrip()
                if expr.strip().startswith("nil, err"):
                    continue
                end = body_s + rm.end() + len(expr)
                edits.append((end, end, ", nil"))
            n += 1
        im = re.search(r"(?m)^\s*Create\(T, \*T, C\) (Value)\s*$", m)
        if im:
            edits.append((im.start(1), im.end(1), "(Value, error)"))
            n += 1
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
    print(f"  declarations: {n}")
    # 3. callers
    subs = {
        "args.go": [("\tvalue := vc.Create(a.Value, &t, a.Config)\n",
                     "\tvalue, err := vc.Create(a.Value, &t, a.Config)\n\tif err != nil {\n\t\treturn s, err\n\t}\n", 2)],
        "flag_impl.go": [("\tif f.Destination == nil {\n\t\tf.value = f.creator.Create(newVal, new(T), f.Config)\n"
                          "\t} else {\n\t\tf.value = f.creator.Create(newVal, f.Destination, f.Config)\n\t}\n",
                          "\tdest := f.Destination\n\tif dest == nil {\n\t\tdest = new(T)\n\t}\n"
                          "\tvalue, err := f.creator.Create(newVal, dest, f.Config)\n\tif err != nil {\n\t\treturn err\n\t}\n"
                          "\tf.value = value\n", 1)],
        "flag_int_test.go": [("\t\t\ttt.flag.Value = uValue.Create(u, &u, tt.config)\n",
                              "\t\t\tvalue, createErr := uValue.Create(u, &u, tt.config)\n\t\t\trequire.NoError(t, createErr)\n"
                              "\t\t\ttt.flag.Value = value\n", 1)],
        "flag_uint_test.go": [("\t\t\ttt.flag.Value = uValue.Create(u, &u, tt.config)\n",
                               "\t\t\tvalue, createErr := uValue.Create(u, &u, tt.config)\n\t\t\trequire.NoError(t, createErr)\n"
                               "\t\t\ttt.flag.Value = value\n", 1)],
        "flag_test.go": [("\tvar ipv int64\n\n\tf := &flag.Flag{\n\t\tName:     \"bar\",\n\t\tUsage:    \"bar usage\",\n"
                          "\t\tValue:    iv.Create(11, &ipv, IntegerConfig{}),\n",
                          "\tvar ipv int64\n\n\tvalue, err := iv.Create(11, &ipv, IntegerConfig{})\n\trequire.NoError(t, err)\n\n"
                          "\tf := &flag.Flag{\n\t\tName:     \"bar\",\n\t\tUsage:    \"bar usage\",\n"
                          "\t\tValue:    value,\n", 1)],
    }
    for f, reps in subs.items():
        raw = read(wt, f)
        for old, new, cnt in reps:
            assert raw.count(old) == cnt, (f, raw.count(old))
            raw = raw.replace(old, new)
        write(wt, f, raw)
    # schema-type test closures: func() *extFlag, no *testing.T of their own
    f = "flag_schema_type_test.go"
    raw = read(wt, f)
    raw, k = re.subn(r"(?m)^(\t+)return &extFlag\{f: &flag\.Flag\{Value: (\w+\.Create\(.*\))\}\}\n",
                     lambda mm: f"{mm.group(1)}value, err := {mm.group(2)}\n{mm.group(1)}if err != nil {{\n"
                                f"{mm.group(1)}\tpanic(err)\n{mm.group(1)}}}\n"
                                f"{mm.group(1)}return &extFlag{{f: &flag.Flag{{Value: value}}}}\n", raw)
    assert k == 5, k
    write(wt, f, raw)

    def fix(f, line, col, msg):
        return False

    compile_until_clean(wt, [""], fix, rounds=1)
    gofmt(wt)
    return {"partial_drop": [("flag_schema_type_test.go", "dv.Create"), ("flag_bool.go", None)]}


# ------------------------------------------------------------------ G4 echo NewHTTPError(code, message) -> (code, message, internal)

ECHO_NHE_INSTR = (
    "`echo.NewHTTPError(code int, message string) *HTTPError` (httperror.go) cannot record the "
    "underlying cause; callers chain `.Wrap(err)` afterwards, which allocates a second error. Add a "
    "third, required parameter `internal error` so the function becomes "
    "`NewHTTPError(code int, message string, internal error) *HTTPError`, storing it as the wrapped "
    "error (what `Unwrap` returns). Update every call, in source and in tests: where the result of "
    "`NewHTTPError(...)` is immediately wrapped with `.Wrap(x)`, pass `x` as the new argument and drop "
    "the `.Wrap` call; everywhere else pass `nil`. Do not change `HTTPError.Wrap` itself, the "
    "`HTTPError{...}` literals, or the predefined `Err*` values' use of `.Wrap`. Do not keep a "
    "two-argument variant. Behavior must not change."
)


@recipe(instance_id="deep__echo__NewHTTPError_add_internal",
        repo="labstack/echo", lang="go", repo_dir=ECHO, base_commit=ECHO_BASE,
        change="add required parameter (package function; call sites that chain .Wrap(x) must fold x into the new argument)",
        instruction=ECHO_NHE_INSTR,
        decl_files=["httperror.go"],
        shapes=[{"id": "NewHTTPError/2", "name": "NewHTTPError", "arity": 2},
                {"id": "NewHTTPError(...).Wrap", "regex": r"\bNewHTTPError\s*\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)\s*\.Wrap\("}],
        gold_tool="build_deep.py go recipe: every NewHTTPError call (unique name) gets `, nil`, or the argument of an "
                  "immediately chained .Wrap(x) (which is removed); go build + go test compile clean "
                  "(go1.25.14 GOTOOLCHAIN=local); gofmt",
        notes="")
def make_echo_nhe(wt: Path):
    name = "NewHTTPError"
    n = 0
    for f in go_files(wt):
        raw = read(wt, f)
        if name not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, name):
            if c.arity != 2:
                continue
            if m[max(0, c.name_start - 5):c.name_start] == "func ":
                edits.append(de.insert_arg(raw, c, 2, "internal error"))
                continue
            after = re.match(r"\s*\.Wrap\s*\(", m[c.close + 1:])
            if after:
                wc = [w for w in de.find_calls(raw, m, "Wrap") if w.name_start > c.close][0]
                x = raw[wc.args[0][0]:wc.args[0][1]]
                edits.append((c.args[-1][1], wc.close + 1, f", {x})"))
            else:
                edits.append(de.insert_arg(raw, c, 2, "nil"))
            n += 1
        if edits:
            raw = de.apply_edits(raw, edits)
            if f == "httperror.go":
                old = "\t\tCode:    code,\n\t\tMessage: message,\n\t}\n"
                assert raw.count(old) == 1
                raw = raw.replace(old, "\t\tCode:    code,\n\t\tMessage: message,\n\t\terr:     internal,\n\t}\n")
            write(wt, f, raw)
    print(f"  call sites: {n}")

    def fix(f, line, col, msg):
        return False

    compile_until_clean(wt, [""], fix, rounds=1)
    gofmt(wt)
