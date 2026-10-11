"""DEEPHARD Go recipes for build_deep.py: seeded changes with many sites whose
edits differ per site (handler bodies with early returns and nested func
literals, constructor results hoisted out of expression contexts with the
error checked in a context-dependent way, accessors whose callers use the
value in different expression contexts).

Same mechanics as deep_recipes_go.py (declarations by pattern, then the Go
compiler's own errors drive the call-site edits, iterated to a clean build;
gofmt), plus a small go/ast query helper (build/deephard_astq.go, built once
into $DEEP_WORK/_astq) that locates func literals, their own return
statements and the statement enclosing a call, so edits never touch nested
func literals and hoisted statements land in the right block.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write
import deep_edit as de
from deep_recipes_go import (GO, GIN, GIN_BASE, ECHO, ECHO_BASE, go_env, go_files,
                             compile_until_clean, gofmt)

CHI = bd.CORPUS / "chi"
CHI_BASE = "3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc"

ASTQ_SRC = Path(__file__).resolve().parent / "deephard_astq.go"


# ---------------------------------------------------------------- go/ast helper

def astq_bin() -> Path:
    d = bd.WORK / "_astq"
    exe = d / "astq"
    if exe.exists() and exe.stat().st_mtime >= ASTQ_SRC.stat().st_mtime:
        return exe
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.go").write_text(ASTQ_SRC.read_text())
    (d / "go.mod").write_text("module astq\n\ngo 1.25\n")
    subprocess.run([GO, "build", "-o", str(exe), "."], cwd=d, check=True, env=go_env())
    return exe


def astq(wt: Path, reqs: list[dict]) -> list:
    r = subprocess.run([str(astq_bin())], cwd=wt, input=json.dumps(reqs), capture_output=True,
                       text=True, check=True)
    return json.loads(r.stdout)


def q1(wt: Path, **req):
    return astq(wt, [req])[0]


# ---------------------------------------------------------------- byte-offset edits

def rb(wt: Path, f: str) -> bytes:
    return (wt / f).read_bytes()


def wb(wt: Path, f: str, data: bytes) -> None:
    (wt / f).write_bytes(data)


def apply_bedits(data: bytes, edits: list[tuple[int, int, str]]) -> bytes:
    for a, b, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        data = data[:a] + rep.encode() + data[b:]
    return data


def line_start(data: bytes, off: int) -> int:
    return data.rfind(b"\n", 0, off) + 1


def indent_of(data: bytes, off: int) -> str:
    ls = line_start(data, off)
    m = re.match(rb"[ \t]*", data[ls:off])
    return m.group(0).decode()


def ensure_import(data: bytes, path: str) -> bytes:
    if re.search(rb'^\s*(\w+\s+)?"' + re.escape(path.encode()) + rb'"\s*$', data, re.M):
        return data
    host = "/".join(path.split("/")[:2]).encode()
    sib = list(re.finditer(rb'^\t(\w+\s+)?"' + re.escape(host) + rb'/[^"]*"\n', data, re.M))
    if sib:  # next to an import from the same host (its own gofmt group)
        return data[:sib[-1].end()] + f'\t"{path}"\n'.encode() + data[sib[-1].end():]
    m = re.search(rb"^import \($", data, re.M)
    if m:
        return data[:m.end()] + f'\n\t"{path}"'.encode() + data[m.end():]
    m = re.search(rb'^import (\w+\s+)?"[^"]+"\s*$', data, re.M)
    if m:
        return data[:m.start()] + f'import "{path}"\n'.encode() + data[m.start():]
    m = re.search(rb"^package \w+\s*$", data, re.M)
    return data[:m.end()] + f'\n\nimport "{path}"\n'.encode() + data[m.end():]


def func_to_error_result(wt: Path, f: str, info: dict) -> bool:
    """Give a func (literal or decl, as answered by astq) an `error` result:
    ` error` after the parameter list, bare `return` -> `return nil` (its own
    returns only), and a final `return nil` unless the body already ends in a
    terminating statement. False if it already has results."""
    if info is None or info["has_results"]:
        return False
    data = rb(wt, f)
    edits = [(info["params_end"], info["params_end"], " error")]
    for r in info["returns"]:
        if r["n"] == 0:
            edits.append((r["start"], r["end"], "return nil"))
    if not info.get("last_terminating"):
        # same-line insertion (gofmt splits it): line numbers of later compile
        # errors in this file stay valid within a round
        rbrace = info["rbrace"]
        edits.append((rbrace, rbrace, "return nil " if not info["stmts"] else "; return nil "))
    wb(wt, f, apply_bedits(data, edits))
    return True


# ================================================================== gin HandlerFunc -> error

GIN_HF_INSTR = (
    "gin handlers cannot report failures except by writing a response or calling `c.Error` themselves. "
    "Change the handler type in gin.go from `type HandlerFunc func(*Context)` to "
    "`type HandlerFunc func(*Context) error`, and make `Context.Next` record a handler's non-nil error "
    "with `c.Error(err)` (appending it to `c.Errors`) before moving on to the next handler, exactly as "
    "if the handler had called `c.Error(err)` itself; a nil error changes nothing. Every handler in the "
    "module must then return an `error`: handler function literals (route handlers, middleware such as "
    "the closures returned by `Logger`/`LoggerWithConfig`, `Recovery`/`CustomRecoveryWithWriter`, "
    "`BasicAuthForRealm`, `ErrorLoggerT`, `WrapF`/`WrapH`, ...), named handler functions, and every "
    "handler in tests and in the `ginS` and `binding`/`render`/other subpackages. Existing handlers "
    "never fail: each returns `nil` -- every bare `return` in a handler's own body becomes `return nil` "
    "and a body that falls off the end gets a final `return nil` -- while `return` statements inside "
    "other func literals nested in a handler (stream callbacks, goroutines, deferred funcs) stay as they "
    "are. Do not add an adapter type or a wrapper that converts old-style `func(*Context)` handlers, and "
    "do not change `RecoveryFunc`, `HandlersChain` or the router's registration methods beyond what the "
    "new `HandlerFunc` type implies. Behavior must not change."
)

GIN_LIT = r"\bfunc\s*\(\s*(?:\w+\s+)?\*(?:gin\.)?Context\s*\)\s*\{"
GIN_DECL = r"(?m)^func\s+\w+\s*\(\s*\w+\s+\*(?:gin\.)?Context\s*\)\s*\{"


@recipe(instance_id="deephard__gin__HandlerFunc_return_error",
        repo="gin-gonic/gin", lang="go", repo_dir=GIN, base_commit=GIN_BASE,
        change="change a func type's result (HandlerFunc gains an error result): every handler literal, "
               "named handler and middleware closure returns error; bare returns in their own bodies "
               "become `return nil`, nested func literals untouched; Next records the error",
        instruction=GIN_HF_INSTR,
        decl_files=["gin.go", "context.go"],
        shapes=[{"id": "handler literal without result", "regex": GIN_LIT},
                {"id": "named handler without result", "regex": GIN_DECL},
                {"id": "HandlerFunc type", "regex": r"\btype\s+HandlerFunc\s+func\s*\(\s*\*Context\s*\)\s*$"}],
        gold_tool="build_deep.py deephard go recipe: type + Next by pattern; handler funcs located from go "
                  "build/go test compile errors (-gcflags=-e, default and nomsgpack tags) and rewritten with "
                  "go/ast positions (deephard_astq.go: own returns only, nested func literals excluded), "
                  "iterated to a clean build; gofmt (go1.25 GOTOOLCHAIN=local)",
        notes="Handler bodies vary: early bare returns, nested func literals with their own returns "
              "(c.Stream callbacks, goroutines, defers), panicking bodies, one-line literals, named handlers "
              "shared by several tests, closures returned by middleware factories.")
def make_gin_handlerfunc(wt: Path):
    f = "gin.go"
    raw = read(wt, f)
    assert raw.count("type HandlerFunc func(*Context)\n") == 1
    write(wt, f, raw.replace("type HandlerFunc func(*Context)\n", "type HandlerFunc func(*Context) error\n"))
    f = "context.go"
    raw = read(wt, f)
    old = "\t\tif c.handlers[c.index] != nil {\n\t\t\tc.handlers[c.index](c)\n\t\t}\n"
    assert raw.count(old) == 1
    write(wt, f, raw.replace(old, "\t\tif c.handlers[c.index] != nil {\n"
                                  "\t\t\tif err := c.handlers[c.index](c); err != nil {\n"
                                  "\t\t\t\t_ = c.Error(err)\n\t\t\t}\n\t\t}\n"))

    pkg_funcs: dict[str, list[str]] = {}

    def decl_files(d: str) -> list[str]:
        if d not in pkg_funcs:
            pkg_funcs[d] = [x for x in go_files(wt) if str(Path(x).parent) == d]
        return pkg_funcs[d]

    def fix(f, line, col, msg):
        if os.environ.get("DEEPHARD_DEBUG"):
            print("   fix", f, line, col, msg[:90], flush=True)
        if not re.search(r"\bHandlerFunc\b|func\(\w* ?\*(gin\.)?Context\) error", msg):
            return False
        m = re.match(r"cannot use (func\(|(\w+) \((?:value|variable) of type func)", msg)
        if not m:
            return False
        if m.group(1) == "func(":
            info = q1(wt, op="funcat", file=f, line=line, col=col)
            if info is None:
                return False
            func_to_error_result(wt, f, info)
            return True
        name = m.group(2)
        if "variable of type" in msg:  # a local `name := func(c *Context) {...}`
            data = rb(wt, f)
            ls = sum(len(l) for l in data.splitlines(keepends=True)[:line - 1])
            defs = list(re.finditer(rb"(?:\b" + re.escape(name.encode()) + rb"\s*:?=\s*|\bvar\s+"
                                    + re.escape(name.encode()) + rb"\s*=\s*)(func\s*\()", data[:ls]))
            if not defs:
                return False
            info = q1(wt, op="funcat", file=f, line=0, col=defs[-1].start(1))
            if info is None or info["start"] != defs[-1].start(1):
                return False
            func_to_error_result(wt, f, info)
            return True
        for g in decl_files(str(Path(f).parent)):
            if re.search(rf"(?m)^func {re.escape(name)}\(", read(wt, g)):
                func_to_error_result(wt, g, q1(wt, op="funcdecl", file=g, name=name))
                return True
        return False

    compile_until_clean(wt, ["", "nomsgpack"], fix, rounds=12)
    gofmt(wt)


# ================================================================== echo XxxWithConfig -> (MiddlewareFunc, error)

ECHO_WC_INSTR = (
    "The middleware package's `XxxWithConfig(config XxxConfig) echo.MiddlewareFunc` constructors panic on "
    "an invalid configuration, so a misconfigured middleware brings the whole server down at startup. "
    "Change every one of them -- `BasicAuthWithConfig`, `BodyDumpWithConfig`, `BodyLimitWithConfig`, "
    "`GzipWithConfig`, `ContextTimeoutWithConfig`, `CORSWithConfig`, `CSRFWithConfig`, "
    "`DecompressWithConfig`, `KeyAuthWithConfig`, `MethodOverrideWithConfig`, `ProxyWithConfig`, "
    "`RateLimiterWithConfig`, `RecoverWithConfig`, the five `...RedirectWithConfig` constructors, "
    "`RequestIDWithConfig`, `RequestLoggerWithConfig`, `RewriteWithConfig`, `SecureWithConfig`, "
    "`AddTrailingSlashWithConfig`, `RemoveTrailingSlashWithConfig` and `StaticWithConfig` -- to return "
    "`(echo.MiddlewareFunc, error)`, i.e. the result of `config.ToMiddleware()`, instead of panicking. The "
    "convenience constructors without a config (`BasicAuth(fn)`, `CORS(...)`, `Gzip()`, `Proxy(b)`, "
    "`HTTPSRedirect()`, `Static(root)`, ...) keep returning a bare `echo.MiddlewareFunc` and keep "
    "panicking on invalid input: they call the `...WithConfig` function and panic with its non-nil error. "
    "Update every other caller of a `...WithConfig` middleware constructor (all "
    "of them are tests): bind both results (`mw, err := ...`) and check the error with "
    "`require.NoError(t, err)` using the test's `*testing.T`/`*testing.B` before using the middleware "
    "(in a function without one, panic on a non-nil error); a call nested inside another expression "
    "(`e.Use(CORSWithConfig(cfg))`, `RewriteWithConfig(cfg)(handler)`, a struct field) must be hoisted into "
    "its own statement just before the statement that uses it. Tests that asserted a constructor panics "
    "(`assert.Panics(t, func() { XxxWithConfig(bad) })`) must instead assert the returned error "
    "(`assert.Error`), and `assert.NotPanics` around a constructor becomes `assert.NoError` on its error; "
    "panic assertions about the convenience constructors and about running a handler stay. Do not change "
    "`echo.NewWithConfig`, `NewRateLimiterMemoryStoreWithConfig` or the `ToMiddleware` methods, and do "
    "not add `Must...` helpers or other wrappers. Behavior of valid configurations must not change."
)

ECHO_WC_NAMES = ["BasicAuth", "BodyDump", "BodyLimit", "Gzip", "ContextTimeout", "CORS", "CSRF", "Decompress",
                 "KeyAuth", "MethodOverride", "Proxy", "RateLimiter", "Recover", "HTTPSRedirect",
                 "HTTPSWWWRedirect", "HTTPSNonWWWRedirect", "WWWRedirect", "NonWWWRedirect", "RequestID",
                 "RequestLogger", "Rewrite", "Secure", "AddTrailingSlash", "RemoveTrailingSlash", "Static"]
ECHO_WC = r"\b(?:" + "|".join(ECHO_WC_NAMES) + r")WithConfig\b"


def _lower_first(s: str) -> str:
    i = 0
    while i < len(s) and s[i].isupper():
        i += 1
    if i > 1 and i < len(s):
        i -= 1
    return s[:i].lower() + s[i:]


def _test_var(funcs: list[dict]) -> str | None:
    for fn in funcs:  # innermost first; closures capture an outer t
        for name, typ in fn["params"]:
            if typ in ("*testing.T", "*testing.B", "testing.TB") and name and name != "_":
                return name
    return None


def _fresh(data: bytes, a: int, b: int, base: str) -> str:
    seg = de.mask(data[a:b].decode(errors="ignore"), "x.go")
    name, k = base, 2
    while re.search(rf"(?<![\w.]){re.escape(name)}\b", seg):
        name, k = f"{base}{k}", k + 1
    return name


@recipe(instance_id="deephard__echo__WithConfig_return_error",
        repo="labstack/echo", lang="go", repo_dir=ECHO, base_commit=ECHO_BASE,
        change="change 25 constructors' result T -> (T, error); wrappers switch to the panicking helper, every "
               "other call is hoisted out of its expression and error-checked with the in-scope *testing.T; "
               "panic/no-panic assertions become error assertions",
        instruction=ECHO_WC_INSTR,
        decl_files=["middleware/middleware.go"],
        shapes=[{"id": "WithConfig returns MiddlewareFunc",
                 "regex": r"(?m)^func\s+\w+WithConfig\s*\([^()]*\)\s*echo\.MiddlewareFunc\s*\{"},
                {"id": "single-result WithConfig use",
                 "regex": r"(?m)(?:^\s*(?:[\w.]+)\s*:?=\s*|[(,]\s*|^\s*return\s+|^\s*)" + ECHO_WC + r"\s*\("},
                {"id": "Panics around WithConfig",
                 "regex": r"\bassert\.(?:Not)?Panics\(\s*\w+\s*,\s*func\(\)\s*\{\s*(?:\w+\s*:=\s*)?" + ECHO_WC}],
        gold_tool="build_deep.py deephard go recipe: declarations + wrapper returns by pattern; (Not)Panics "
                  "assertions around a constructor rewritten to error assertions; every remaining caller "
                  "hoisted with go/ast statement positions (deephard_astq.go) and checked with the enclosing "
                  "test's require.NoError, driven by go build/go test compile errors; gofmt (go1.25)",
        notes="Call contexts: e.Use(X(cfg)), e.Pre(X(cfg)), X(cfg)(handler)(c), mw := X(cfg), table-driven "
              "subtests (t from the t.Run closure), benchmarks (*testing.B), assert.Panics closures.")
def make_echo_withconfig(wt: Path):
    # 1. declarations: (echo.MiddlewareFunc, error), returning config.ToMiddleware()
    n = 0
    names = "|".join(ECHO_WC_NAMES)
    for f in go_files(wt):
        if not f.startswith("middleware/") or f.endswith("_test.go"):
            continue
        raw = read(wt, f)
        new, k = re.subn(r"(?m)^(func\s+(?:" + names + r")WithConfig\s*\(config\s+\w+\)\s*)echo\.MiddlewareFunc(\s*\{\n)"
                         r"((?:\t.*\n|\n)*?)"
                         r"(?:\treturn toMiddlewareOrPanic\(config\)\n|\tmw, err := config\.ToMiddleware\(\)\n"
                         r"\tif err != nil \{\n\t\tpanic\(err\)\n\t\}\n\treturn mw\n)\}",
                         r"\1(echo.MiddlewareFunc, error)\2\3\treturn config.ToMiddleware()\n}", raw)
        n += k
        if new != raw:
            write(wt, f, new)
    print(f"  declarations: {n}")
    assert n == len(ECHO_WC_NAMES), n

    # 2. (Not)Panics closures whose body constructs the middleware
    for f in go_files(wt):
        if not f.endswith("_test.go"):
            continue
        data = rb(wt, f)
        if not re.search(ECHO_WC.encode(), data):
            continue
        edits = []
        for m in re.finditer(rb"(?m)^([ \t]*)assert\.(Not)?Panics\((\w+), func\(\) \{\n((?:.*\n)*?)\1\}\)\n", data):
            ind, notp, t, body = m.group(1).decode(), m.group(2), m.group(3).decode(), m.group(4).decode()
            first, _, rest = body.partition("\n")
            cm = re.match(r"\s*(?:(\w+) := )?(" + ECHO_WC + r"\(.*)$", first)
            if not cm:
                continue
            # the call may span several lines: take lines until parens balance
            call = cm.group(2)
            lines = rest.split("\n")
            bal = lambda x: (lambda mk: mk.count("(") + mk.count("{") - mk.count(")") - mk.count("}"))(de.mask(x, "x.go"))
            while bal(call) > 0:
                call += "\n" + lines.pop(0)
            rest_lines = [l for l in lines if l.strip()]
            var = cm.group(1)
            if notp:
                lhs = f"{var}, err" if var else "_, err"
                out = f"{ind}{lhs} := {call.strip()}\n{ind}assert.NoError({t}, err)\n"
                for l in rest_lines:
                    out += ind + l.strip() + "\n"
            else:
                out = f"{ind}_, err := {call.strip()}\n{ind}assert.Error({t}, err)\n"
            edits.append((m.start(), m.end(), out))
        if edits:
            wb(wt, f, apply_bedits(data, edits))
            print(f"  panic assertions rewritten in {f}: {len(edits)}")

    # 3. compile-driven hoisting
    def fix(f, line, col, msg):
        if "no new variables on left side of :=" in msg or msg == "err redeclared in this block":
            data = rb(wt, f)
            ls = sum(len(l) for l in data.splitlines(keepends=True)[:line - 1])
            eol = data.index(b"\n", ls)
            ln = data[ls:eol]
            if not re.search(rb"\berr :=", ln):
                return False
            wb(wt, f, data[:ls] + ln.replace(b" := ", b" = ", 1) + data[eol:])
            return True
        if msg.startswith("too many return values"):  # wrapper: return XxxWithConfig(...)
            calls = [c for n_ in ECHO_WC_NAMES for c in q1(wt, op="calls", file=f, name=n_ + "WithConfig")
                     if c["line"] == line]
            if len(calls) != 1:
                return False
            name = rb(wt, f)[calls[0]["start"]:calls[0]["lparen"]].decode()
        else:
            mm = re.search(r"(?:multiple-value (\w+WithConfig)\(|assignment mismatch: 1 variable but (\w+WithConfig) returns 2 values"
                           r"|^cannot use (\w+WithConfig)\(.*\(value of interface type error\))", msg)
            if mm and mm.group(3):  # f(X(cfg)) into a variadic ...MiddlewareFunc: spread of both results
                mm = re.search(r"(\w+WithConfig)", msg)
            if not mm or not re.fullmatch(ECHO_WC, mm.group(1) or mm.group(2)):
                return False
            name = mm.group(1) or mm.group(2)
            calls = [c for c in q1(wt, op="calls", file=f, name=name) if c["line"] == line and c["col"] >= col]
            if not calls:
                calls = [c for c in q1(wt, op="calls", file=f, name=name) if c["line"] == line]
        if not calls:
            return False
        c = min(calls, key=lambda c: c["col"])
        data = rb(wt, f)
        st = q1(wt, op="stmt", file=f, line=0, col=c["start"])
        if st is None:
            return False
        if re.match(r"\w+, (?:err|mwErr) :?= ", data[st["start"]:st["end"]].decode()):
            return True  # already bound (another error on the same statement)
        tvar = _test_var(st["funcs"])
        fstart = st["funcs"][0]["start"]
        ind = indent_of(data, st["start"])
        call_txt = data[c["start"]:c["end"]].decode()
        fend = data.find(b"\n}\n", st["end"])
        # a later `var err error` in the same function would clash with a hoisted err
        ev = "mwErr" if re.search(rb"\bvar err\b", data[fstart:fend if fend > 0 else len(data)]) else "err"
        check = f"require.NoError({tvar}, {ev})" if tvar else f"if {ev} != nil {{\npanic({ev})\n}}"
        # `x := X(...)` / `x = X(...)` statement: bind err alongside
        stmt_txt = data[st["start"]:st["end"]].decode()
        am = re.fullmatch(r"(\w+)\s*(:?=)\s*" + re.escape(call_txt), stmt_txt)
        if am:
            rep = f"{am.group(1)}, {ev} {am.group(2)} {call_txt}\n{ind}{check}"
            data = apply_bedits(data, [(st["start"], st["end"], rep)])
        else:
            base = _lower_first(name[:-len("WithConfig")]) + "MW"
            var = _fresh(data, fstart, st["funcs"][0].get("end", st["end"] + 1), base)
            hoist = f"{var}, {ev} := {call_txt}\n{ind}{check}\n{ind}"
            data = apply_bedits(data, [(c["start"], c["end"], var), (st["start"], st["start"], hoist)])
        if tvar:
            data = ensure_import(data, "github.com/stretchr/testify/require")
        wb(wt, f, data)
        return True

    compile_until_clean(wt, [""], fix, rounds=12)
    gofmt(wt)


# ================================================================== chi URLParam -> (string, bool)

CHI_UP_INSTR = (
    "chi cannot tell a missing URL parameter from an empty one: `URLParam`, `URLParamFromCtx` and "
    "`(*Context).URLParam` all return \"\" for both, and `RouteContext` returns a nil `*Context` when the "
    "request carries no routing context. Make both explicit, comma-ok style: change "
    "`URLParam(r *http.Request, key string) string`, `URLParamFromCtx(ctx context.Context, key string) "
    "string` and `(x *Context) URLParam(key string) string` (context.go) to return `(string, bool)`, where "
    "the bool reports whether the routing context has a parameter with that key (\"\", false when it does "
    "not, or when there is no routing context), and change `RouteContext(ctx context.Context) *Context` to "
    "return `(*Context, bool)` (ok reports whether a routing context is present; the pointer is nil "
    "exactly when ok is false). Update every caller in the module (mux, tree, the middleware package and "
    "all tests): callers that only need the value discard the bool (`v, _ := ...`); a call used inside "
    "a larger expression (a `fmt.Sprintf`/`fmt.Fprintf` argument, `[]byte(...)`, a string concatenation, a "
    "comparison) must be hoisted into its own `name, _ := ...` statement just before the statement that "
    "uses it, keeping the evaluation order of the arguments; callers that guarded on `rctx != nil` may "
    "keep doing so. Do not add single-result helpers or wrappers (in tests either), and do not change "
    "`URLParams`/`RouteParams` or the `_examples` modules. Behavior must not change."
)

CHI_HOIST_NAME = {"*": "wildcard"}


@recipe(instance_id="deephard__chi__URLParam_comma_ok",
        repo="go-chi/chi", lang="go", repo_dir=CHI, base_commit=CHI_BASE,
        change="change four accessors' results T -> (T, bool) (URLParam, URLParamFromCtx, Context.URLParam, "
               "RouteContext); callers in expression contexts are hoisted into named statements",
        instruction=CHI_UP_INSTR,
        decl_files=["context.go"],
        shapes=[{"id": "URLParam single-value use",
                 "regex": r"(?m)(?:^\s*\w+\s*:?=\s*|[(,+]\s*|==\s*|^\s*return\s+)(?:chi\.|\w+\.)?URLParam(?:FromCtx)?\s*\("},
                {"id": "RouteContext single-value use",
                 "regex": r"(?m)(?:^\s*\w+\s*:?=\s*|[(,]\s*|^\s*return\s+|\bif\s+\w+\s*:=\s*)(?:chi\.)?RouteContext\s*\("},
                {"id": "string-result decl",
                 "regex": r"(?m)^func\s+(?:\(\w+\s+\*Context\)\s+)?(?:URLParam|URLParamFromCtx)\s*\([^()]*\)\s*string\s*\{"},
                {"id": "RouteContext decl", "regex": r"(?m)^func\s+RouteContext\s*\([^()]*\)\s*\*Context\s*\{"}],
        gold_tool="build_deep.py deephard go recipe: context.go declarations by explicit edit; callers from go "
                  "build/go test compile errors: `x := f()` binds `x, _`, other uses hoisted into "
                  "`<key-named var>, _ := f()` statements at go/ast statement positions (deephard_astq.go); "
                  "gofmt (go1.25)",
        notes="Hoisted names come from the parameter key (\"hubID\" -> hubID, \"*\" -> wildcard); several calls "
              "in one fmt.Sprintf are hoisted in argument order.")
def make_chi_urlparam(wt: Path):
    f = "context.go"
    raw = read(wt, f)
    subs = [
        ("func URLParam(r *http.Request, key string) string {",
         "func URLParam(r *http.Request, key string) (string, bool) {"),
        ("func URLParamFromCtx(ctx context.Context, key string) string {\n"
         "\tif rctx := RouteContext(ctx); rctx != nil {\n\t\treturn rctx.URLParam(key)\n\t}\n\treturn \"\"\n}",
         "func URLParamFromCtx(ctx context.Context, key string) (string, bool) {\n"
         "\tif rctx, ok := RouteContext(ctx); ok {\n\t\treturn rctx.URLParam(key)\n\t}\n\treturn \"\", false\n}"),
        ("func RouteContext(ctx context.Context) *Context {\n\tval, _ := ctx.Value(RouteCtxKey).(*Context)\n\treturn val\n}",
         "func RouteContext(ctx context.Context) (*Context, bool) {\n\tval, _ := ctx.Value(RouteCtxKey).(*Context)\n"
         "\treturn val, val != nil\n}"),
        ("func (x *Context) URLParam(key string) string {\n\tfor i, k := range slices.Backward(x.URLParams.Keys) {\n"
         "\t\tif k == key {\n\t\t\treturn x.URLParams.Values[i]\n\t\t}\n\t}\n\treturn \"\"\n}",
         "func (x *Context) URLParam(key string) (string, bool) {\n\tfor i, k := range slices.Backward(x.URLParams.Keys) {\n"
         "\t\tif k == key {\n\t\t\treturn x.URLParams.Values[i], true\n\t\t}\n\t}\n\treturn \"\", false\n}"),
    ]
    for old, new in subs:
        assert raw.count(old) == 1, old[:60]
        raw = raw.replace(old, new)
    write(wt, f, raw)

    names = ("URLParam", "URLParamFromCtx", "RouteContext")

    def fix(f, line, col, msg):
        mm = re.search(r"(?:multiple-value (?:[\w.]+\.)?(\w+)\(|assignment mismatch: (\d+) variables? but "
                       r"(?:[\w.]+\.)?(\w+) returns 2 values)", msg)
        if not mm:
            return False
        name = mm.group(1) or mm.group(3)
        if name not in names:
            return False
        calls = [c for c in q1(wt, op="calls", file=f, name=name) if c["line"] == line]
        if not calls:
            return False
        data = rb(wt, f)
        # this error's call: at the reported column, else the first on the line
        c = next((c for c in calls if c["col"] == col), None) or \
            next((c for c in calls if c["col"] > col), calls[0])
        st = q1(wt, op="stmt", file=f, line=0, col=c["start"])
        if st is None:
            return False
        stmt_txt = data[st["start"]:st["end"]].decode()
        if re.match(r"(?:if\s+)?\w+, _ :?= ", stmt_txt):
            return True  # hoisted already (another error on the same statement)
        call_txt = data[c["start"]:c["end"]].decode()
        am = re.fullmatch(r"(\w+)\s*(:?=)\s*" + re.escape(call_txt), stmt_txt)
        if am:  # x := f(...)  ->  x, _ := f(...)
            wb(wt, f, apply_bedits(data, [(st["start"], st["start"] + len(am.group(1).encode()),
                                           am.group(1) + ", _")]))
            return True
        im = re.match(r"if\s+(\w+)\s*:=\s*" + re.escape(call_txt) + r"\s*;", stmt_txt)
        if im:  # if rctx := RouteContext(ctx); ...
            a = st["start"] + stmt_txt.index(im.group(1))
            wb(wt, f, apply_bedits(data, [(a, a + len(im.group(1)), im.group(1) + ", _")]))
            return True
        # hoist every call of these names in this statement that is not yet hoisted, in order
        ind = indent_of(data, st["start"])
        fstart = st["funcs"][0]["start"] if st["funcs"] else 0
        group = [x for n in names for x in q1(wt, op="calls", file=f, name=n)
                 if st["start"] <= x["start"] and x["end"] <= st["end"]]
        group.sort(key=lambda x: x["start"])
        # outermost only (a call nested inside another hoisted call's args stays inside it)
        outer = [x for x in group if not any(y is not x and y["start"] <= x["start"] and x["end"] <= y["end"]
                                             for y in group)]
        edits, hoist, used = [], "", set()
        for x in outer:
            ctxt = data[x["start"]:x["end"]].decode()
            km = re.search(r'"([^"]*)"\s*\)$', ctxt)
            key = km.group(1) if km else ""
            base = CHI_HOIST_NAME.get(key) or (re.sub(r"\W", "", key) if re.fullmatch(r"[A-Za-z_][\w-]*", key) else "")
            base = base[0].lower() + base[1:] if base else ("rctx" if "RouteContext" in ctxt else "param")
            if base in ("type", "func", "range", "map", "go", "select", "case"):
                base += "Param"
            var = base
            k = 2
            fend = st["funcs"][0]["end"] if st["funcs"] else len(data)
            scope = de.mask(data[fstart:fend].decode(errors="ignore"), "x.go")  # code only, not strings
            while var in used or re.search(rf"(?<![\w.]){re.escape(var)}\b", scope):
                var, k = f"{base}{k}", k + 1
            used.add(var)
            hoist += f"{var}, _ := {ctxt}\n{ind}"
            edits.append((x["start"], x["end"], var))
        edits.append((st["start"], st["start"], hoist))
        wb(wt, f, apply_bedits(data, edits))
        return True

    compile_until_clean(wt, [""], fix, rounds=12)
    gofmt(wt)
