"""High-turn ("deephard") TypeScript recipes for build_deep.py (hono, zod).

Same machinery as deep_recipes_ts.py (TsBox: a node:20 container holding the
checkout plus node_modules; tsc-driven edit loops). These changes are chosen
so one text substitution cannot do them: the right edit at each site depends
on the static type or role of the expression there (a status code vs. an
init object, a params bag vs. an issue object), look-alikes with the same
spelling must stay, and sites hide behind variables, spreads and helpers.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write
import deep_edit as de
import deep_recipes_ts as dt  # registers the deep__ TS recipes + the typecheck_cmd spec hook
from deep_recipes_ts import TsBox, tsc_until_clean, ts_files, HONO, HONO_BASE, ZOD, ZOD_BASE, HONO_TC

import js_eval


def vitest_failures(box: TsBox, repo: str, files: list[str] | None = None) -> list[str]:
    """Run the scorer's own vitest command in the box (source re-synced);
    names of failing tests (file > title)."""
    box.sync()
    cmd = js_eval.TEST_CMD[repo] + (" " + " ".join(files) if files else "")
    subprocess.run(["docker", "exec", "-w", "/w", box.name, "bash", "-c", cmd + " >/tmp/vt.log 2>&1"],
                   capture_output=True, text=True, timeout=3600)
    r = subprocess.run(["docker", "exec", box.name, "cat", "/tmp/vitest.json"], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        tail = subprocess.run(["docker", "exec", box.name, "tail", "-60", "/tmp/vt.log"],
                              capture_output=True, text=True).stdout
        raise RuntimeError("vitest produced no json:\n" + tail)
    print(f"  vitest: {data.get('numPassedTests')}/{data.get('numTotalTests')} passed", flush=True)
    if not data.get("numTotalTests"):
        raise RuntimeError("vitest ran no tests")
    bad = []
    for tf in data.get("testResults", []):
        rel = tf["name"].replace("/w/", "", 1)
        if tf.get("status") == "failed" and not tf.get("assertionResults"):
            bad.append(f"{rel} > <suite failed: {tf.get('message', '')[:300]}>")
        for a in tf.get("assertionResults", []):
            if a.get("status") == "failed":
                bad.append(f"{rel} > {' '.join(a.get('ancestorTitles', []) + [a['title']])}: "
                           f"{(a.get('failureMessages') or [''])[0][:300]}")
    return bad


# ------------------------------------------------------------------ Z1
# zod v4 classic: remove the deprecated v3-compatibility surface

FMT = ["email", "url", "jwt", "emoji", "guid", "uuid", "uuidv4", "uuidv6", "uuidv7", "nanoid", "cuid", "cuid2",
       "ulid", "base64", "base64url", "xid", "ksuid", "ipv4", "ipv6", "cidrv4", "cidrv6", "e164",
       "datetime", "date", "time", "duration"]
ISO = {"datetime", "date", "time", "duration"}
SIMPLE_RENAME = {"safe": "int", "step": "multipleOf", "passthrough": "loose", "removeDefault": "unwrap",
                 "removeCatch": "unwrap"}

ZDEP_INSTR = (
    "Remove zod v4's deprecated Zod-3 compatibility surface from zod classic and core (packages/zod/src/v4), "
    "and migrate every use in packages/zod (library code and the v4 classic, mini and core tests) to the "
    "replacement its deprecation note names. (1) The `message` params key: delete `message` from the shared "
    "`Params` type (core/api.ts) and stop `util.normalizeParams` from reading it, so a schema or check is "
    "customized only through `error`; every params object handed to a schema factory, check or `.refine` that "
    "uses `message: x` (or shorthand `message`) must pass `error: x` instead. `message` keys that are not "
    "params stay as they are: issue objects (`ctx.addIssue({ message })`, `issues.push`, expected issues in "
    "assertions/snapshots) and the `{ message }` objects that error maps return. (2) The format methods of "
    "`ZodString` (`.email()`, `.url()`, `.jwt()`, `.emoji()`, `.guid()`, `.uuid()`, `.uuidv4/6/7()`, "
    "`.nanoid()`, `.cuid()`, `.cuid2()`, `.ulid()`, `.base64()`, `.base64url()`, `.xid()`, `.ksuid()`, "
    "`.ipv4()`, `.ipv6()`, `.cidrv4()`, `.cidrv6()`, `.e164()`, `.datetime()`, `.date()`, `.time()`, "
    "`.duration()`): remove them from the interface and the implementation. Where such a method is called "
    "directly on a bare `z.string()`, the pair becomes the top-level format schema with the same arguments "
    "(`z.string().email(p)` -> `z.email(p)`; `.datetime/.date/.time/.duration` -> `z.iso.datetime(p)` etc.), "
    "keeping the rest of the chain; anywhere else (other checks earlier in the chain, a coerced string, a "
    "schema held in a variable) keep the check in place as `.check(z.email(p))` (`.check(z.iso.date(p))`, "
    "...), which is exactly what the removed method did. (3) `ZodNumber.safe(p)` -> `.int(p)`, "
    "`.step(v, p)` -> `.multipleOf(v, p)`, and drop `.finite()` calls (a no-op); (4) `ZodObject.passthrough()` -> `.loose()`; "
    "(5) `ZodDefault.removeDefault()` and "
    "`ZodCatch.removeCatch()` -> `.unwrap()`; (6) `nativeEnum(...)` -> `enum(...)` in classic and mini "
    "(delete both `nativeEnum` functions). Delete the tests that only check the removed behavior itself "
    "(e.g. that `message` and `error` together throw). Do not change zod v3 (packages/zod/src/v3), other "
    "packages, `ZodNumber.isInt/isFinite`, `ZodObject.merge`, mini's `z.merge` or anything else. Parse "
    "behavior must not change and the tests must pass (a test whose expectation counts internal schema nodes "
    "may be updated to the new structure)."
)


def _ns(raw: str) -> str:
    m = re.search(r"""^import\s+\*\s+as\s+(\w+)\s+from\s+["'](?:zod(?:/v4)?(?:/classic)?|[./]*index\.js|\.\./index\.js)["']""",
                  raw, re.M)
    return m.group(1) if m else "z"


