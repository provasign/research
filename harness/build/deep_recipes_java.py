"""Java recipes for build_deep.py (jackson-databind, commons-lang, gson ...)."""
from __future__ import annotations

import re
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write, java_compile, ensure_java_import
import deep_edit as de

DATABIND = bd.CORPUS / "jackson-databind"
DATABIND_BASE = "25b2a221f9aa4107e455065a74635e209418cf55"


def java_files(wt: Path) -> list[str]:
    return de.code_files(wt, (".java",))


def compile_until_clean(wt: Path, fix_error, rounds: int = 8, ignore=lambda e: False) -> None:
    """Compile; hand every error to fix_error(file, line, col, msg) -> bool
    (True = handled). Stop when clean; raise when an error is unhandled or
    a round makes no progress."""
    last = None
    for i in range(rounds):
        ok, errs, tail = java_compile(wt)
        errs = [e for e in errs if not ignore(e)]
        print(f"  compile round {i}: ok={ok} errors={len(errs)}", flush=True)
        if ok or (not errs and ignore is not None and "module not found" in tail):
            return
        if not errs:
            raise RuntimeError("build failed without parsable errors:\n" + tail)
        key = sorted(errs)
        if key == last:
            raise RuntimeError("no progress:\n" + "\n".join(map(str, errs[:20])))
        last = key
        # bottom-up per file so earlier offsets stay valid
        unhandled = []
        for e in sorted(errs, key=lambda e: (e[0], -e[1], -e[2])):
            if not fix_error(*e):
                unhandled.append(e)
        if unhandled and len(unhandled) == len(errs):
            raise RuntimeError("unhandled errors:\n" + "\n".join(map(str, unhandled[:30])))
    raise RuntimeError("did not converge")


# ------------------------------------------------------------------ J1
# JsonFormatVisitable.acceptJsonFormatVisitor(visitor, typeHint)
#   -> acceptJsonFormatVisitor(visitor, typeHint, SerializerProvider provider)

SP = "com.fasterxml.jackson.databind.SerializerProvider"

AJFV_INSTR = (
    "Format visitors currently fetch the active `SerializerProvider` back out of the visitor "
    "(`visitor.getProvider()`), which is null for visitors built without one. Make it explicit: add a "
    "third, required parameter `SerializerProvider provider` to "
    "`JsonFormatVisitable.acceptJsonFormatVisitor(JsonFormatVisitorWrapper visitor, JavaType typeHint)` "
    "(com.fasterxml.jackson.databind.jsonFormatVisitors), so the method becomes "
    "`acceptJsonFormatVisitor(JsonFormatVisitorWrapper visitor, JavaType typeHint, SerializerProvider provider)`. "
    "This changes `JsonSerializer.acceptJsonFormatVisitor` and every serializer (and every other "
    "`JsonFormatVisitable`) that overrides it, in main and test code. Update every call of this method "
    "to pass the provider in effect at the call site: inside an `acceptJsonFormatVisitor` implementation "
    "pass its own `provider` parameter on; where some other `SerializerProvider` is in scope (a method "
    "parameter, or `this` inside a provider) pass that; otherwise pass `visitor.getProvider()` for the "
    "visitor being handed over. Do not keep a two-argument overload or a default. Do not change the "
    "unrelated `acceptJsonFormatVisitor(JavaType/Class<?> type, JsonFormatVisitorWrapper visitor)` methods "
    "of `ObjectMapper`, `ObjectWriter` and `DefaultSerializerProvider` (their parameter order is reversed). "
    "Implementations do not have to use the new parameter yet; behavior must not change."
)


@recipe(instance_id="deep__jackson-databind__acceptJsonFormatVisitor_add_provider",
        repo="FasterXML/jackson-databind", lang="java", repo_dir=DATABIND, base_commit=DATABIND_BASE,
        change="add required parameter (interface method, ~45 overrides + callers)",
        instruction=AJFV_INSTR,
        decl_files=["src/main/java/com/fasterxml/jackson/databind/jsonFormatVisitors/JsonFormatVisitable.java",
                    "src/main/java/com/fasterxml/jackson/databind/JsonSerializer.java"],
        shapes=[{"id": "ajfv/2", "name": "acceptJsonFormatVisitor", "arity": 2}],
        gold_tool="build_deep.py recipe: declarations by pattern (first parameter JsonFormatVisitorWrapper), "
                  "call sites from javac's own errors in docker maven test-compile, iterated to a clean build",
        notes="Look-alikes with the same name and arity: ObjectMapper/ObjectWriter/DefaultSerializerProvider "
              "acceptJsonFormatVisitor(type, visitor); unchanged by gold, so they cancel in the shape counts.")
