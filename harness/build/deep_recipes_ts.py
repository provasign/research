"""TypeScript recipes for build_deep.py (hono, zod, h3).

The type checker runs in a long-lived node:20 container per checkout: the
source is copied in (never node_modules onto the host bind mount, same as
js_eval), dependencies are installed once with the scorer's own install
command, and every round re-syncs the source and runs `tsc --noEmit`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write
import deep_edit as de

import js_eval

HONO = bd.CORPUS / "hono"
HONO_BASE = "7c3b0df96dbf3e767968ff5afe4c0d999257b8ee"
ZOD = bd.CORPUS / "zod"
ZOD_BASE = "7a00236683c79000dbab0d92f6faf0b7fba39f59"
H3 = bd.CORPUS / "h3"
H3_BASE = "7eb018eda1221276fbb4ba1772a0b731ec9aa2d4"

TSC = {
    "honojs/hono": "npx tsc -p tsconfig.spec.json --noEmit --pretty false",
    "colinhacks/zod": "npx tsc -p packages/zod/tsconfig.json --noEmit --pretty false",
    "h3js/h3": "npx tsc --noEmit -p tsconfig.json --pretty false",
}

TS_ERR = re.compile(r"^(\S+?\.tsx?)\((\d+),(\d+)\): error (TS\d+): (.*)$", re.M)


def _docker(*a, timeout=3600, check=True) -> str:
    r = subprocess.run(["docker", *a], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"docker {a[:3]}: {(r.stdout + r.stderr)[-1500:]}")
    return r.stdout + r.stderr


class TsBox:
    """A node:20 container holding a copy of the checkout plus node_modules."""

    def __init__(self, wt: Path, repo: str):
        self.wt, self.repo = wt, repo
        self.name = "deep-ts-" + re.sub(r"[^a-z0-9]+", "-", wt.parent.name.lower())[-50:]
        _docker("rm", "-f", self.name, check=False)
        _docker("run", "-d", "--name", self.name, "-v", f"{wt}:/src:ro",
                "-v", f"{js_eval.NPM_CACHE}:/root/.npm", "-v", f"{js_eval.PNPM_STORE}:/pnpm-store",
                "-v", f"{js_eval.BUN_CACHE}:/root/.bun/install/cache",
                js_eval.IMAGE, "sleep", "infinity")
        self.sync()
        out = _docker("exec", "-w", "/w", self.name, "bash", "-c",
                      f"({js_eval.INSTALL_CMD[repo]}) >/tmp/install.log 2>&1 || {{ tail -40 /tmp/install.log; exit 3; }}")
        print("  installed deps", out[-200:], flush=True)

    def sync(self) -> None:
        _docker("exec", self.name, "bash", "-c",
                "mkdir -p /w && cd /w && find . -path ./node_modules -prune -o -path '*/node_modules' -prune "
                "-o -type f -print0 | xargs -0 rm -f; "
                "cd /src && tar --exclude=./.git --exclude=node_modules -cf - . | tar -C /w -xf -")

    def tsc(self) -> tuple[bool, list, str]:
        self.sync()
        r = subprocess.run(["docker", "exec", "-w", "/w", self.name, "bash", "-c", TSC[self.repo] + " 2>&1"],
                           capture_output=True, text=True, timeout=3600)
        out = r.stdout + r.stderr
        errs = [(m.group(1), int(m.group(2)), int(m.group(3)), m.group(4), m.group(5)) for m in TS_ERR.finditer(out)]
        return r.returncode == 0, errs, out[-3000:]

    def close(self) -> None:
        _docker("rm", "-f", self.name, check=False)


def tsc_until_clean(box: TsBox, fix_error, rounds: int = 10, baseline: set | None = None) -> None:
    """baseline: {(file, code, message)} errors already present at base (zod's
    test files carry some); they are ignored."""
    last = None
    baseline = baseline or set()
    for i in range(rounds):
        ok, errs, tail = box.tsc()
        errs = [e for e in errs if (e[0], e[3], e[4]) not in baseline]
        print(f"  tsc round {i}: ok={ok} errors={len(errs)}", flush=True)
        if ok or not errs and baseline and "error TS" in tail:
            return
        if not errs:
            raise RuntimeError("tsc failed without parsable errors:\n" + tail)
        key = sorted(errs)
        if key == last:
            raise RuntimeError("no progress:\n" + "\n".join(map(str, errs[:30])))
        last = key
        handled = 0
        seen = set()
        for e in sorted(errs, key=lambda e: (e[0], -e[1], -e[2])):
            if (e[0], e[1]) in seen:
                continue
            if fix_error(*e):
                handled += 1
                seen.add((e[0], e[1]))
        if not handled:
            raise RuntimeError("unhandled errors:\n" + "\n".join(map(str, errs[:30])))
    raise RuntimeError("did not converge")


def ts_files(wt: Path) -> list[str]:
    return de.code_files(wt, (".ts", ".tsx", ".mts"))


# ------------------------------------------------------------- shared edits

def make_enclosing_async(raw: str, masked: str, pos: int) -> tuple[int, str] | None:
    """Edit (offset, "async ") that makes the function whose body holds pos
    async: an arrow `(...) => {`/`x => {`, a `function` or a method `m(...) {`.
    None if it is already async."""
    depth = 0
    i = pos - 1
    while i >= 0:
        ch = masked[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                before = masked[:i].rstrip()
                if before.endswith("=>"):
                    j = len(before) - 2
                    head = masked[:j].rstrip()
                    if head.endswith(")"):
                        d, k = 0, len(head) - 1
                        while k >= 0:
                            d += head[k] == ")"
                            d -= head[k] == "("
                            if d == 0:
                                break
                            k -= 1
                        start = k
                    else:
                        m = re.search(r"[\w$]+$", head)
                        start = m.start()
                    if re.search(r"\basync\s*$", masked[:start]):
                        return None
                    return (start, "async ")
                if before.endswith(")"):
                    d, k = 0, len(before) - 1
                    while k >= 0:
                        d += before[k] == ")"
                        d -= before[k] == "("
                        if d == 0:
                            break
                        k -= 1
                    m = re.search(r"(\bfunction\s*\*?\s*[\w$]*\s*|[\w$]+\s*)$", masked[:k])
                    if m and not re.match(r"(if|for|while|switch|catch)\b", m.group(0).strip()):
                        if re.search(r"\basync\s*$", masked[:m.start()]):
                            return None
                        return (m.start(), "async ")
                # a block ({ of if/for/object literal...): keep walking out
            else:
                depth -= 1
        i -= 1
    return None


def line_col_offset(raw: str, line: int, col: int) -> int:
    return bd.line_offset(raw, line, col)


# build_deep.make_gold copies a fixed set of recipe keys into the spec; TS
# recipes also carry "typecheck_cmd" (js_eval runs it after the suite and
# requires it to pass). Copy it into the spec here, without touching
# build_deep.py: wrap make_gold for recipes that set it.
_orig_make_gold = bd.make_gold


def _make_gold_with_extras(tid: str) -> dict:
    spec = _orig_make_gold(tid)
    r = bd.RECIPES[tid]
    extra = {k: r[k] for k in ("typecheck_cmd",) if k in r}
    if extra:
        spec.update(extra)
        import json
        (bd.task_dir(tid) / "spec.json").write_text(json.dumps(spec, indent=1))
    return spec


if bd.make_gold is _orig_make_gold and getattr(bd.make_gold, "__name__", "") == "make_gold":
    bd.make_gold = _make_gold_with_extras


HONO_TC = "npx tsc -p tsconfig.spec.json"

# ------------------------------------------------------------------ T1
# hono: GetConnInfo (c) => ConnInfo  ->  (c) => Promise<ConnInfo>

GCI_INSTR = (
    "Some runtimes can only look up the client's connection info asynchronously, so hono's "
    "connection-info helper has to become async. Change the `GetConnInfo` type in "
    "`src/helper/conninfo/types.ts` from `(c: Context) => ConnInfo` to `(c: Context) => Promise<ConnInfo>`, and "
    "make every adapter's `getConnInfo` (aws-lambda, bun, cloudflare-pages, cloudflare-workers, deno, "
    "lambda-edge, netlify, vercel) an `async` function returning the same `ConnInfo` as before. Then update "
    "every caller to await the result: the `ipRestriction` middleware (which must keep accepting a plain "
    "`(c) => string` getter too), every test that calls a `getConnInfo` or defines its own `GetConnInfo`, "
    "and every other use. Where a test expected `getConnInfo(c)` to throw, it must now expect the returned "
    "promise to reject with the same error. Do not keep a synchronous variant. The connection info returned "
    "and the middleware's behavior must not change, and the project must still type-check "
    "(`tsc -p tsconfig.spec.json`)."
)


@recipe(instance_id="deep__hono__getConnInfo_async",
        repo="honojs/hono", lang="ts", repo_dir=HONO, base_commit=HONO_BASE,
        change="change return type (sync ConnInfo -> Promise<ConnInfo>; async cascade into callers)",
        instruction=GCI_INSTR, typecheck_cmd=HONO_TC,
        decl_files=["src/helper/conninfo/types.ts"],
        shapes=[
            {"id": "gci/sync-impl", "regex": r"\bgetConnInfo\s*:\s*GetConnInfo\s*=\s*\("},
            {"id": "gci/sync-type", "regex": r"\bGetConnInfo\s*=\s*\([^)]*\)\s*=>\s*ConnInfo\b"},
            {"id": "gci/unawaited-call", "regex": r"(?<!await )(?<![\w$.])getConnInfo\s*\("},
            {"id": "gci/unawaited-getIP", "regex": r"(?<!await )(?<![\w$.])getIP\s*\("},
            {"id": "gci/sync-inline-getter", "regex": r"ipRestriction\(\s*(\([^()]*\)|[\w$]+)\s*=>\s*\(\{"},
        ],
        gold_tool="build_deep.py recipe (deep_recipes_ts): async on each GetConnInfo implementation by pattern, "
                  "await at every call, enclosing callbacks made async from tsc's TS1308 errors, "
                  "toThrowError -> rejects.toThrowError; iterated to a clean `tsc -p tsconfig.spec.json`",
        notes="The shapes are the sync forms gold removes; an unawaited call left in a test also fails the test "
              "(a Promise has no .remote). typecheck_cmd is hono's own pre-test type check.")
def make_gci(wt: Path):
    box = TsBox(wt, "honojs/hono")
    try:
        f = "src/helper/conninfo/types.ts"
        write(wt, f, read(wt, f).replace("export type GetConnInfo = (c: Context) => ConnInfo",
                                         "export type GetConnInfo = (c: Context) => Promise<ConnInfo>"))
        for f in ts_files(wt):
            raw = read(wt, f)
            if "getConnInfo" not in raw and "getIP(" not in raw:
                continue
            new = re.sub(r"(\bgetConnInfo\s*:\s*GetConnInfo\s*=\s*)\(", r"\1async (", raw)
            # expect(() => getConnInfo(c)).toThrowError(X) -> await expect(getConnInfo(c)).rejects.toThrowError(X)
            new = re.sub(r"expect\(\(\)\s*=>\s*getConnInfo\((\w+)\)\)\.toThrow(Error)?\(",
                         r"await expect(getConnInfo(\1)).rejects.toThrow\2(", new)
            new = re.sub(r"(?<![\w$.])(?<!await )(?<!expect\()getConnInfo\((\w+)\)", r"await getConnInfo(\1)", new)
            new = new.replace("const connInfo = getIP(c)", "const connInfo = await getIP(c)")
            if new != raw:
                write(wt, f, new)

        def fix(f, line, col, code, msg):
            raw = read(wt, f)
            pos = line_col_offset(raw, line, col)
            if code in ("TS1308", "TS1359") or "only allowed within async functions" in msg:
                m = de.mask(raw, f)
                e = make_enclosing_async(raw, m, pos)
                if not e:
                    return False
                write(wt, f, de.apply_edits(raw, [(e[0], e[0], e[1])]))
                return True
            if code == "TS2322" and "Promise<ConnInfo>" in msg:
                # an inline sync getter `(c) => ({ remote })` handed to ipRestriction
                m = de.mask(raw, f)
                k = m.rfind("=>", 0, pos + 1)
                head = m[:k].rstrip()
                if not head.endswith(")"):
                    return False
                start = head.rfind("(")
                write(wt, f, raw[:start] + "async " + raw[start:])
                return True
            return False

        tsc_until_clean(box, fix)
    finally:
        box.close()


# ------------------------------------------------------------------ T2
# hono: new HTTPException(status, options?) -> new HTTPException({ status, ...options })

HE_INSTR = (
    "`new HTTPException(401, { res })` splits one error description across a positional status and an "
    "options bag. Change the constructor of `HTTPException` (src/http-exception.ts) to take a single, "
    "required options object that carries the status: `constructor(options: HTTPExceptionOptions & { status: "
    "ContentfulStatusCode })`, used as `new HTTPException({ status: 401, res })`. The status is now required "
    "(there is no implicit 500 default any more); `res`, `message` and `cause` keep their meaning. Update "
    "every `new HTTPException(...)` in the repository -- middleware, helpers, the validator, request "
    "handling and all tests -- so each passes the same status and options it passes today. Do not keep the "
    "positional form or an overload for it. Behavior must not change, the tests must pass and the project "
    "must still type-check (`tsc -p tsconfig.spec.json`)."
)


@recipe(instance_id="deep__hono__HTTPException_options_object",
        repo="honojs/hono", lang="ts", repo_dir=HONO, base_commit=HONO_BASE,
        change="constructor signature change (positional status + options -> one required options object)",
        instruction=HE_INSTR, typecheck_cmd=HONO_TC,
        decl_files=["src/http-exception.ts"],
        shapes=[
            {"id": "he/positional-call", "regex": r"\bHTTPException\s*\(\s*(?!\{)"},
            {"id": "he/positional-ctor", "regex": r"\bconstructor\s*\(\s*status\b"},
        ],
        gold_tool="build_deep.py recipe (deep_recipes_ts): every `HTTPException(` call found in comment/string-"
                  "masked source, its status folded into the options object literal (or spread when the options "
                  "are not a literal); verified with `tsc -p tsconfig.spec.json`",
        notes="The positional-call shape is any HTTPException( whose first argument is not an object literal.")
def make_he(wt: Path):
    box = TsBox(wt, "honojs/hono")
    try:
        f = "src/http-exception.ts"
        raw = read(wt, f)
        old = ("  constructor(status: ContentfulStatusCode = 500, options?: HTTPExceptionOptions) {\n"
               "    super(options?.message, { cause: options?.cause })\n"
               "    this.res = options?.res\n"
               "    this.status = status\n")
        new = ("  constructor(options: HTTPExceptionOptions & { status: ContentfulStatusCode }) {\n"
               "    super(options.message, { cause: options.cause })\n"
               "    this.res = options.res\n"
               "    this.status = options.status\n")
        assert old in raw
        raw = raw.replace(old, new)
        raw = raw.replace("   * @param status - HTTP status code for the exception. Defaults to 500.\n"
                          "   * @param options - Additional options for the exception.\n",
                          "   * @param options - The status code and additional options for the exception.\n")
        write(wt, f, raw)
        n = 0
        for f in ts_files(wt):
            raw = read(wt, f)
            if "HTTPException(" not in raw:
                continue
            m = de.mask(raw, f)
            edits = []
            for c in de.find_calls(raw, m, "HTTPException"):
                if c.arity == 0 or m[c.args[0][0]] == "{":
                    continue
                status = raw[c.args[0][0]:c.args[0][1]]
                if c.arity == 1:
                    rep = "{ status: %s }" % status
                else:
                    a, b = c.args[1]
                    opt = raw[a:b]
                    if opt.startswith("{"):
                        inner = opt[1:]
                        if inner.lstrip().startswith("}"):
                            rep = "{ status: %s }" % status
                        elif inner.startswith("\n"):
                            ind = re.match(r"\n([ \t]*)", inner).group(1)
                            rep = "{\n" + ind + "status: " + status + "," + inner
                        else:
                            rep = "{ status: " + status + "," + (inner if inner.startswith(" ") else " " + inner)
                    else:
                        rep = "{ status: %s, ...%s }" % (status, opt)
                edits.append((c.args[0][0], c.args[-1][1], rep))
            if edits:
                write(wt, f, de.apply_edits(raw, edits))
                n += len(edits)
        print(f"  rewrote {n} calls")
        tsc_until_clean(box, lambda *e: False)
    finally:
        box.close()


# ------------------------------------------------------------------ T3
# zod v4: codec(in_, out, { decode, encode }) -> codec({ input, output, decode, encode })

CODEC_INSTR = (
    "In zod v4 a codec is declared as `z.codec(inputSchema, outputSchema, { decode, encode })`, the only "
    "schema factory that splits its definition between positional schemas and an options object. Change "
    "`codec` to take one required object: `codec({ input, output, decode, encode })`, where `input` and "
    "`output` are the two schemas that used to be the first and second arguments and `decode`/`encode` keep "
    "their signatures and meaning. Make this change to both `codec` functions -- zod classic "
    "(packages/zod/src/v4/classic/schemas.ts) and zod mini (packages/zod/src/v4/mini/schemas.ts) -- with "
    "types that still infer the codec's input and output types from the two schemas. Then update every "
    "`codec(...)` call in the repository's code (library code, the bench package and all tests, including "
    "calls whose third argument is not an object literal) to the new form, passing the same schemas and "
    "functions. Do not keep the three-argument form or an overload for it, and leave unrelated APIs "
    "(`invertCodec`, `ZodCodec`, `$ZodCodec`, `pipe`, `transform`) alone. Behavior must not change and the "
    "tests must pass."
)


@recipe(instance_id="deep__zod__codec_options_object",
        repo="colinhacks/zod", lang="ts", repo_dir=ZOD, base_commit=ZOD_BASE,
        change="signature change (3 positional parameters -> one required options object), classic + mini",
        instruction=CODEC_INSTR,
        decl_files=["packages/zod/src/v4/classic/schemas.ts", "packages/zod/src/v4/mini/schemas.ts"],
        shapes=[{"id": "codec/3", "name": "codec", "arity": 3}],
        gold_tool="build_deep.py recipe (deep_recipes_ts): declarations rewritten by hand-written replacement, "
                  "every `codec(` call with three top-level arguments folded into one object (spread when the "
                  "third argument is not a literal); verified with the repo's tsc (packages/zod/tsconfig.json) "
                  "showing no errors beyond the 15 already present at base",
        notes="zod's own tsc config has 15 type errors at base, so no typecheck_cmd; the arity shape catches "
              "every unconverted call and any kept 3-parameter declaration.")
def make_codec(wt: Path):
    box = TsBox(wt, "colinhacks/zod")
    try:
        _, base_errs, _ = box.tsc()
        baseline = {(e[0], e[3], e[4]) for e in base_errs}
        print(f"  base tsc errors: {len(base_errs)}")
        for f, ret, cls in (("packages/zod/src/v4/classic/schemas.ts", "ZodCodec<A, B>", "ZodCodec"),
                            ("packages/zod/src/v4/mini/schemas.ts", "ZodMiniCodec<A, B>", "ZodMiniCodec")):
            raw = read(wt, f)
            sa = "SomeType" if "mini" in f else "core.SomeType"
            old = (f"export function codec<const A extends {sa}, B extends core.SomeType = core.$ZodType>(\n"
                   "  in_: A,\n  out: B,\n  params: {\n")
            new = (f"export function codec<const A extends {sa}, B extends core.SomeType = core.$ZodType>(params: {{\n"
                   "  input: A;\n  output: B;\n")
            assert old in raw, f
            raw = raw.replace(old, new)
            old2 = ("    encode: (value: core.input<B>, payload: core.ParsePayload<core.input<B>>) => "
                    "core.util.MaybeAsync<core.output<A>>;\n  }\n): " + ret + " {\n")
            new2 = ("  encode: (value: core.input<B>, payload: core.ParsePayload<core.input<B>>) => "
                    "core.util.MaybeAsync<core.output<A>>;\n}): " + ret + " {\n")
            assert old2 in raw, f
            raw = raw.replace(old2, new2)
            raw = raw.replace("    decode: (value: core.output<A>, payload: core.ParsePayload<core.output<A>>) => "
                              "core.util.MaybeAsync<core.input<B>>;\n  encode:",
                              "  decode: (value: core.output<A>, payload: core.ParsePayload<core.output<A>>) => "
                              "core.util.MaybeAsync<core.input<B>>;\n  encode:")
            raw = raw.replace("    in: in_ as any as core.$ZodType,\n    out: out as any as core.$ZodType,\n"
                              "    transform: params.decode as any,",
                              "    in: params.input as any as core.$ZodType,\n    out: params.output as any as core.$ZodType,\n"
                              "    transform: params.decode as any,")
            write(wt, f, raw)
        n = 0
        for f in ts_files(wt):
            raw = read(wt, f)
            if "codec" not in raw:
                continue
            m = de.mask(raw, f)
            edits = []
            for c in de.find_calls(raw, m, "codec"):
                if c.arity != 3 or de.prev_token(m, c.name_start) == "function":
                    continue
                x = raw[c.args[0][0]:c.args[0][1]]
                y = raw[c.args[1][0]:c.args[1][1]]
                a, b = c.args[2]
                p = raw[a:b]
                if p.startswith("{"):
                    inner = p[1:]
                    if inner.startswith("\n"):
                        ind = re.match(r"\n([ \t]*)", inner).group(1)
                        rep = "{\n" + ind + "input: " + x + ",\n" + ind + "output: " + y + "," + inner
                    else:
                        rep = "{ input: " + x + ", output: " + y + "," + (inner if inner.startswith(" ") else " " + inner)
                else:
                    rep = "{ input: %s, output: %s, ...%s }" % (x, y, p)
                edits.append((c.args[0][0], b, rep))
            if edits:
                write(wt, f, de.apply_edits(raw, edits))
                n += len(edits)
        print(f"  rewrote {n} calls")
        tsc_until_clean(box, lambda *e: False, baseline=baseline)
    finally:
        box.close()


# ------------------------------------------------------------------ T4
# h3: move src/event.ts (H3Event, HTTPEvent, kEventRes...) -> src/core/event.ts

import posixpath as _pp

H3_TC = "npx tsc --noEmit -p tsconfig.json"

MOVE_INSTR = (
    "Start an `src/core/` directory for h3's request primitives: move the module `src/event.ts` -- which "
    "defines `H3Event`, `HTTPEvent`, `kEventRes`, `kEventResHeaders` and `kEventResErrHeaders` -- to "
    "`src/core/event.ts`, and delete `src/event.ts` (no re-export shim at the old path). Fix the moved "
    "module's own relative imports, and update every import or re-export of the old module across the "
    "repository -- `src/index.ts`, the router/handler/response modules, the `src/types/` and `src/utils/` "
    "modules (including `src/utils/internal/`) and the tests -- to the correct relative path of the new "
    "location. Note that `src/utils/event.ts` is a different module (`mockEvent`, `getEventContext`, ...): it "
    "stays where it is, and imports of it must not change. The public API exported from `src/index.ts` must "
    "not change, the tests must pass and the project must still type-check (`tsc --noEmit -p tsconfig.json`)."
)


def _spec_targets(f: str, spec: str) -> str | None:
    if not spec.startswith("."):
        return None
    return _pp.normpath(_pp.join(_pp.dirname(f), spec))


def _rel(f: str, target: str) -> str:
    r = _pp.relpath(target, _pp.dirname(f))
    return r if r.startswith(".") else "./" + r


@recipe(instance_id="deep__h3__H3Event_module_move",
        repo="h3js/h3", lang="ts", repo_dir=H3, base_commit=H3_BASE,
        change="move a module (src/event.ts -> src/core/event.ts) and repoint every import",
        instruction=MOVE_INSTR, typecheck_cmd=H3_TC,
        decl_files=["src/core/event.ts"],
        shapes=[
            # any relative specifier ending in event.ts: imports of the look-alike src/utils/event.ts
            # are counted too and cancel against gold
            {"id": "move/old-specifier", "regex": r"[\"'](?:\.{1,2}/)+(?:src/)?event\.ts[\"']", "raw": True},
            {"id": "move/old-class-file", "regex": r"\bclass\s+H3Event\b"},
        ],
        gold_tool="build_deep.py recipe (deep_recipes_ts): file moved, every relative import/export specifier "
                  "that resolves to src/event.ts recomputed for the new path (posix relpath), the moved file's own "
                  "imports re-based; verified with `tsc --noEmit -p tsconfig.json`",
        notes="old-class-file counts `class H3Event` per file, so an H3Event class left at src/event.ts fails; "
              "old-specifier is per file, so look-alike imports of src/utils/event.ts cancel.")
def make_move(wt: Path):
    box = TsBox(wt, "h3js/h3")
    try:
        old, new = "src/event.ts", "src/core/event.ts"
        (wt / "src/core").mkdir(exist_ok=True)
        raw = read(wt, old)
        spec_re = re.compile(r"""((?:from|import)\s*\(?\s*["'])([^"']+)(["'])""")

        def rebase(m):
            t = _spec_targets(old, m.group(2))
            if t is None:
                return m.group(0)
            return m.group(1) + _rel(new, t) + m.group(3)
        write(wt, new, spec_re.sub(rebase, raw))
        (wt / old).unlink()
        n = 0
        for f in ts_files(wt):
            if f == new or not (wt / f).exists():
                continue
            raw = read(wt, f)
            if "event.ts" not in raw:
                continue

            def repoint(m, f=f):
                if _spec_targets(f, m.group(2)) == old:
                    return m.group(1) + _rel(f, new) + m.group(3)
                return m.group(0)
            out = spec_re.sub(repoint, raw)
            if out != raw:
                write(wt, f, out)
                n += 1
        print(f"  repointed imports in {n} files")
        tsc_until_clean(box, lambda *e: False)
        # partial: forget two TYPE-ONLY imports (erased at runtime, so the suite alone passes;
        # the shape and the type check must catch them)
        return {"partial_drop": [("src/utils/cors.ts", None), ("src/utils/internal/event-stream.ts", None)]}
    finally:
        box.close()