def _chain_start(m: str, dot: int) -> int:
    """Start offset of the receiver expression ending just before m[dot] == '.'."""
    i = dot
    while True:
        j = i - 1
        while j >= 0 and m[j].isspace():
            j -= 1
        if j < 0:
            return i
        if m[j] in ")]":
            d, k = 0, j
            while k >= 0:
                d += m[k] in ")]"
                d -= m[k] in "(["
                if d == 0:
                    break
                k -= 1
            j = k - 1
            while j >= 0 and m[j].isspace():
                j -= 1
            if j >= 0 and m[j] == ">":  # generic call foo<T>(...)
                d, k = 0, j
                while k >= 0:
                    d += m[k] == ">"
                    d -= m[k] == "<"
                    if d == 0:
                        break
                    k -= 1
                j = k - 1
            if j >= 0 and m[j] == "!":
                j -= 1
        if j >= 0 and (m[j].isalnum() or m[j] in "_$"):
            k = j
            while k >= 0 and (m[k].isalnum() or m[k] in "_$"):
                k -= 1
            start = k + 1
        elif m[j] == "!":
            i = j
            continue
        else:
            return j + 1
        k = start - 1
        while k >= 0 and m[k].isspace():
            k -= 1
        if k >= 0 and m[k] == "." or (k >= 1 and m[k - 1:k + 1] == "?."):
            i = k if m[k] == "." else k - 1
            continue
        return start


def rewrite_member(raw: str, f: str, pos: int, ns: str) -> str | None:
    """Rewrite the deprecated member access whose name starts at pos."""
    m = de.mask(raw, f)
    name = re.match(r"[\w$]+", m[pos:]).group(0)
    dot = pos - 1
    while m[dot].isspace():
        dot -= 1
    if m[dot] != ".":
        return None
    q = dot - 1 if m[dot - 1] == "?" else dot
    calls = [c for c in de.find_calls(raw, m, name) if c.name_start == pos]
    if name == "nativeEnum":
        return raw[:pos] + "enum" + raw[pos + len(name):]
    if not calls:
        return None
    c = calls[0]
    args = raw[c.open + 1:c.close]
    if name in SIMPLE_RENAME:
        return raw[:pos] + SIMPLE_RENAME[name] + raw[pos + len(name):]
    if name == "finite":
        # drop `.finite(...)` incl. the line break before the dot when it sits alone on a line
        a = q
        while a > 0 and raw[a - 1] in " \t":
            a -= 1
        if a > 0 and raw[a - 1] == "\n":
            a -= 1
        return raw[:a] + raw[c.close + 1:]
    if name in FMT:
        fac = f"{ns}.iso.{name}" if name in ISO else f"{ns}.{name}"
        start = _chain_start(m, q)
        recv = re.sub(r"\s+", "", m[start:q])
        if recv == f"{ns}.string()":
            return raw[:start] + f"{fac}({args})" + raw[c.close + 1:]
        return raw[:q] + f".check({fac}({args}))" + raw[c.close + 1:]
    return None


def _rename_message_keys(raw: str, f: str, a: int, b: int) -> tuple[str, int]:
    """Rename top-level `message` keys of object literals that are direct
    arguments in raw[a:b] (a call's argument span)."""
    m = de.mask(raw, f)
    edits, stack = [], []
    i = a
    while i < b:
        ch = m[i]
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            stack.pop()
        elif stack == ["(", "{"] and m.startswith("message", i) and not (m[i - 1].isalnum() or m[i - 1] in "_$.") \
                and not (m[i + 7].isalnum() or m[i + 7] in "_$"):
            nxt = de.next_char(m, i + 7)
            prv = de.prev_token(m, i)
            if prv in ("{", ","):
                if nxt == ":":
                    edits.append((i, i + 7, "error"))
                elif nxt in ",}":
                    edits.append((i, i + 7, "error: message"))
        i += 1
    return de.apply_edits(raw, edits), len(edits)


def _drop_test(raw: str, title: str) -> str:
    i = raw.index(f'test("{title}"')
    m = de.mask(raw, "x.ts")
    c = [c for c in de.find_calls(raw, m, "test") if c.name_start == i][0]
    j = c.close + 1
    if raw[j] == ";":
        j += 1
    while raw[j] == "\n" and raw[j + 1:j + 2] == "\n":
        j += 1
    return raw[:i] + raw[j + 1:]