def make_ajfv(wt: Path):
    name = "acceptJsonFormatVisitor"
    ndecl = 0
    for f in java_files(wt):
        raw = read(wt, f)
        if name not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, name):
            first = raw[c.args[0][0]:c.args[0][1]] if c.args else ""
            if de.prev_token(m, c.name_start) == "void" and c.arity == 2 and \
                    re.match(r"(final\s+)?JsonFormatVisitorWrapper\b", first):
                edits.append(de.insert_arg(raw, c, 2, "SerializerProvider provider"))
        if edits:
            raw = de.apply_edits(raw, edits)
            raw = ensure_java_import(raw, SP)
            write(wt, f, raw)
            ndecl += len(edits)
    print(f"  declarations: {ndecl}")

    def fix(f, line, col, msg):
        if "cannot be applied to given types" in msg or "no suitable method found for acceptJsonFormatVisitor" in msg \
                or ("acceptJsonFormatVisitor" in msg and "cannot be applied" in msg):
            cs = [c for c in bd.calls_near(wt, f, name, line) if c.arity == 2]
            if not cs:
                return False
            raw = read(wt, f)
            m = de.mask(raw, f)
            c = cs[0]
            params = bd.enclosing_java_params(raw, m, c.name_start)
            pm = re.search(r"\bSerializerProvider\s+(\w+)", params)
            first = raw[c.args[0][0]:c.args[0][1]]
            loc = re.findall(r"\bSerializerProvider\s+(\w+)\s*=", m[max(0, c.name_start - 1500):c.name_start])
            if pm:
                val = pm.group(1)
            elif loc:
                val = loc[-1]
            elif re.search(r"class\s+\w+\s+extends\s+(Default)?SerializerProvider", raw) and \
                    "SerializerProvider" in f:
                val = "this"
            elif re.fullmatch(r"[\w.]+", first):
                val = f"{first}.getProvider()"
            else:
                return False
            write(wt, f, de.apply_edits(raw, [de.insert_arg(raw, c, 2, val)]))
            return True
        if "is already defined in method acceptJsonFormatVisitor" in msg:
            raw = read(wt, f)
            off = bd.line_offset(raw, line)
            eol = raw.index("\n", off)
            ln = raw[off:eol]
            mm = re.match(r"\s*(?:final\s+)?SerializerProvider\s+provider\s*=\s*visitor\.getProvider\(\);\s*$", ln)
            if not mm:
                return False
            write(wt, f, raw[:off] + raw[eol + 1:])
            return True
        return False

    compile_until_clean(wt, fix)


# ------------------------------------------------------------------ J2
# JsonDeserializer.supportsUpdate(DeserializationConfig): Boolean -> OptBoolean

OPTB = "com.fasterxml.jackson.annotation.OptBoolean"

SU_INSTR = (
    "`JsonDeserializer.supportsUpdate(DeserializationConfig config)` (com.fasterxml.jackson.databind) "
    "returns a tri-state `java.lang.Boolean` where `null` means \"unknown\"; callers have to remember the "
    "null case (`ReferenceTypeDeserializer.deserialize(p, ctxt, reference)` calls `.equals` on it). "
    "Change its return type to `com.fasterxml.jackson.annotation.OptBoolean`: `Boolean.TRUE` becomes "
    "`OptBoolean.TRUE`, `Boolean.FALSE` becomes `OptBoolean.FALSE`, and `null` (unknown) becomes "
    "`OptBoolean.DEFAULT`. The base declaration in `JsonDeserializer` and every deserializer that overrides "
    "it must return `OptBoolean` (implementations that forward to another deserializer keep forwarding; "
    "implementations that return a stored `Boolean` must convert it, e.g. with `OptBoolean.fromBoolean`). "
    "Update every caller of `supportsUpdate` to work with the `OptBoolean` result, treating `DEFAULT` the way "
    "it treated `null`. Leave fields and constructor parameters that hold a `Boolean` (such as "
    "`JsonNodeDeserializer`'s `_supportsUpdates`) as they are. Do not keep a `Boolean`-returning variant. "
    "Behavior must not change."
)


