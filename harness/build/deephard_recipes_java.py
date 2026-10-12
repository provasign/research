"""HIGH-TURN ("deephard") Java recipes for build_deep.py.

Same conventions as deep_recipes_java.py (gold made mechanically in a fresh
checkout, javac's own errors drive the call-site edits, iterated to a clean
build; build_wide's shapes oracle + the repo's tests validate), but every
change here is chosen so one text substitution cannot do it: the edit at a
call site depends on the static type of an argument or on which overload /
override the site reaches, sites hide in anonymous classes, test trees and
other Maven modules, and javac's 100-error cap means many compile rounds.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import build_deep as bd
from build_deep import recipe, read, write, ensure_java_import
import deep_edit as de
from deep_recipes_java import DATABIND, DATABIND_BASE, GSON, GSON_BASE, java_files

# javac error header line, then indented continuation lines (candidate lists,
# "required:/found:" pairs) until the next [ERROR]/[INFO]/blank-prefix line.
JAVA_ERR_BLOCK = re.compile(r"^\[ERROR\] /w/(\S+\.java):\[(\d+),(\d+)\] (.*(?:\n(?!\[)[^\n]*)*)", re.M)


def java_compile_full(wt: Path, mvn_args: str = "", image: str = "maven:3.9-eclipse-temurin-17"):
    """mvn test-compile in docker; (ok, [(file, line, col, full_msg)], tail).
    Unlike build_deep.java_compile the message keeps javac's continuation
    lines (argument types of the failed call)."""
    import java_eval
    java_eval._pin_snapshot_parent(wt)
    cmd = f"set -o pipefail; mvn -q -nsu {mvn_args} test-compile -Dmaven.compiler.maxerrs=400 2>&1 | tail -5000"
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{wt}:/w", "-v", f"{bd.M2}:/root/.m2",
                        "-w", "/w", image, "bash", "-lc", cmd],
                       capture_output=True, text=True, timeout=3600)
    out = r.stdout + r.stderr
    seen, errs = set(), []
    for m in JAVA_ERR_BLOCK.finditer(out):
        e = (m.group(1), int(m.group(2)), int(m.group(3)), m.group(4))
        if e[:3] not in seen:
            seen.add(e[:3])
            errs.append(e)
    return r.returncode == 0, errs, out[-3000:]


def compile_until_clean(wt: Path, fix_error, rounds: int = 25, mvn_args: str = "", ignore=lambda e: False) -> None:
    last = None
    for i in range(rounds):
        ok, errs, tail = java_compile_full(wt, mvn_args)
        errs = [e for e in errs if not ignore(e)]
        print(f"  compile round {i}: ok={ok} errors={len(errs)}", flush=True)
        if ok:
            return
        if not errs:
            raise RuntimeError("build failed without parsable errors:\n" + tail)
        key = sorted(e[:3] for e in errs)
        if key == last:
            raise RuntimeError("no progress:\n" + "\n".join(str(e)[:400] for e in errs[:20]))
        last = key
        unhandled = []
        for e in sorted(errs, key=lambda e: (e[0], -e[1], -e[2])):
            if not fix_error(*e):
                unhandled.append(e)
        if unhandled and len(unhandled) == len(errs):
            raise RuntimeError("unhandled errors:\n" + "\n".join(str(e)[:600] for e in unhandled[:30]))
    raise RuntimeError("did not converge")


def remove_methods(text: str, decl_re: str) -> tuple[str, int]:
    """Delete every method whose declaration matches decl_re (anchored at the
    modifiers, after the javadoc), together with its javadoc/annotations."""
    pat = re.compile(r"\n(?:    /\*\*(?:(?!\*/).)*\*/\n)?(?:    @\w+(?:\([^)]*\))?\n)*    " + decl_re, re.S)
    out, pos, n = [], 0, 0
    for m in pat.finditer(text):
        i = text.index("{", m.end())
        d, j = 0, i
        while True:
            d += text[j] == "{"
            d -= text[j] == "}"
            if d == 0:
                break
            j += 1
        out.append(text[pos:m.start()])
        pos, n = j + 1, n + 1
    out.append(text[pos:])
    return "".join(out), n


def receiver_of(raw: str, masked: str, name_start: int) -> str | None:
    """The receiver expression text of a call `recv.name(` (None when the
    call is unqualified). Handles identifier chains with empty-arg calls."""
    j = name_start - 1
    while j >= 0 and masked[j].isspace():
        j -= 1
    if j < 0 or masked[j] != ".":
        return None
    end = j
    k = j - 1
    while k >= 0 and masked[k].isspace():
        k -= 1
    # walk back over [ident | ident() | ident(...)] ( . ... )*
    start = k + 1
    while k >= 0:
        if masked[k] == ")":
            d = 0
            while k >= 0:
                d += masked[k] == ")"
                d -= masked[k] == "("
                if d == 0:
                    break
                k -= 1
            k -= 1
        while k >= 0 and (masked[k].isalnum() or masked[k] in "_$"):
            k -= 1
        start = k + 1
        if k >= 0 and masked[k] == ".":
            k -= 1
            continue
        break
    return raw[start:end].strip()


def broad_test_classes(wt: Path, pkg_dirs: list[str], root: str = "src/test/java/") -> list[str]:
    """Test classes for the green layer: every *Test class in the given test
    package directories plus every test file the gold changed (build_wide's
    default is only the latter, too thin for a change spread over main code)."""
    de.git("-C", str(wt), "add", "-A")
    touched = [l for l in de.git("-C", str(wt), "diff", "--cached", "--name-only").splitlines()
               if "/src/test/java/" in "/" + l and l.endswith(".java")]
    files = set(touched)
    for d in pkg_dirs:
        for p in sorted((wt / root / d).glob("*Test.java")):
            files.add(str(p.relative_to(wt)))
    out = sorted({f.split("src/test/java/", 1)[1][:-5].replace("/", ".") for f in files})
    return out


def decl_params(raw: str, masked: str, c: de.Call) -> de.Call:
    """c with its argument spans re-split as a declaration's parameter list:
    commas inside generic type arguments (`Map<?,?> value`) do not split."""
    depth, start, spans = 0, c.open + 1, []
    for i in range(c.open + 1, c.close):
        ch = masked[i]
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        elif ch == "," and depth == 0:
            spans.append((start, i))
            start = i + 1
    spans.append((start, c.close))
    out = []
    for a, b in spans:
        seg = masked[a:b]
        if seg.strip():
            out.append((a + len(seg) - len(seg.lstrip()), b - (len(seg) - len(seg.rstrip()))))
    return de.Call(c.name_start, c.name_end, c.open, c.close, out)


# ------------------------------------------------------------------ JH1
# databind: DeserializationContext.handleUnexpectedToken / reportWrongTokenException /
# reportInputMismatch -- drop the Class<?> and JsonDeserializer<?> overloads, keep
# only the JavaType (and, for reportInputMismatch, BeanProperty) forms.

DC = "src/main/java/com/fasterxml/jackson/databind/DeserializationContext.java"
REPORT_NAMES = ("handleUnexpectedToken", "reportWrongTokenException", "reportInputMismatch",
                "handleWeirdKey", "handleWeirdStringValue", "handleWeirdNumberValue")
WEIRD = (("handleWeirdKey", "keyClass", "keyType"), ("handleWeirdStringValue", "targetClass", "targetType"),
         ("handleWeirdNumberValue", "targetClass", "targetType"))

COLLAPSE_INSTR = (
    "`DeserializationContext` (com.fasterxml.jackson.databind) identifies the target of a reported problem "
    "sometimes by `Class<?>`, sometimes by `JsonDeserializer<?>` and sometimes by `JavaType`; make it `JavaType` "
    "everywhere. (1) Delete the overloads `handleUnexpectedToken(Class<?> instClass, JsonParser p)`, "
    "`handleUnexpectedToken(Class<?> instClass, JsonToken t, JsonParser p, String msg, Object... msgArgs)`, "
    "`reportWrongTokenException(JsonDeserializer<?> deser, JsonToken expToken, String msg, Object... msgArgs)`, "
    "`reportWrongTokenException(Class<?> targetType, JsonToken expToken, String msg, Object... msgArgs)`, "
    "`reportInputMismatch(JsonDeserializer<?> src, String msg, Object... msgArgs)` and "
    "`reportInputMismatch(Class<?> targetType, String msg, Object... msgArgs)`, keeping their `JavaType` "
    "overloads and `reportInputMismatch(BeanProperty prop, ...)` (which also records the property path) as they "
    "are. (2) Change the first parameter of `handleWeirdKey(Class<?> keyClass, ...)`, "
    "`handleWeirdStringValue(Class<?> targetClass, ...)` and `handleWeirdNumberValue(Class<?> targetClass, ...)` "
    "to `JavaType keyType` / `JavaType targetType`; inside, use `ClassUtil.rawClass(...)` of it wherever the "
    "class was used, so the `DeserializationProblemHandler` callbacks still receive the same `Class<?>` and "
    "messages do not change. Do not change `DeserializationProblemHandler` itself (its "
    "`handleWeirdKey`/`handleWeirdStringValue`/`handleWeirdNumberValue`/`handleUnexpectedToken` methods, and "
    "their overrides in tests, keep their signatures). Then update every call of the affected "
    "`DeserializationContext` methods, in main and test code, by converting the first argument according to its "
    "static type, using the `DeserializationContext` the call is made on (the call's receiver, e.g. "
    "`ctxt`/`context`, or no receiver inside `DeserializationContext` itself): a `Class<?>` expression `x` becomes "
    "`<ctxt>.constructType(x)`; a `JsonDeserializer<?>` expression `d` becomes "
    "`<ctxt>.constructType(d.handledType())` (`this` inside a deserializer becomes "
    "`<ctxt>.constructType(handledType())`). Arguments that already are a `JavaType` or `BeanProperty` stay as "
    "they are. Do not add overloads, helpers or deprecated forwarding methods. Behavior and messages must not change."
)


def _collapse_shapes() -> list[dict]:
    # Old forms: a call of one of the three names whose first argument is a
    # Class/deserializer expression as written at base. The exact first-arg
    # texts are filled in by the recipe run (see make_collapse); declarations
    # of the removed overloads are a separate shape.
    return [{"id": "removed overload decl",
             "regex": r"\bpublic\s+(?:<T>\s+T|Object|void)\s+(?:handleUnexpectedToken|reportWrongTokenException|reportInputMismatch|"
                      r"handleWeirdKey|handleWeirdStringValue|handleWeirdNumberValue)\s*\(\s*"
                      r"(?:final\s+)?(?:Class\s*<\s*\?\s*>|JsonDeserializer\s*<\s*\?\s*>)\s+\w+\s*,"}]


COLLAPSE_FIRST_ARGS = [
    # first-argument texts (whitespace-normalised) that gold wraps; the shape below
    # matches them only directly as the first argument of the three methods.
]


@recipe(instance_id="deephard__jackson-databind__report_overloads_JavaType",
        repo="FasterXML/jackson-databind", lang="java", repo_dir=DATABIND, base_commit=DATABIND_BASE,
        change="remove 6 Class<?>/JsonDeserializer<?> overloads of 3 DeserializationContext methods and retype the first "
               "parameter of 3 more (Class -> JavaType); every caller converts its first argument by static type, with the "
               "call's own receiver; same-named DeserializationProblemHandler callbacks stay",
        instruction=COLLAPSE_INSTR,
        decl_files=[DC],
        shapes=[],  # set at gold time (make_collapse) -- see _set_collapse_shapes
        gold_tool="deephard_recipes_java.py: the six overloads deleted by pattern; every call site from javac's own "
                  "errors (argument types read from the error text, receiver from the call), wrapped in "
                  "<recv>.constructType(x) / <recv>.constructType(d.handledType()); docker maven test-compile clean")
def make_collapse(wt: Path):
    raw = read(wt, DC)
    raw, n = remove_methods(raw, r"public (?:<T> T|Object|void) (?:handleUnexpectedToken|reportWrongTokenException|"
                                 r"reportInputMismatch)\((?:Class<\?>|JsonDeserializer<\?>) ")
    assert n == 6, n
    for nm, cls, typ in WEIRD:
        pat = rf"(public Object {nm}\()Class<\?> {cls}(,[^{{]*\{{)"
        raw, k = re.subn(pat, lambda mm: f"{mm.group(1)}JavaType {typ}{mm.group(2)}\n"
                                         f"        final Class<?> {cls} = ClassUtil.rawClass({typ});", raw)
        assert k == 1, (nm, k)
    write(wt, DC, raw)
    wrapped: list[tuple[str, str, str]] = []  # (file, name, first-arg text)

    def fix(f, line, col, msg):
        head = msg.splitlines()[0]
        m = re.match(r"no suitable method found for (\w+)\(([^,)]*)", head)
        names = None
        argtype = None
        if m and m.group(1) in REPORT_NAMES:
            names, argtype = (m.group(1),), m.group(2)
        else:
            m2 = re.match(r"incompatible types: (.+?) cannot be converted to com\.fasterxml\.jackson\.databind\.JavaType", head)
            m3 = re.match(r"method (\w+) in class \S+ cannot be applied to given types", head)
            if m2:
                names, argtype = REPORT_NAMES, m2.group(1)
            elif m3 and m3.group(1) in REPORT_NAMES:
                fm = re.search(r"found:\s*([^,\n]+)", msg)
                names, argtype = (m3.group(1),), fm.group(1).strip() if fm else None
            elif "reference to reportInputMismatch is ambiguous" in head:
                names, argtype = ("reportInputMismatch",), "<null>"
        if not names or not argtype:
            return False
        r = read(wt, f)
        mk = de.mask(r, f)
        off = bd.line_offset(r, line, col)
        cands = []
        for nm in names:
            for c in de.find_calls(r, mk, nm):
                ln = r.count("\n", 0, c.name_start) + 1
                if c.args and (c.name_start <= off <= c.close or ln == line) and ln in (line, line + 1, line - 1) \
                        or (c.args and c.args[0][0] == off):
                    cands.append((nm, c))
        # javac points at the receiver/name for "no suitable method", at the argument for "incompatible"
        exact = [x for x in cands if x[1].args[0][0] == off]
        cands = exact or cands
        if not cands:
            return False
        nm, c = min(cands, key=lambda x: abs(x[1].name_start - off))
        a0, a1 = c.args[0]
        first = r[a0:a1]
        if "constructType(" in first:
            return False
        recv = receiver_of(r, mk, c.name_start)
        ctx = f"{recv}.constructType" if recv else "constructType"
        if argtype == "<null>":
            rep = "(JavaType) null"
        elif argtype.startswith("java.lang.Class") or argtype.startswith("Class<"):
            rep = f"{ctx}({first})"
        else:  # a deserializer
            rep = f"{ctx}(handledType())" if first == "this" else f"{ctx}({first}.handledType())"
        write(wt, f, r[:a0] + rep + r[a1:])
        wrapped.append((f, nm, re.sub(r"\s+", " ", first)))
        return True

    compile_until_clean(wt, fix)
    print(f"  call sites converted: {len(wrapped)} in {len({w[0] for w in wrapped})} files")
    firsts = sorted({w[2] for w in wrapped}, key=lambda s: (-len(s), s))
    alt = "|".join(re.escape(x).replace(r"\ ", r"\s*") for x in firsts)
    shape = {"id": "Class/deserializer first argument",
             "regex": rf"\b(?:{'|'.join(REPORT_NAMES)})\s*\(\s*(?:{alt})\s*,"}
    bd.RECIPES["deephard__jackson-databind__report_overloads_JavaType"]["shapes"] = _collapse_shapes() + [shape]
    bd.RECIPES["deephard__jackson-databind__report_overloads_JavaType"]["test_classes"] = broad_test_classes(
        wt, [f"com/fasterxml/jackson/databind/{d}" for d in ("deser/jdk", "deser/filter", "deser/enums", "exc", "node", "convert")])
    return {"notes": f"{len(wrapped)} call sites converted by gold."}


# ------------------------------------------------------------------ JH2
# databind: the type (de)serializer becomes the FIRST parameter of
#   JsonSerializer.serializeWithType(value, gen, serializers, typeSer)
#   JsonSerializable.serializeWithType(gen, serializers, typeSer)
#   JsonDeserializer.deserializeWithType(p, ctxt, typeDeser[, intoValue])

def move_arg_to_front(raw: str, call: de.Call, k: int) -> tuple[int, int, str]:
    """An edit that moves top-level argument/parameter #k to position 0,
    keeping the separators (and so the line breaks) where they were."""
    spans = call.args
    texts = [raw[a:b] for a, b in spans]
    order = [texts[k]] + texts[:k] + texts[k + 1:]
    out = []
    for i, (a, b) in enumerate(spans):
        out.append(order[i])
        if i + 1 < len(spans):
            out.append(raw[b:spans[i + 1][0]])
    return (spans[0][0], spans[-1][1], "".join(out))


WT_INSTR = (
    "Make the type (de)serializer the first parameter of jackson-databind's polymorphic-type entry points, so it "
    "reads first at every call: `JsonSerializer.serializeWithType(T value, JsonGenerator gen, SerializerProvider "
    "serializers, TypeSerializer typeSer)` becomes `serializeWithType(TypeSerializer typeSer, T value, "
    "JsonGenerator gen, SerializerProvider serializers)`; `JsonSerializable.serializeWithType(JsonGenerator gen, "
    "SerializerProvider serializers, TypeSerializer typeSer)` becomes `serializeWithType(TypeSerializer typeSer, "
    "JsonGenerator gen, SerializerProvider serializers)`; `JsonDeserializer.deserializeWithType(JsonParser p, "
    "DeserializationContext ctxt, TypeDeserializer typeDeserializer)` becomes `deserializeWithType(TypeDeserializer "
    "typeDeserializer, JsonParser p, DeserializationContext ctxt)` and `JsonDeserializer.deserializeWithType(JsonParser "
    "p, DeserializationContext ctxt, TypeDeserializer typeDeserializer, Object intoValue)` becomes "
    "`deserializeWithType(TypeDeserializer typeDeserializer, JsonParser p, DeserializationContext ctxt, Object "
    "intoValue)`. The other parameters keep their relative order. Change the declarations in "
    "`JsonSerializer`, `JsonSerializable` and `JsonDeserializer` and every override or implementation (serializers, "
    "deserializers, `JsonNode` classes and every other `JsonSerializable`, in main and test code, including "
    "anonymous and nested classes), and reorder the arguments of every call of these methods accordingly, "
    "keeping each argument expression as it is. Do not keep the old parameter orders as overloads or "
    "deprecated forwarders, and do not rename anything. Behavior must not change."
)


@recipe(instance_id="deephard__jackson-databind__withType_typeser_first",
        repo="FasterXML/jackson-databind", lang="java", repo_dir=DATABIND, base_commit=DATABIND_BASE,
        change="parameter reorder of three coupled method families (JsonSerializer/JsonSerializable.serializeWithType, "
               "JsonDeserializer.deserializeWithType x2 arities): every override and every call",
        instruction=WT_INSTR,
        decl_files=["src/main/java/com/fasterxml/jackson/databind/JsonSerializer.java",
                    "src/main/java/com/fasterxml/jackson/databind/JsonSerializable.java",
                    "src/main/java/com/fasterxml/jackson/databind/JsonDeserializer.java"],
        shapes=[],  # set at gold time: first argument texts of the moved type (de)serializers
        gold_tool="deephard_recipes_java.py: every serializeWithType/deserializeWithType declaration and call found in "
                  "masked text (arity 4 serializer: arg #3 to front; arity 3 / deserializer arity 4: arg #2 to front, "
                  "separators kept); docker maven test-compile clean")
def make_withtype(wt: Path):
    moved_first: set[str] = set()
    ndecl = ncall = 0
    files = set()
    for f in java_files(wt):
        raw = read(wt, f)
        if "WithType" not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for nm in ("serializeWithType", "deserializeWithType"):
            for c in de.find_calls(raw, m, nm):
                prev = de.prev_token(m, c.name_start)
                if bool(prev) and (prev[-1].isalnum() or prev[-1] in "_$>]") and \
                        prev not in ("return", "new", "throw", "else"):
                    c = decl_params(raw, m, c)
                if nm == "serializeWithType" and c.arity == 4:
                    k = 3
                elif c.arity in (3, 4):
                    k = 2
                else:
                    continue
                prev = de.prev_token(m, c.name_start)
                is_decl = bool(prev) and (prev[-1].isalnum() or prev[-1] in "_$>]") and \
                    prev not in ("return", "new", "throw", "else")
                t = re.sub(r"\s+", " ", raw[c.args[k][0]:c.args[k][1]])
                if is_decl:
                    if not re.match(r"(final )?(TypeSerializer|TypeDeserializer)\b", t):
                        raise RuntimeError(f"{f}: unexpected {nm} declaration param {t}")
                    ndecl += 1
                else:
                    moved_first.add(t)
                    ncall += 1
                edits.append(move_arg_to_front(raw, c, k))
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
            files.add(f)
    print(f"  declarations: {ndecl}, calls: {ncall}, files: {len(files)}")
    ok, errs, tail = java_compile_full(wt)
    if not ok:
        raise RuntimeError("gold does not compile:\n" + "\n".join(str(e)[:400] for e in errs[:20]) + tail[-1500:])
    alt = "|".join(re.escape(x).replace(r"\ ", r"\s*") for x in sorted(moved_first, key=lambda s: (-len(s), s)))
    # old form: a declaration whose first parameter is not the type (de)serializer, or a
    # call whose first argument is not one of the moved type-(de)serializer expressions
    shape = {"id": "type (de)serializer not first",
             "regex": rf"\b(?:serializeWithType|deserializeWithType)\s*\(\s*(?!(?:final\s+)?(?:TypeSerializer|"
                      rf"TypeDeserializer)\b|(?:{alt})\s*,)[\w(]"}
    bd.RECIPES["deephard__jackson-databind__withType_typeser_first"]["shapes"] = [shape]
    bd.RECIPES["deephard__jackson-databind__withType_typeser_first"]["test_classes"] = broad_test_classes(
        wt, [f"com/fasterxml/jackson/databind/{d}" for d in ("jsontype", "jsontype/deftyping", "jsontype/ext",
                                                              "ser/jdk", "node", "deser/jdk")])
    return {"notes": f"gold moved {ndecl} declarations and {ncall} calls."}


# ------------------------------------------------------------------ JH3
# gson: TypeAdapter.write(JsonWriter out, T value) -> writeValue(T value, JsonWriter out)

TA_WRITE_INSTR = (
    "`TypeAdapter.write(JsonWriter out, T value)` (com.google.gson) takes its arguments in the opposite order of "
    "`toJson(T value)`/`toJsonTree(T value)` and shares its name with `java.io.Writer.write`, which makes "
    "adapter code hard to search. Rename it to `writeValue` and put the value first: the abstract method becomes "
    "`public abstract void writeValue(T value, JsonWriter out) throws IOException`. Change every `TypeAdapter` "
    "subclass that overrides it -- named, nested and anonymous `new TypeAdapter<...>() { ... }` classes, in every "
    "Maven module (gson, extras, proto, metrics, test-graal-native-image, test-shrinker, test-jpms) and in tests -- to "
    "`writeValue(<value parameter>, <JsonWriter parameter>)`, keeping each override's parameter names, modifiers "
    "and body. Update every call of `TypeAdapter.write` (through fields, locals, `delegate()`, "
    "`TypeAdapter.this`, unqualified calls inside adapters, ...) to `writeValue` with the two argument expressions "
    "swapped. Do not touch methods that merely look similar: `java.io.Writer.write`, `Streams.write(JsonElement, "
    "JsonWriter)`, and `ReflectiveTypeAdapterFactory.BoundField.write(JsonWriter, Object)` (and its "
    "implementations and calls) keep their names and parameter order. Do not keep a `write` method or a "
    "forwarding overload on `TypeAdapter`. Behavior must not change."
)


def _swap_rename(raw: str, c: de.Call, new: str) -> list[tuple[int, int, str]]:
    a = move_arg_to_front(raw, c, 1)
    return [(c.name_start, c.name_end, new), a]


@recipe(instance_id="deephard__gson__TypeAdapter_writeValue_swap",
        repo="google/gson", lang="java", repo_dir=GSON, base_commit=GSON_BASE,
        change="rename + parameter swap of the core abstract method TypeAdapter.write(JsonWriter, T) -> "
               "writeValue(T, JsonWriter): every override (mostly anonymous classes, 5 Maven modules) and every call; "
               "same-named BoundField.write / Writer.write / Streams.write stay",
        instruction=TA_WRITE_INSTR,
        decl_files=["gson/src/main/java/com/google/gson/TypeAdapter.java"],
        # write/2 covers declarations and calls (a renamed-but-unswapped or swapped-but-unrenamed site still
        # counts: the former is write/2 no more but fails to compile, the latter stays write/2)
        shapes=[{"id": "write/2", "name": "write", "arity": 2}],
        gold_tool="deephard_recipes_java.py: every `void write(JsonWriter, X)` declaration (BoundField's, which throws "
                  "IllegalAccessException, excluded) renamed + parameters swapped in masked text; calls from javac's "
                  "own `cannot find symbol ... write(JsonWriter,...)` errors, renamed + arguments swapped; docker maven "
                  "test-compile clean (-pl !test-jpms, which needs the packaged jar)",
        notes="Look-alikes with the same name and arity (BoundField.write(writer, source), Streams.write(element, "
              "writer)) are unchanged by gold, so they cancel in the write/2 counts.")
def make_ta_write(wt: Path):
    ndecl = 0
    for f in java_files(wt):
        raw = read(wt, f)
        if "JsonWriter" not in raw or "write" not in raw:
            continue
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, "write"):
            if de.prev_token(m, c.name_start) != "void":
                continue
            c = decl_params(raw, m, c)
            if c.arity != 2:
                continue
            if not re.match(r"(final\s+)?JsonWriter\b", raw[c.args[0][0]:c.args[0][1]]):
                continue
            tail = m[c.close:c.close + 120]
            if re.match(r"\)\s*throws[^{;]*IllegalAccessException", tail):
                continue  # ReflectiveTypeAdapterFactory.BoundField.write
            if f.endswith("ReflectiveTypeAdapterFactory.java") and re.search(r"abstract\s+void\s*$", m[:c.name_start]) \
                    and "Object source" in raw[c.open:c.close]:
                continue
            edits += _swap_rename(raw, c, "writeValue")
            ndecl += 1
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
    print(f"  declarations: {ndecl}")
    ncall = [0]

    def fix(f, line, col, msg):
        if not (msg.startswith("cannot find symbol") and re.search(r"symbol:\s+method write\(", msg)):
            return False
        r = read(wt, f)
        mk = de.mask(r, f)
        off = bd.line_offset(r, line, col)
        cs = [c for c in de.find_calls(r, mk, "write") if c.arity == 2 and
              (c.name_start == off or (r.count("\n", 0, c.name_start) + 1 in (line, line + 1) and c.name_start >= off))]
        if not cs:
            return False
        c = min(cs, key=lambda c: c.name_start - off)
        write(wt, f, de.apply_edits(r, _swap_rename(r, c, "writeValue")))
        ncall[0] += 1
        return True

    compile_until_clean(wt, fix, mvn_args="-pl '!test-jpms'")
    print(f"  calls: {ncall[0]}")
    return {"notes": f"gold renamed {ndecl} declarations and {ncall[0]} calls."}


# ------------------------------------------------------------------ JH4
# gson: JsonWriter.value(...) overloads -> stringValue / booleanValue / numberValue

JW_INSTR = (
    "`JsonWriter.value(...)` (com.google.gson.stream) is overloaded seven ways, and which JSON type a call writes "
    "depends on Java overload resolution of its argument (an `int` silently goes to `value(long)`, an `Integer` to "
    "`value(Number)`, a `String` that is null writes `null`). Replace the overloads with type-named methods: "
    "`value(String)` becomes `stringValue(String)`; `value(boolean)` and `value(Boolean)` become "
    "`booleanValue(boolean)` and `booleanValue(Boolean)`; `value(float)`, `value(double)`, `value(long)` and "
    "`value(Number)` become `numberValue(float)`, `numberValue(double)`, `numberValue(long)` and "
    "`numberValue(Number)`. Bodies, annotations and Javadoc stay the same; `jsonValue(String)` and `nullValue()` "
    "are unchanged. Rename them in `JsonWriter` and in every subclass that overrides them (e.g. "
    "`com.google.gson.internal.bind.JsonTreeWriter`), and update every call of the old `value(...)` methods in "
    "every Maven module (gson, extras, proto, metrics, test-graal-native-image, test-shrinker, test-jpms), main and "
    "test code, so that each call keeps writing exactly what it wrote before: choose the new name from the static "
    "type of the argument (a `String` expression -> `stringValue`, `boolean`/`Boolean` -> `booleanValue`, any "
    "primitive number, `char` or `Number` subtype -> `numberValue`). Do not keep any `value(...)` method on "
    "`JsonWriter`, and do not touch unrelated methods named `value` (e.g. annotation `value()` elements). "
    "Behavior must not change."
)

JW_TYPES = {"String": "stringValue", "boolean": "booleanValue", "Boolean": "booleanValue",
            "float": "numberValue", "double": "numberValue", "long": "numberValue", "Number": "numberValue"}


def _jw_name_for(argtype: str) -> str:
    t = argtype.strip()
    if t in ("java.lang.String", "String"):
        return "stringValue"
    if t in ("boolean", "java.lang.Boolean", "Boolean"):
        return "booleanValue"
    if t in ("int", "long", "short", "byte", "char", "float", "double") or re.match(r"java\.(lang|math|util)\.", t) \
            or t.endswith("Number") or t.startswith("com.google.gson.internal.LazilyParsedNumber"):
        return "numberValue"
    raise RuntimeError(f"unknown argument type for JsonWriter.value: {t}")


@recipe(instance_id="deephard__gson__JsonWriter_value_typed_names",
        repo="google/gson", lang="java", repo_dir=GSON, base_commit=GSON_BASE,
        change="replace 7 overloads JsonWriter.value(...) by 3 type-named method groups (stringValue/booleanValue/"
               "numberValue) in JsonWriter + JsonTreeWriter; every call renamed by the static type of its argument",
        instruction=JW_INSTR,
        decl_files=["gson/src/main/java/com/google/gson/stream/JsonWriter.java",
                    "gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java"],
        shapes=[{"id": "value/1", "name": "value", "arity": 1}],  # declarations and calls
        gold_tool="deephard_recipes_java.py: the 14 declarations renamed by parameter type; every call from javac's "
                  "own `cannot find symbol: method value(<static type>)` errors, renamed by that type; docker maven "
                  "test-compile clean (-pl !test-jpms, which needs the packaged jar; its one call edited by pattern)",
        notes="value/1 look-alikes (other classes' one-argument value(...) methods) are unchanged by gold and cancel.")
def make_jw_value(wt: Path):
    nd = 0
    for f in ("gson/src/main/java/com/google/gson/stream/JsonWriter.java",
              "gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java"):
        raw = read(wt, f)
        raw, k = re.subn(r"\bpublic JsonWriter value\((String|boolean|Boolean|float|double|long|Number) ",
                         lambda mm: f"public JsonWriter {JW_TYPES[mm.group(1)]}({mm.group(1)} ", raw)
        assert k == 7, (f, k)
        nd += k
        write(wt, f, raw)
    ncall = [0]
    by_name: dict[str, int] = {}

    def fix(f, line, col, msg):
        sm = re.search(r"symbol:\s+method value\((.*)\)\s*$", msg, re.M)
        if not (msg.startswith("cannot find symbol") and sm) or "," in sm.group(1):
            return False
        r = read(wt, f)
        argtxt = sm.group(1)
        if re.search(r"\s|\[\.\.\.\]", argtxt):
            # javac prints a poly expression (conditional) instead of a type: type it from its non-null branch
            r0 = r
            mk0 = de.mask(r0, f)
            off0 = bd.line_offset(r0, line, col)
            cs0 = [c for c in de.find_calls(r0, mk0, "value") if c.arity == 1 and c.name_start >= off0 - 1]
            arg = r0[cs0[0].args[0][0]:cs0[0].args[0][1]] if cs0 else ""
            branches = [b.strip() for b in re.split(r"[?:]", arg)[1:]]
            other = [b for b in branches if b != "null"]
            if other and all(re.search(r'^"|toString\(\)$|^String\.valueOf\(|toExternalForm\(\)$|getHostAddress\(\)$|'
                                       r'^constantToName\.get\(', b) for b in other):
                argtxt = "java.lang.String"
            else:
                raise RuntimeError(f"{f}:{line}: cannot type poly argument {arg}")
        new = _jw_name_for(argtxt)
        mk = de.mask(r, f)
        off = bd.line_offset(r, line, col)
        cs = [c for c in de.find_calls(r, mk, "value") if c.arity == 1 and c.name_start >= off - 1 and
              r.count("\n", 0, c.name_start) + 1 in (line, line + 1)]
        if not cs:
            return False
        c = min(cs, key=lambda c: c.name_start)
        write(wt, f, r[:c.name_start] + new + r[c.name_end:])
        ncall[0] += 1
        by_name[new] = by_name.get(new, 0) + 1
        return True

    compile_until_clean(wt, fix, mvn_args="-pl '!test-jpms'")
    # test-jpms needs the packaged gson jar to compile; its calls are edited by literal type
    for f in java_files(wt):
        if not f.startswith("test-jpms/"):
            continue
        raw = read(wt, f)
        m = de.mask(raw, f)
        edits = []
        for c in de.find_calls(raw, m, "value"):
            if c.arity != 1 or de.prev_token(m, c.name_start) != ".":
                continue
            arg = raw[c.args[0][0]:c.args[0][1]]
            if re.fullmatch(r'"[^"]*"', arg):
                edits.append((c.name_start, c.name_end, "stringValue"))
            elif re.fullmatch(r"-?\d+[lL]?|-?\d+\.\d*[dDfF]?", arg):
                edits.append((c.name_start, c.name_end, "numberValue"))
            elif arg in ("true", "false"):
                edits.append((c.name_start, c.name_end, "booleanValue"))
            else:
                raise RuntimeError(f"{f}: cannot type {arg}")
        if edits:
            write(wt, f, de.apply_edits(raw, edits))
            ncall[0] += len(edits)
    print(f"  declarations: {nd}, calls: {ncall[0]} {by_name}")
    return {"notes": f"gold renamed {nd} declarations and {ncall[0]} calls {by_name}."}