@recipe(instance_id="deephard__zod__remove_deprecated_v3_compat",
        repo="colinhacks/zod", lang="ts", repo_dir=ZOD, base_commit=ZOD_BASE,
        change="remove 6 deprecated API families (params key, 26 ZodString format methods, number/object/default "
               "helpers, nativeEnum); each site's replacement depends on its role and chain shape",
        instruction=ZDEP_INSTR,
        decl_files=["packages/zod/src/v4/core/api.ts", "packages/zod/src/v4/core/util.ts",
                    "packages/zod/src/v4/classic/schemas.ts", "packages/zod/src/v4/mini/schemas.ts"],
        shapes=[
            {"id": "message-key", "regex": r"(?<![\w$.])message\s*:"},
            {"id": "string-format-method", "regex": r"(?<!\bz)(?<!\biso)\.\s*(?:" + "|".join(FMT) + r")\s*\("},
            {"id": "string-format-decl", "regex": r"^\s*(?:" + "|".join(FMT) + r")\(params\??[:)]"},
            {"id": "number-deprecated", "regex": r"\.\s*(?:safe|step|finite)\s*\(|^\s*(?:safe|step|finite)\("},
            {"id": "object-deprecated", "regex": r"\.\s*(?:passthrough|removeDefault|removeCatch)\s*\(|"
                                                 r"^\s*(?:passthrough|removeDefault|removeCatch)\s*\("},
            {"id": "nativeEnum", "name": "nativeEnum"},
        ],
        gold_tool="build_deep.py recipe (deephard_recipes_ts): declarations removed by hand-written edits; every "
                  "use located from the repo's own tsc errors (TS2339/TS2353/TS2769/TS2305 in "
                  "packages/zod/tsconfig.json) and rewritten by role: params `message` -> `error`, format methods "
                  "to z.<fmt>()/z.iso.<fmt>() when called on a bare z.string() else .check(z.<fmt>()), renames, "
                  ".finite() dropped; uses hidden from tsc (`// @ts-ignore`d lines) found by a masked-text scan; iterated to tsc showing only the base errors; "
                  "zod's vitest project green",
        notes="v3 (packages/zod/src/v3) carries the same names with its own semantics and must not change; its "
              "tests are in the green layer. Look-alike shapes (mini z.merge, issue `message` keys, console.time) "
              "are unchanged by gold and cancel in the per-file counts.")