@recipe(instance_id="deep__jackson-databind__supportsUpdate_OptBoolean",
        repo="FasterXML/jackson-databind", lang="java", repo_dir=DATABIND, base_commit=DATABIND_BASE,
        change="change return type (Boolean -> OptBoolean) of an overridden method + adapt callers",
        instruction=SU_INSTR,
        decl_files=["src/main/java/com/fasterxml/jackson/databind/JsonDeserializer.java"],
        shapes=[{"id": "Boolean supportsUpdate", "regex": r"\bBoolean\s+supportsUpdate\s*\("},
                {"id": "Boolean = supportsUpdate", "regex": r"\bBoolean\s+\w+\s*=\s*[\w.()]*supportsUpdate\s*\("}],
        gold_tool="build_deep.py recipe: return types and return statements of every supportsUpdate override "
                  "rewritten by pattern; the two value-using callers rewritten; docker maven test-compile clean")
def make_supports_update(wt: Path):
    n = 0
    for f in java_files(wt):
        raw = read(wt, f)
        if "supportsUpdate" not in raw:
            continue
        orig = raw
        m = de.mask(raw, f)
        edits = []
        for dm in re.finditer(r"\bBoolean(\s+supportsUpdate\s*\(\s*DeserializationConfig\s+\w+\s*\)\s*\{)", m):
            edits.append((dm.start(), dm.start() + len("Boolean"), "OptBoolean"))
            # method body: up to the matching close brace
            i, depth = dm.end(), 1
            while depth:
                depth += m[i] == "{"
                depth -= m[i] == "}"
                i += 1
            body_a, body_b = dm.end(), i - 1
            for rm in re.finditer(r"\breturn\s+([^;]+);", m[body_a:body_b]):
                a, b = body_a + rm.start(1), body_a + rm.end(1)
                expr = raw[a:b]
                rep = {"Boolean.TRUE": "OptBoolean.TRUE", "Boolean.FALSE": "OptBoolean.FALSE",
                       "null": "OptBoolean.DEFAULT", "_supportsUpdates": "OptBoolean.fromBoolean(_supportsUpdates)"}
                if expr in rep:
                    edits.append((a, b, rep[expr]))
                elif re.fullmatch(r"\(_valueDeserializer == null\) \? null\s+: _valueDeserializer\.supportsUpdate\(config\)", expr):
                    edits.append((a, b, expr.replace("? null", "? OptBoolean.DEFAULT")))
                elif re.fullmatch(r"[\w.()!= ]+\?\s*(Boolean\.TRUE|Boolean\.FALSE|null)\s*:\s*(Boolean\.TRUE|Boolean\.FALSE|null)", expr):
                    cond, rest = expr.split("?", 1)
                    rest = re.sub(r"Boolean\.(TRUE|FALSE)", r"OptBoolean.\1", rest)
                    rest = re.sub(r"\bnull\b", "OptBoolean.DEFAULT", rest)
                    edits.append((a, b, cond + "?" + rest))
                elif re.fullmatch(r"[\w.]+\.supportsUpdate\(\w+\)", expr):
                    pass  # forwarding: type follows
                else:
                    raise RuntimeError(f"unhandled return in {f}: {expr}")
            n += 1
        if edits:
            raw = de.apply_edits(raw, edits)
            raw = ensure_java_import(raw, OPTB)
        # callers that use the value
        raw = raw.replace(
            "            Boolean mayMerge = valueDeser.supportsUpdate(ctxt.getConfig());\n\n"
            "            if (mayMerge == null) {",
            "            OptBoolean mayMerge = valueDeser.supportsUpdate(ctxt.getConfig());\n\n"
            "            if (mayMerge == OptBoolean.DEFAULT) {")
        raw = raw.replace("} else if (!mayMerge.booleanValue()) { // prevented",
                          "} else if (mayMerge == OptBoolean.FALSE) { // prevented")
        raw = raw.replace(
            "        Boolean B = _valueDeserializer.supportsUpdate(ctxt.getConfig());\n"
            "        // if explicitly stated that merge won't work...\n"
            "        if (B.equals(Boolean.FALSE) ||  (_valueTypeDeserializer != null)) {",
            "        OptBoolean B = _valueDeserializer.supportsUpdate(ctxt.getConfig());\n"
            "        // if explicitly stated that merge won't work...\n"
            "        if ((B == OptBoolean.FALSE) ||  (_valueTypeDeserializer != null)) {")
        if raw != orig:
            if "OptBoolean" in raw:
                raw = ensure_java_import(raw, OPTB)
            write(wt, f, raw)
    print(f"  overrides rewritten: {n}")
    ok, errs, tail = java_compile(wt)
    if not ok:
        raise RuntimeError("gold does not compile:\n" + "\n".join(map(str, errs[:30])) + tail[-1500:])