def make_zod_deprecated(wt: Path):
    box = TsBox(wt, "colinhacks/zod")
    try:
        _, base_errs, _ = box.tsc()
        baseline = {(e[0], e[3], e[4]) for e in base_errs}
        print(f"  base tsc errors: {len(base_errs)}")
        # --- declarations
        f = "packages/zod/src/v4/core/api.ts"
        raw = read(wt, f)
        old = ("              error?: string | errors.$ZodErrorMap<IssueTypes> | undefined;\n"
               "              /** @deprecated This parameter is deprecated. Use `error` instead. */\n"
               "              message?: string | undefined; // supported in Zod 3\n")
        assert old in raw
        write(wt, f, raw.replace(old, "              error?: string | errors.$ZodErrorMap<IssueTypes> | undefined;\n"))
        f = "packages/zod/src/v4/core/util.ts"
        raw = read(wt, f)
        old = ("  if (params?.message !== undefined) {\n"
               "    if (params?.error !== undefined) throw new Error(\"Cannot specify both `message` and `error` params\");\n"
               "    params.error = params.message;\n"
               "  }\n"
               "  delete params.message;\n")
        assert old in raw
        write(wt, f, raw.replace(old, ""))
        f = "packages/zod/src/v4/classic/schemas.ts"
        raw = read(wt, f)
        # ZodString interface members (with their jsdoc) and implementation methods
        a = raw.index("export interface ZodString extends _ZodString<core.$ZodStringInternals<string>> {")
        b = raw.index("\n}\n", a)
        raw = raw[:a] + "export interface ZodString extends _ZodString<core.$ZodStringInternals<string>> {}" + raw[b + 2:]
        a = raw.index('export const ZodString: core.$constructor<ZodString> = /*@__PURE__*/ core.$constructor<ZodString>(')
        ia = raw.index("  {\n    email(params) {", a)
        ib = raw.index("\n  }\n);\n", ia)
        raw = raw[:ia].rstrip().rstrip(",") + "\n);\n" + raw[ib + len("\n  }\n);\n"):]
        # ZodNumber
        for pat in (r"  /\*\* @deprecated This is now identical to `\.int\(\)`\.[^\n]*\n  safe\([^\n]*\n",
                    r"  /\*\* @deprecated Use `\.multipleOf\(\)` instead\. \*/\n  step\([^\n]*\n",
                    r"\n  /\*\* @deprecated In v4 and later, z\.number\(\) does not allow infinite[^\n]*\n  finite\([^\n]*\n",
                    r"  /\*\* @deprecated Use `z\.looseObject\(\)` or `\.loose\(\)` instead\. \*/\n  passthrough\(\)[^\n]*\n",
                    r"  /\*\* @deprecated Use `\.unwrap\(\)` instead\. \*/\n  removeDefault\(\): T;\n",
                    r"  /\*\* @deprecated Use `\.unwrap\(\)` instead\. \*/\n  removeCatch\(\): T;\n",
                    r"  inst\.removeDefault = inst\.unwrap;\n", r"  inst\.removeCatch = inst\.unwrap;\n"):
            raw, k = re.subn(pat, "", raw, count=1)
            assert k == 1, pat
        write(wt, f, raw)
        print("  declarations removed (interfaces)")
        n = {"tsc": 0}

        def fix(f, line, col, code, msg):
            if "/src/v3/" in f:
                return False
            raw = read(wt, f)
            pos = bd.line_offset(raw, line, col)
            ns = _ns(raw)
            if code in ("TS2353", "TS2561") and "'message'" in msg:
                if raw[pos:pos + 7] != "message":
                    return False
                rep = "error" if de.next_char(raw, pos + 7) == ":" else "error: message"
                write(wt, f, raw[:pos] + rep + raw[pos + 7:])
                n["tsc"] += 1
                return True
            if code == "TS2769":
                m = de.mask(raw, f)
                name = re.match(r"[\w$]*", m[pos:]).group(0)
                for c in de.find_calls(raw, m, name) if name else []:
                    if c.name_start <= pos <= c.close:
                        new, k = _rename_message_keys(raw, f, c.open, c.close + 1)
                        if k:
                            write(wt, f, new)
                            n["tsc"] += k
                            return True
                return False
            if code in ("TS2339", "TS2551", "TS2305", "TS2724"):
                pm = re.search(r"'(\w+)'", msg)
                if not pm:
                    return False
                name = pm.group(1)
                if name not in FMT and name not in SIMPLE_RENAME and name not in ("finite", "nativeEnum"):
                    return False
                if raw[pos:pos + len(name)] != name:
                    return False
                new = rewrite_member(raw, f, pos, ns)
                if new is None:
                    return False
                write(wt, f, new)
                n["tsc"] += 1
                return True
            return False

        # implementation methods for the removed members of number/object
        for pat in (r"\n    safe\(params\) \{\n(?:      [^\n]*\n)+?    \},",
                    r"\n    step\([^)]*\) \{\n(?:      [^\n]*\n)+?    \},",
                    r"\n    finite\([^)]*\) \{\n(?:      [^\n]*\n)+?    \},",
                    r"\n    passthrough\(\) \{\n(?:      [^\n]*\n)+?    \},"):
            raw = read(wt, "packages/zod/src/v4/classic/schemas.ts")
            new, k = re.subn(pat, "", raw, count=1)
            print(f"  impl {pat[6:20]!r}: {k}")
            write(wt, "packages/zod/src/v4/classic/schemas.ts", new)
        # nativeEnum in classic + mini: the deprecated function and its jsdoc
        for f in ("packages/zod/src/v4/classic/schemas.ts", "packages/zod/src/v4/mini/schemas.ts"):
            raw = read(wt, f)
            mm = re.search(r"/\*\* @deprecated This API has been merged into `z\.enum\(\)`\.(?:(?!\*/).)*\*/\nexport function "
                           r"nativeEnum<(?:(?!\n}\n).)*\n}\n\n?", raw, re.S)
            assert mm, f
            write(wt, f, raw[:mm.start()] + raw[mm.end():])
        # the footprint tests use `email` as their sample ZodString method: use a kept one
        f = "packages/zod/src/v4/classic/tests/instance-footprint.test.ts"
        raw = read(wt, f)
        for o, nw in (("  const email = schema.email;\n  expect(email().safeParse(",
                       "  const toLowerCase = schema.toLowerCase;\n  expect(toLowerCase().safeParse("),
                      ("typeof inst.email)", "typeof inst.toLowerCase)"),
                      ('hasOwnProperty.call(proto, "email")', 'hasOwnProperty.call(proto, "toLowerCase")'),
                      ("typeof plain.email)", "typeof plain.toLowerCase)"),
                      ('new MyString({ type: "string" }).email)', 'new MyString({ type: "string" }).toLowerCase)')):
            assert raw.count(o) == 1, o
            raw = raw.replace(o, nw)
        write(wt, f, raw)
        # the conflict test exercises removed behavior
        f = "packages/zod/src/v4/classic/tests/error.test.ts"
        write(wt, f, _drop_test(read(wt, f), "do not allow error and message together"))
        tsc_until_clean(box, fix, baseline=baseline, rounds=15)
        print(f"  tsc-driven rewrites: {n['tsc']}")
        # uses tsc cannot see (`// @ts-ignore`): a masked-text scan of the v4 tree
        dep = re.compile(r"(?<![\w$])(nativeEnum)\s*\(|\.\s*(" + "|".join(FMT + list(SIMPLE_RENAME) + ["finite"]) + r")\s*\(")
        for f in ts_files(wt):
            if not f.startswith("packages/zod/src/v4/"):
                continue
            while True:
                raw = read(wt, f)
                m = de.mask(raw, f)
                hit = None
                for x in dep.finditer(m):
                    g = 1 if x.group(1) else 2
                    pos = x.start(g)
                    name = x.group(g)
                    pre = m[max(0, pos - 6):pos]
                    if name in FMT and re.search(r"(?<![\w$])(z|iso)\.\s*$", pre):
                        continue
                    line = raw.count("\n", 0, pos) + 1
                    prevline = raw.split("\n")[line - 2] if line > 1 else ""
                    if "@ts-ignore" in prevline or "@ts-expect-error" in prevline or name == "nativeEnum":
                        hit = (pos, name, line)
                        break
                    print(f"    scan look-alike kept: {f}:{line}: {raw.split(chr(10))[line - 1].strip()[:100]}")
                if not hit:
                    break
                new = rewrite_member(raw, f, hit[0], _ns(raw)) if hit[1] != "nativeEnum" or m[hit[0] - 1] == "." else None
                if new is None:
                    raise RuntimeError(f"scan: cannot rewrite {f}:{hit[2]}")
                print(f"    scan rewrite {f}:{hit[2]} {hit[1]}")
                write(wt, f, new)
        f = "packages/zod/src/v4/classic/tests/to-json-schema.test.ts"
        raw = read(wt, f)
        a = raw.index('test("override: do not run on references"')
        b = raw.index("expect(overrideCount).toBe(12);", a)
        if "z.iso.date(), z.iso.datetime(), z.iso.datetime({ local: true })" in raw[a:b]:
            # three fewer schema nodes: the format schemas are no longer wrapped as checks of a ZodString
            raw = raw[:b] + "expect(overrideCount).toBe(9);" + raw[b + len("expect(overrideCount).toBe(12);"):]
            write(wt, f, raw)
        bad = vitest_failures(box, "colinhacks/zod")
        print(f"  vitest failures: {len(bad)}")
        for x in bad[:80]:
            print("   ", x)
        if bad:
            raise RuntimeError(f"{len(bad)} vitest failures")
    finally:
        box.close()


# ------------------------------------------------------------------ H1
# hono: drop the positional-status overloads of c.body/text/json/html/newResponse

RESPONDERS = ("json", "text", "html", "body", "newResponse")

HSTAT_INSTR = (
    "hono's response helpers each accept the status code in two shapes -- a positional number "
    "(`c.json(data, 201, headers)`) or an init object (`c.json(data, { status: 201, headers })`) -- through "
    "paired overloads in `src/context.ts`. Remove the positional-status form from `Context.body`, `Context.text`, "
    "`Context.json`, `Context.html` and `Context.newResponse`: in the `NewResponse`, `BodyRespond`, `TextRespond`, "
    "`JSONRespond` and `HTMLRespond` interfaces keep a single shape per call signature, "
    "`(data, init?: ResponseOrInit<U>, headers?: HeaderRecord)` (the optional third `headers` record keeps its "
    "current meaning and precedence), and make the implementations take `init?: ResponseOrInit` instead of "
    "`StatusCode | ResponseOrInit`. The typed status inference must keep working, so `c.json(x, { status: 201 })` "
    "is still typed as a 201 response for the RPC client. Then update every call in the repository -- "
    "middleware, helpers, adapters, `Context.redirect`, JSX/streaming helpers and all tests -- whose second "
    "argument is a status code (a literal, a variable or parameter holding a status, a conditional, "
    "`res.status`, ...) to pass `{ status: <that expression> }` instead, keeping any third `headers` argument "
    "where it is; calls whose second argument already is an init object or a `Response`, or that pass no "
    "status, stay as they are, and so do the unrelated `Response.json(...)`, `res.json()`/`res.text()` and "
    "`c.redirect(location, status)`. Where a status value may be either a number or an init object, convert "
    "it at that site. Do not keep the numeric overloads or add a compatibility shim. Behavior must not "
    "change, the tests must pass and the project must still type-check (`tsc -p tsconfig.spec.json`)."
)

_BALANCED = r"(?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*?"


@recipe(instance_id="deephard__hono__responders_status_init_only",
        repo="honojs/hono", lang="ts", repo_dir=HONO, base_commit=HONO_BASE,
        change="remove the positional-status overloads of 5 Context response helpers; every call whose second "
               "argument is a status (by type, not spelling) wraps it as { status }, init-object calls stay",
        instruction=HSTAT_INSTR, typecheck_cmd=HONO_TC,
        decl_files=["src/context.ts"],
        shapes=[
            {"id": "responder/numeric-status",
             "regex": r"\.\s*(?:" + "|".join(RESPONDERS) + r")\s*(?:<[^<>()]*>)?\s*\(" + _BALANCED +
                      r",\s*(?:\d{3}|[\w$.]*[sS]tatus(?:Code)?)\s*(?:as\s+[\w$]+\s*)?[,)]"},
            {"id": "responder/positional-decl", "regex": r"^\s*status\?:\s*(?:U|StatusCode|ContentfulStatusCode),?\s*$"},
            {"id": "responder/inline-decl", "regex": r"status\?:\s*StatusCode,\s*headers\?:\s*HeaderRecord"},
        ],
        gold_tool="build_deep.py recipe (deephard_recipes_ts): the five responder interfaces and implementations "
                  "rewritten by hand-written replacement; every call whose second argument tsc rejects "
                  "(TS2345/TS2769/TS2322 at a .json/.text/.html/.body/.newResponse call) wrapped as "
                  "`{ status: <arg> }`, iterated to a clean `tsc -p tsconfig.spec.json`; hono's vitest projects green",
        notes="The numeric-status shape counts calls whose second top-level argument is a 3-digit literal or a "
              "*status/*statusCode name; statuses held in other expressions are guarded by typecheck_cmd.")