# ------------------------------------------------------------------ J3
# move com.fasterxml.jackson.databind.util.NameTransformer -> ...databind.introspect

NT_OLD, NT_NEW = "com.fasterxml.jackson.databind.util.NameTransformer", \
    "com.fasterxml.jackson.databind.introspect.NameTransformer"

NT_INSTR = (
    "`NameTransformer` (property-name transformation used by `@JsonUnwrapped`) lives in the grab-bag "
    "`com.fasterxml.jackson.databind.util` package, although it belongs with the other property "
    "introspection types. Move the class `com.fasterxml.jackson.databind.util.NameTransformer` "
    "(including its nested classes) to the package `com.fasterxml.jackson.databind.introspect`, i.e. to "
    "`src/main/java/com/fasterxml/jackson/databind/introspect/NameTransformer.java`, and delete it from "
    "`util` completely: no deprecated subclass, alias or forwarding copy may remain in the old package. "
    "Update every reference in main and test code so the project compiles: explicit imports, "
    "fully-qualified references, classes that relied on being in the same package or on a "
    "`com.fasterxml.jackson.databind.util.*` wildcard import, and imports that become redundant because "
    "the user is now in the same package as the class. Keep every test class in its current package. "
    "Do not rename anything; behavior must not change."
)


@recipe(instance_id="deep__jackson-databind__NameTransformer_move_package",
        repo="FasterXML/jackson-databind", lang="java", repo_dir=DATABIND, base_commit=DATABIND_BASE,
        change="move a widely used type to another package (old location removed)",
        instruction=NT_INSTR,
        decl_files=["src/main/java/com/fasterxml/jackson/databind/introspect/NameTransformer.java",
                    "src/main/java/com/fasterxml/jackson/databind/util/NameTransformer.java"],
        shapes=[{"id": "old FQN", "regex": r"\bcom\.fasterxml\.jackson\.databind\.util\.NameTransformer\b"},
                {"id": "class decl", "regex": r"\bclass\s+NameTransformer\b"}],
        gold_tool="build_deep.py recipe: git mv + package line; imports/FQNs rewritten by pattern; same-package "
                  "and util.* wildcard users given an explicit import; docker maven test-compile clean")
def make_nt_move(wt: Path):
    old_p = "src/main/java/com/fasterxml/jackson/databind/util/NameTransformer.java"
    new_p = "src/main/java/com/fasterxml/jackson/databind/introspect/NameTransformer.java"
    de.git("-C", str(wt), "mv", old_p, new_p)
    src = read(wt, new_p).replace("package com.fasterxml.jackson.databind.util;",
                                  "package com.fasterxml.jackson.databind.introspect;", 1)
    write(wt, new_p, src)
    n = 0
    for f in java_files(wt):
        if not f.startswith("src/"):
            continue
        raw = read(wt, f)
        if "NameTransformer" not in raw:
            continue
        orig = raw
        pkg = (re.search(r"^package\s+([\w.]+);", raw, re.M) or [None, ""])[1]
        in_introspect = pkg == "com.fasterxml.jackson.databind.introspect"
        if in_introspect:
            raw = re.sub(rf"^import\s+{re.escape(NT_OLD)};\n", "", raw, flags=re.M)
        else:
            raw = re.sub(rf"^import\s+{re.escape(NT_OLD)};", f"import {NT_NEW};", raw, flags=re.M)
        m = de.mask(raw, f)
        # fully qualified uses in code (not imports, not comments)
        edits = [(x.start(), x.end(), NT_NEW) for x in re.finditer(re.escape(NT_OLD), m)
                 if not m[max(0, x.start() - 7):x.start()].startswith("import")]
        raw = de.apply_edits(raw, edits)
        m = de.mask(raw, f)
        uses_simple = re.search(r"(?<![\w.])NameTransformer\b", m)
        if uses_simple and not in_introspect and f != new_p and \
                not re.search(rf"^import\s+{re.escape(NT_NEW)};", raw, re.M) and \
                not re.search(r"^import\s+com\.fasterxml\.jackson\.databind\.introspect\.\*;", raw, re.M):
            if pkg == "com.fasterxml.jackson.databind.util" or \
                    re.search(r"^import\s+com\.fasterxml\.jackson\.databind\.util\.\*;", raw, re.M):
                raw = ensure_java_import(raw, NT_NEW)
        if raw != orig:
            write(wt, f, raw)
            n += 1
    print(f"  files rewritten: {n}")
    ok, errs, tail = java_compile(wt)
    if not ok:
        raise RuntimeError("gold does not compile:\n" + "\n".join(map(str, errs[:30])) + tail[-1500:])
    return {"partial_drop": [
        ("src/test/java/com/fasterxml/jackson/databind/util/NameTransformerTest.java", None),
        ("src/main/java/com/fasterxml/jackson/databind/ser/impl/UnwrappingBeanPropertyWriter.java", None)]}