def make_hono_status(wt: Path):
    box = TsBox(wt, "honojs/hono")
    try:
        f = "src/context.ts"
        raw = read(wt, f)
        reps = [
            ("  (data: Data | null, status?: StatusCode, headers?: HeaderRecord): Response\n"
             "  (data: Data | null, init?: ResponseOrInit): Response\n",
             "  (data: Data | null, init?: ResponseOrInit, headers?: HeaderRecord): Response\n"),
            ("  <T extends Data, U extends ContentfulStatusCode>(\n    data: T,\n    status?: U,\n    headers?: HeaderRecord\n"
             "  ): Response & TypedResponse<T, U, 'body'>\n"
             "  <T extends Data, U extends ContentfulStatusCode>(\n    data: T,\n    init?: ResponseOrInit<U>\n"
             "  ): Response & TypedResponse<T, U, 'body'>\n"
             "  <T extends null, U extends StatusCode>(\n    data: T,\n    status?: U,\n    headers?: HeaderRecord\n"
             "  ): Response & TypedResponse<null, U, 'body'>\n"
             "  <T extends null, U extends StatusCode>(\n    data: T,\n    init?: ResponseOrInit<U>\n"
             "  ): Response & TypedResponse<null, U, 'body'>\n",
             "  <T extends Data, U extends ContentfulStatusCode>(\n    data: T,\n    init?: ResponseOrInit<U>,\n"
             "    headers?: HeaderRecord\n  ): Response & TypedResponse<T, U, 'body'>\n"
             "  <T extends null, U extends StatusCode>(\n    data: T,\n    init?: ResponseOrInit<U>,\n"
             "    headers?: HeaderRecord\n  ): Response & TypedResponse<null, U, 'body'>\n"),
            (" * @param {U} [status] - An optional status code for the response.\n",
             " * @param {ResponseOrInit<U>} [init] - An optional response init (status, headers, statusText) or Response.\n"),
            ("  <T extends string, U extends ContentfulStatusCode = ContentfulStatusCode>(\n    text: T,\n    status?: U,\n"
             "    headers?: HeaderRecord\n  ): Response & TypedResponse<T, U, 'text'>\n"
             "  <T extends string, U extends ContentfulStatusCode = ContentfulStatusCode>(\n    text: T,\n"
             "    init?: ResponseOrInit<U>\n  ): Response & TypedResponse<T, U, 'text'>\n",
             "  <T extends string, U extends ContentfulStatusCode = ContentfulStatusCode>(\n    text: T,\n"
             "    init?: ResponseOrInit<U>,\n    headers?: HeaderRecord\n  ): Response & TypedResponse<T, U, 'text'>\n"),
            ("  >(\n    object: T,\n    status?: U,\n    headers?: HeaderRecord\n  ): JSONRespondReturn<T, U>\n"
             "  <\n    T extends JSONValue | {} | InvalidJSONValue,\n    U extends ContentfulStatusCode = ContentfulStatusCode,\n"
             "  >(\n    object: T,\n    init?: ResponseOrInit<U>\n  ): JSONRespondReturn<T, U>\n",
             "  >(\n    object: T,\n    init?: ResponseOrInit<U>,\n    headers?: HeaderRecord\n  ): JSONRespondReturn<T, U>\n"),
            (" * @param status - (Optional) The HTTP status code for the response.\n", ""),
            ("  <T extends string | Promise<string>>(\n    html: T,\n    status?: ContentfulStatusCode,\n"
             "    headers?: HeaderRecord\n  ): T extends string ? Response : Promise<Response>\n"
             "  <T extends string | Promise<string>>(\n    html: T,\n    init?: ResponseOrInit<ContentfulStatusCode>\n"
             "  ): T extends string ? Response : Promise<Response>\n",
             "  <T extends string | Promise<string>>(\n    html: T,\n    init?: ResponseOrInit<ContentfulStatusCode>,\n"
             "    headers?: HeaderRecord\n  ): T extends string ? Response : Promise<Response>\n"),
            ("    data: Data | null,\n    arg?: StatusCode | RequestInit,\n    headers?: HeaderRecord\n"
             "  ): ReturnType<BodyRespond> => this.#newResponse(data, arg, headers) as ReturnType<BodyRespond>",
             "    data: Data | null,\n    init?: ResponseOrInit,\n    headers?: HeaderRecord\n"
             "  ): ReturnType<BodyRespond> => this.#newResponse(data, init, headers) as ReturnType<BodyRespond>"),
            ("  text: TextRespond = (\n    text: string,\n    arg?: ContentfulStatusCode | ResponseOrInit,\n    headers?: HeaderRecord\n"
             "  ): ReturnType<TextRespond> => {\n    return !this.#preparedHeaders && !this.#status && !arg && !headers",
             "  text: TextRespond = <T extends string, U extends ContentfulStatusCode = ContentfulStatusCode>(\n"
             "    text: T,\n    init?: ResponseOrInit<U>,\n    headers?: HeaderRecord\n"
             "  ): Response & TypedResponse<T, U, 'text'> => {\n"
             "    return !this.#preparedHeaders && !this.#status && !init && !headers"),
            ("      ? (new Response(text) as ReturnType<TextRespond>)\n",
             "      ? (new Response(text) as Response & TypedResponse<T, U, 'text'>)\n"),
            ("          setDefaultContentType(TEXT_PLAIN, headers)\n        ) as ReturnType<TextRespond>)\n",
             "          setDefaultContentType(TEXT_PLAIN, headers)\n        ) as Response & TypedResponse<T, U, 'text'>)\n"),
            ("      : (this.#newResponse(\n          text,\n          arg,\n",
             "      : (this.#newResponse(\n          text,\n          init,\n"),
            ("    object: T,\n    arg?: U | ResponseOrInit<U>,\n    headers?: HeaderRecord\n  ): JSONRespondReturn<T, U> => {\n"
             "    return this.#newResponse(\n      JSON.stringify(object),\n      arg,\n",
             "    object: T,\n    init?: ResponseOrInit<U>,\n    headers?: HeaderRecord\n  ): JSONRespondReturn<T, U> => {\n"
             "    return this.#newResponse(\n      JSON.stringify(object),\n      init,\n"),
            ("  html: HTMLRespond = (\n    html: string | Promise<string>,\n    arg?: ContentfulStatusCode | ResponseOrInit<ContentfulStatusCode>,\n"
             "    headers?: HeaderRecord\n  ): Response | Promise<Response> => {\n    const res = (html: string) =>\n"
             "      this.#newResponse(html, arg, ",
             "  html: HTMLRespond = <T extends string | Promise<string>>(\n    html: T,\n"
             "    init?: ResponseOrInit<ContentfulStatusCode>,\n"
             "    headers?: HeaderRecord\n  ): T extends string ? Response : Promise<Response> => {\n"
             "    const res = (html: string) =>\n"
             "      this.#newResponse(html, init, "),
            ("    return typeof html === 'object'\n      ? resolveCallback(html, HtmlEscapedCallbackPhase.Stringify, false, {}).then(res)\n"
             "      : res(html)\n",
             "    return (\n      typeof html === 'object'\n"
             "        ? resolveCallback(html, HtmlEscapedCallbackPhase.Stringify, false, {}).then(res)\n"
             "        : res(html)\n    ) as T extends string ? Response : Promise<Response>\n"),
        ]
        for o, nw in reps:
            k = raw.count(o)
            assert k >= 1, o[:120]
            raw = raw.replace(o, nw)
        write(wt, f, raw)
        n = {"wrap": 0}

        def fix(f, line, col, code, msg):
            if code not in ("TS2345", "TS2769", "TS2322", "TS2559"):
                return False
            raw = read(wt, f)
            pos = bd.line_offset(raw, line, col)
            m = de.mask(raw, f)
            best = None
            for name in RESPONDERS:
                for c in de.find_calls(raw, m, name):
                    if m[c.name_start - 1] != "." and not re.search(r"\.\s*$", m[:c.name_start]):
                        continue
                    if c.arity >= 2 and c.name_start <= pos <= c.close and (best is None or c.name_start > best.name_start):
                        best = c
            if best is None:
                return False
            a, b = best.args[1]
            arg = raw[a:b]
            if arg.startswith("{") or arg == "undefined":
                return False
            write(wt, f, raw[:a] + "{ status: " + arg + " }" + raw[b:])
            n["wrap"] += 1
            return True

        tsc_until_clean(box, fix, rounds=15)
        print(f"  wrapped {n['wrap']} status arguments")
        bad = vitest_failures(box, "honojs/hono")
        print(f"  vitest failures: {len(bad)}")
        for x in bad[:60]:
            print("   ", x)
        if bad:
            raise RuntimeError(f"{len(bad)} vitest failures")
    finally:
        box.close()


# ------------------------------------------------------------------ H2
# hono: app.request(input, requestInit?, Env?, executionCtx?) -> app.request(input, { init?, env?, executionCtx? })

HREQ_INSTR = (
    "`Hono.request(input, requestInit?, Env?, executionCtx?)` (src/hono-base.ts), the in-process request helper "
    "used throughout the tests, takes three optional positional arguments, so a test that only needs bindings "
    "has to write `app.request('/x', undefined, env)`. Replace them with one optional options object: "
    "`request(input: Request | string | URL, options?: { init?: RequestInit; env?: E['Bindings'] | {}; "
    "executionCtx?: ExecutionContext })`, where `init`, `env` and `executionCtx` mean exactly what the second, "
    "third and fourth arguments meant. Then update every call of `Hono.request` in the repository -- library "
    "code (e.g. the SSG helper), every test, and calls on any `Hono` instance whatever its variable is called "
    "(sub-apps, routes, `new Hono()` inline, apps returned by helpers) -- to the new form: "
    "`app.request(url, init)` -> `app.request(url, { init })` (with the same expression for `init`, whether "
    "it is an object literal, a variable or a call), `app.request(url, undefined, env)` -> "
    "`app.request(url, { env })`, `app.request(url, init, env, ctx)` -> `app.request(url, { init, env, "
    "executionCtx: ctx })`, omitting arguments that were `undefined` placeholders; one-argument calls stay. "
    "The RPC client's `fetch` option must stay fetch-shaped: change `HonoRequest` in src/client/types.ts "
    "(today `typeof Hono.prototype['request']`) to `(input: RequestInfo | URL, requestInit?: RequestInit) => "
    "Response | Promise<Response>`, and wherever `app.request` itself is handed over as a fetch function "
    "(`hc(url, { fetch: app.request })` and similar) pass `(input, init) => app.request(input, { init })` "
    "instead. Do not touch other `request` functions or methods (e.g. `fetch`, `Request`, `c.req`). "
    "Do not keep the positional form or an overload for it. Behavior must not change, the tests must pass "
    "and the project must still type-check (`tsc -p tsconfig.spec.json`)."
)

_FIRST_ARG = r"(?:[^(),]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))+"


def _shorthand(key: str, expr: str) -> str:
    return key if expr == key else f"{key}: {expr}"