# ------------------------------------------------------------------ J4
# gson TypeAdapterFactory.create(Gson, TypeToken<T>): TypeAdapter<T> (null = "not mine")
#   -> Optional<TypeAdapter<T>>

GSON = bd.CORPUS / "gson"
GSON_BASE = "dae37cf0fe12235b76fb09f01118a0a8c8823f42"

TAF_INSTR = (
    "`TypeAdapterFactory.create(Gson gson, TypeToken<T> type)` (com.google.gson) signals \"this factory "
    "does not handle the type\" by returning `null`, which every caller has to remember to check. Change "
    "its return type to `java.util.Optional<TypeAdapter<T>>`: a factory that does not handle the type "
    "returns `Optional.empty()`, a factory that does returns the adapter wrapped in an `Optional` (use "
    "`Optional.ofNullable` where the adapter expression itself may be null). Update the interface and "
    "every implementation -- named classes and anonymous `new TypeAdapterFactory() { ... }` classes, in all "
    "Maven modules (gson, extras, proto, test-shrinker, ...) and in tests -- changing only the `return` "
    "statements that belong to `create` itself (not the `return null` inside a nested `TypeAdapter`'s "
    "`read`/`write`). Update every caller of `create` (e.g. `Gson.getAdapter`, `Gson.getDelegateAdapter`, "
    "`JsonAdapterAnnotationTypeAdapterFactory`, tests) to unwrap the `Optional` so that \"not handled\" is "
    "treated exactly as `null` was. Do not add a nullable-returning variant. Behavior must not change."
)


def _own_returns(m: str, a: int, b: int) -> list[tuple[int, int]]:
    """(start, end) of `return ...;` statements in m[a:b] (a method body)
    that belong to that method: not inside a nested class body or lambda."""
    stack = [False]  # foreign?
    out = []
    i = a
    while i < b:
        ch = m[i]
        if ch == "{":
            j = i - 1
            while j > a and m[j].isspace():
                j -= 1
            foreign = stack[-1]
            if m[j - 1:j + 1] == "->":
                foreign = True
            elif m[j] == ")":
                # match back to "(" and look at what precedes it
                depth, k = 0, j
                while k > a:
                    depth += m[k] == ")"
                    depth -= m[k] == "("
                    if depth == 0:
                        break
                    k -= 1
                before = m[max(a, k - 200):k]
                if re.search(r"\bnew\s+[\w.]+\s*(<[^;{}()]*>)?\s*$", before):
                    foreign = True
            else:
                seg = m[max(a, i - 300):i]
                seg = re.split(r"[;{}]", seg)[-1]
                if re.search(r"\b(class|interface|enum|record)\s+\w+", seg):
                    foreign = True
            stack.append(foreign)
        elif ch == "}":
            stack.pop()
        elif not stack[-1] and m.startswith("return", i) and not (m[i - 1].isalnum() or m[i - 1] == "_") \
                and not (m[i + 6].isalnum() or m[i + 6] == "_"):
            k = i
            depth = 0
            while True:
                c = m[k]
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    depth -= 1
                elif c == ";" and depth == 0:
                    break
                k += 1
            out.append((i, k + 1))
            i = k
        i += 1
    return out


@recipe(instance_id="deep__gson__TypeAdapterFactory_create_Optional",
        repo="google/gson", lang="java", repo_dir=GSON, base_commit=GSON_BASE,
        change="change return type (nullable -> Optional) of an interface method: ~45 implementations + callers",
        instruction=TAF_INSTR,
        decl_files=["gson/src/main/java/com/google/gson/TypeAdapterFactory.java"],
        shapes=[{"id": "TypeAdapter<T> create(Gson", "regex": r"\bTypeAdapter\s*<\s*\w+\s*>\s+create\s*\(\s*(?:final\s+)?Gson\b"}],
        gold_tool="build_deep.py recipe: create() declarations and their own return statements rewritten "
                  "(nested-class/lambda returns excluded by a brace scan); callers unwrapped with "
                  ".orElse(null) from javac errors; docker maven test-compile clean")
def make_taf(wt: Path):
    decl = re.compile(r"\bTypeAdapter(\s*<\s*(\w+)\s*>)(\s+create\s*\(\s*(?:final\s+)?Gson\s+\w+\s*,\s*(?:final\s+)?TypeToken\s*<[^>]*>\s*\w+\s*\)\s*\{)")
    ndecl = nret = 0
    for f in java_files(wt):
        raw = read(wt, f)
        if "create" not in raw or "TypeAdapter" not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for dm in decl.finditer(m):
            tv = dm.group(2)
            edits.append((dm.start(), dm.start(3), f"Optional<TypeAdapter<{tv}>>"))
            body_a = dm.end()
            i, depth = body_a, 1
            while depth:
                depth += m[i] == "{"
                depth -= m[i] == "}"
                i += 1
            for ra, rb in _own_returns(m, body_a, i - 1):
                expr_a = ra + len("return")
                expr = raw[expr_a:rb - 1].strip()
                ea = raw.index(expr, expr_a)
                if expr == "null":
                    edits.append((ea, ea + len(expr), "Optional.empty()"))
                elif expr.startswith("new ") and not expr.startswith("new ") is False and \
                        re.fullmatch(r"new\s[^?]*", expr) and "?" not in expr:
                    edits.append((ea, ea + len(expr), f"Optional.of({expr})"))
                else:
                    edits.append((ea, ea + len(expr), f"Optional.ofNullable({expr})"))
                nret += 1
            ndecl += 1
        if edits:
            raw = de.apply_edits(raw, edits)
            raw = ensure_java_import(raw, "java.util.Optional")
            write(wt, f, raw)
    itf = "gson/src/main/java/com/google/gson/TypeAdapterFactory.java"
    raw = read(wt, itf)
    raw = raw.replace("  <T> TypeAdapter<T> create(Gson gson, TypeToken<T> type);",
                      "  <T> Optional<TypeAdapter<T>> create(Gson gson, TypeToken<T> type);")
    write(wt, itf, ensure_java_import(raw, "java.util.Optional"))
    print(f"  create declarations: {ndecl}, own returns: {nret}")

    def fix(f, line, col, msg):
        if "incompatible types" in msg and "Optional" in msg:
            cs = [c for c in bd.calls_near(wt, f, "create", line) if c.arity == 2]
            if not cs:
                return False
            raw = read(wt, f)
            c = cs[0]
            write(wt, f, raw[:c.close + 1] + ".orElse(null)" + raw[c.close + 1:])
            return True
        return False

    jpms = lambda e: e[0].startswith("test-jpms/") and "module not found: com.google.gson" in e[3]
    compile_until_clean(wt, fix, ignore=jpms)
    # a cast caller compiles against Optional but would ClassCastException at runtime
    for f in java_files(wt):
        raw = read(wt, f)
        new = re.sub(r"\(TypeAdapter<Object>\) adapterFactory\.create\(gson, typeToken\);",
                     "(TypeAdapter<Object>) adapterFactory.create(gson, typeToken).orElse(null);", raw)
        if new != raw:
            write(wt, f, new)
    ok, errs, tail = java_compile(wt)
    if [e for e in errs if not jpms(e)] or (not ok and not errs):
        raise RuntimeError("gold does not compile after cast fix:\n" + "\n".join(map(str, errs[:20])))