@recipe(instance_id="deephard__hono__request_options_object",
        repo="honojs/hono", lang="ts", repo_dir=HONO, base_commit=HONO_BASE,
        change="signature change (3 optional positional params -> one options object) of the in-process "
               "request helper; ~300 calls on differently named Hono instances, placeholders dropped",
        instruction=HREQ_INSTR, typecheck_cmd=HONO_TC,
        decl_files=["src/hono-base.ts"],
        shapes=[
            {"id": "request/3", "name": "request", "arity": 3},
            {"id": "request/4", "name": "request", "arity": 4},
            {"id": "request/2-positional",
             "regex": r"\.\s*request\s*\(\s*" + _FIRST_ARG + r",\s*(?!\{\s*(?:init|env|executionCtx)\b)(?!undefined\s*\))[^\s)]"},
            {"id": "request/positional-decl", "regex": r"\brequestInit\?:\s*RequestInit,"},
            {"id": "request/as-fetch", "regex": r"\bfetch\s*:\s*[\w$.]+\.request\b(?!\s*\()"},
            {"id": "request/HonoRequest-alias", "regex": r"\btypeof\s+Hono\.prototype\s*\)\s*\["},
        ],
        gold_tool="build_deep.py recipe (deephard_recipes_ts): declaration rewritten by hand; every `.request(` "
                  "call tsc rejects (TS2554/TS2353/TS2559/TS2345 inside it) rebuilt as `{ init, env, executionCtx }` "
                  "with `undefined` placeholders dropped, iterated to a clean `tsc -p tsconfig.spec.json`; hono's "
                  "vitest projects green; the client's HonoRequest type made fetch-shaped and `fetch: app.request` "
                  "uses (which still compiled against the old alias but would mis-handle init at runtime) wrapped",
        notes="request/2-positional counts two-argument .request( calls whose second argument is not a new-form "
              "options literal; look-alike .request( calls on other objects are unchanged by gold and cancel.")
def make_hono_request(wt: Path):
    box = TsBox(wt, "honojs/hono")
    try:
        f = "src/hono-base.ts"
        raw = read(wt, f)
        old = ("  request = (\n    input: Request | string | URL,\n    requestInit?: RequestInit,\n"
               "    Env?: E['Bindings'] | {},\n    executionCtx?: ExecutionContext\n"
               "  ): Response | Promise<Response> => {\n    if (input instanceof Request) {\n"
               "      return this.fetch(requestInit ? new Request(input, requestInit) : input, Env, executionCtx)\n"
               "    }\n    input = input.toString()\n    return this.fetch(\n      new Request(\n"
               "        /^https?:\\/\\//.test(input) ? input : `http://localhost${mergePath('/', input)}`,\n"
               "        requestInit\n      ),\n      Env,\n      executionCtx\n    )\n  }\n")
        new = ("  request = (\n    input: Request | string | URL,\n    options?: {\n      init?: RequestInit\n"
               "      env?: E['Bindings'] | {}\n      executionCtx?: ExecutionContext\n    }\n"
               "  ): Response | Promise<Response> => {\n    const { init, env, executionCtx } = options ?? {}\n"
               "    if (input instanceof Request) {\n"
               "      return this.fetch(init ? new Request(input, init) : input, env, executionCtx)\n"
               "    }\n    input = input.toString()\n    return this.fetch(\n      new Request(\n"
               "        /^https?:\\/\\//.test(input) ? input : `http://localhost${mergePath('/', input)}`,\n"
               "        init\n      ),\n      env,\n      executionCtx\n    )\n  }\n")
        assert old in raw
        write(wt, f, raw.replace(old, new))
        # the RPC client's `fetch` option typed itself as app.request; keep it fetch-shaped
        f = "src/client/types.ts"
        raw = read(wt, f)
        old = "type HonoRequest = (typeof Hono.prototype)['request']\n"
        assert old in raw
        write(wt, f, raw.replace(old, "type HonoRequest = (\n  input: RequestInfo | URL,\n  requestInit?: RequestInit\n"
                                      ") => globalThis.Response | Promise<globalThis.Response>\n"))
        n = {"calls": 0, "fetch": 0}

        def fix(f, line, col, code, msg):
            if code not in ("TS2554", "TS2353", "TS2559", "TS2345", "TS2769", "TS2322"):
                return False
            raw = read(wt, f)
            pos = bd.line_offset(raw, line, col)
            m = de.mask(raw, f)
            fm = re.compile(r"fetch\s*:\s*([\w$.]+)\.request\b(?!\s*\()").match(m, pos)
            if code == "TS2322" and fm:
                recv = raw[fm.start(1):fm.end(1)]
                write(wt, f, raw[:fm.start(1)] + f"(input, init) => {recv}.request(input, {{ init }})"
                      + raw[fm.end():])
                n["fetch"] += 1
                return True
            if code == "TS2322":
                return False
            best = None
            for c in de.find_calls(raw, m, "request"):
                if not re.search(r"\.\s*$", m[:c.name_start]) or c.arity < 2:
                    continue
                if c.name_start <= pos <= c.close and (best is None or c.name_start > best.name_start):
                    best = c
            if best is None:
                return False
            args = [raw[a:b] for a, b in best.args]
            if len(args) == 2 and re.match(r"\{\s*(init|env|executionCtx)\b", args[1]):
                return False
            parts = [_shorthand(k, v) for k, v in zip(("init", "env", "executionCtx"), args[1:]) if v != "undefined"]
            if any("..." in p for p in parts):
                return False
            rep = ("{ " + ", ".join(parts) + " }") if parts else ""
            a = best.args[0][1]
            write(wt, f, raw[:a] + (", " + rep if rep else "") + raw[best.args[-1][1]:])
            n["calls"] += 1
            return True

        tsc_until_clean(box, fix, rounds=15)
        print(f"  rewrote {n['calls']} calls, {n['fetch']} app.request-as-fetch uses")
        bad = vitest_failures(box, "honojs/hono")
        print(f"  vitest failures: {len(bad)}")
        for x in bad[:60]:
            print("   ", x)
        if bad:
            raise RuntimeError(f"{len(bad)} vitest failures")
    finally:
        box.close()
