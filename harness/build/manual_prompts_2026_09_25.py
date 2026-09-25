"""Hand-written problem statements for tasks whose PR links no issue (2026-09-25).

These tasks had prompt_source == "TITLE ONLY": the PR was the only description, and
PR text describes the fix. Rule applied to every entry, written from the PR text or
JIRA ticket only (never the gold patch or test patch):
  - keep what a user would report: symptom, repro, expected vs actual, public API names;
  - drop what was changed, how, and internal mechanism ("Cause:" / "Fix:" sections);
  - "Fix X" titles restated as the symptom.
Where a JIRA ticket exists its text is used (COLLECTIONS-714, LANG-1818). Where an
issue exists after all (jackson-databind #6031) it is fetched, not written.
Refactor/deprecation PRs (werkzeug, pydantic) are stated as the requested change,
since there is no bug to report.

Run: python3 build/manual_prompts_2026_09_25.py   (sets problem_statement,
keeps the previous text in problem_statement_title_only, prompt_source = "manual").
"""
import glob, json, subprocess
from pathlib import Path

P = {}

P["pallets__werkzeug__pr3162"] = """Inconsistent header name capitalization across the codebase

Header names are written in several different capitalizations throughout the code (for example `content-type`, `Content-type`, `Content-Type`). Please make header names consistently `Title-Case` everywhere, except where code deliberately works with lower-case names for case-insensitive comparison, and in tests that are specifically about case handling. This is a consistency cleanup: behavior must not change."""

P["pallets__werkzeug__pr3169"] = """Deprecate the `storage_class` attributes and `cls` parameters

`Request.parameter_storage_class` (used for `args`, `form`, `files`), `Request.dict_storage_class` (used for `cookies`) and `Request.list_storage_class` (used for `access_route`), as well as the `cls` parameter of `parse_cookie`, `parse_form_data` and `FormDataParser`, appear to exist only so users could substitute `OrderedMultiDict`, which has been removed now that `dict` preserves order. Request data is immutable, and an app that needs a mutable copy can do `MultiDict(request.form)`.

Please deprecate these attributes and parameters (emit a deprecation warning when they are used or overridden) so they can be removed in a future release, while keeping current behavior working in the meantime."""

P["pydantic__pydantic__pr12716"] = """Validation and serialization track the current field name differently

Validation and serialization each keep track of the field currently being processed in their state, but they do it in different ways (validation rebinds a copy of its `Extra` data to record the field name). Please unify how `field_name` is carried in state so validation and serialization use the same mechanism, avoiding the need to copy the full `Extra` struct. Behavior should be unchanged."""

P["FasterXML__jackson-databind__pr6099"] = """Naming a class in JSON runs its static initializer

When a class name comes from input — a `Class`-valued property or map key, or a polymorphic type id — `TypeFactory.findClass()` resolves it in a way that initializes the class. So merely naming a class in JSON runs that class's static initializer, just to look it up.

On the polymorphic path this happens before the `PolymorphicTypeValidator` gets to deny the type: a class that the validator rejects still has its static block executed.

Expected: resolving a class name from input should not run its static initializer; the class should only be initialized when it is actually used (for example when an allowed subtype is instantiated). Valid deserialization behavior should not change.

(2.18 branch.)"""

P["akheron__jansson__pr731"] = """Unpack: type mismatch errors don't say which key was wrong

When `json_unpack_ex` finds a value of the wrong type while unpacking an object such as `{"one": 1, "two": 2, "three": 3}`, the error message is just `Expected string, got integer`. It doesn't say which item was the problem, unlike the missing-item error, which does: `Object item not found: four`.

Expected: for values inside an object, the type-mismatch message should name the key, e.g. `Expected string, got integer for key two`. For values that are not in an object (in an array, or at the root level), the message should stay as it is. The innermost key is enough; a full path is not needed."""

P["akheron__jansson__pr740"] = """json_pack accepts a negative string length with `s#` / `+#`

The `s#` and `+#` formats of `json_pack` take a string plus an explicit length. Passing a negative length is not rejected; it is accepted as if it were a valid length.

Expected: a negative length for `s#` / `+#` should be treated as invalid input, and packing should fail with an error rather than proceed."""

P["akheron__jansson__pr741"] = """Deeply nested values overflow the stack in dump, equal and deep copy

`json_dump*`, `json_equal` and `json_deep_copy` recurse once per level of nesting. A value nested deeply enough (for example many thousands of nested arrays) exhausts the C stack and crashes the process.

Expected: these operations should not crash on deeply nested input; they should enforce a maximum nesting depth and fail with an error instead of overflowing the stack."""

P["apache__commons-collections__pr700"] = """switchClosure / switchMapClosure / switchMapTransformer modify the caller's map

`ClosureUtils.switchClosure(Map)`, `ClosureUtils.switchMapClosure(Map)` and `TransformerUtils.switchMapTransformer(Map)` treat the entry with a `null` key as the default. After calling one of them, that `null`-key entry has disappeared from the map the caller passed in: the factory has a side effect on its argument.

Expected: the factories should read the default from the map without mutating the caller's map; the caller's map should be unchanged after the call."""

P["apache__commons-collections__pr704"] = """MapUtils.getIntValue(Map, K, Function) returns truncated values

`MapUtils.getIntValue(Map, K, Function)` returns wrong results for values outside the signed-byte range:

- a map entry of `1000` returns `-24`;
- a `defaultFunction` yielding `Integer.MAX_VALUE` returns `-1`.

Expected: the full `int` value (`1000`, `Integer.MAX_VALUE`), as the other `getXxxValue(Map, K, Function)` overloads do for their types."""

P["apache__commons-collections__pr705"] = """HashBag / HashMultiSet counts and size overflow to negative

In `HashBag` and `HashMultiSet` (and the other bags/multisets built on `AbstractMapBag` / `AbstractMapMultiSet`), adding occurrences past `Integer.MAX_VALUE` overflows:

```java
bag.add(x, Integer.MAX_VALUE);
bag.add(x, 1);
bag.getCount(x);   // Integer.MIN_VALUE
bag.size();        // negative
```

Expected: `getCount` and `size()` should not go negative; per the `Collection.size()` contract they should saturate at `Integer.MAX_VALUE`."""

P["apache__commons-collections__pr710"] = """size() goes negative for composite and multi-valued collections

`CompositeCollection.size()`, `CompositeSet.size()` and `CompositeMap.size()` return a negative number when the total of their members exceeds `Integer.MAX_VALUE` — for example two members each reporting `Integer.MAX_VALUE` give `-2`. Compositing two full `HashBag`s is enough to hit it. `CompositeMap`'s Javadoc already promises `Integer.MAX_VALUE` in that case.

`AbstractMultiValuedMap.size()` and `AbstractMultiSet.size()` show the same wrap-around when their value collections / entry counts add up past `Integer.MAX_VALUE`.

Expected: per the `Collection.size()` contract, these should return `Integer.MAX_VALUE` when the true size is larger, never a negative number."""

P["apache__commons-collections__pr712"] = """PatriciaTrie ignores trailing null characters in keys

In Java, strings are not null terminated. The string "x" (of length = 1 char) is different from the string "x\\u0000" (of length = 2 chars). However, PatriciaTrie does not seem to distinguish between these strings.

To reproduce:
```java
public void testNullTerminatedKey1() {
    Map<String, Integer> map = new HashMap<>();
    map.put("x", 0);         // key of length 1
    map.put("x\\u0000", 1);   // key of length 2
    map.put("x\\u0000y", 2);  // key of length 3
    Assert.assertEquals(3, map.size());  // ok, 3 distinct keys

    PatriciaTrie<Integer> trie = new PatriciaTrie<>(map);
    Assert.assertEquals(3, trie.size());  // fail; actual=2
}
```
In the above example, the resulting trie has only two keys: "x\\u0000" and "x\\u0000y". The key "x" gets overwritten. Here is another way to repro the bug:
```java
public void testNullTerminatedKey2() {
    PatriciaTrie<Integer> trie = new PatriciaTrie<>();
    trie.put("x", 0);
    Assert.assertTrue(trie.containsKey("x")); // ok
    trie.put("x\\u0000", 1);
    Assert.assertTrue(trie.containsKey("x")); // fail
}
```
In the above example, the key "x" suddenly disappears when an entry with key "x\\u0000" is inserted.

The PatriciaTrie docs do not mention anything about null-terminated strings. In general, I believe this also breaks the JDK Map contract since the keys "x".equals("x\\u0000") is false.

(COLLECTIONS-714)"""

P["apache__commons-collections__pr713"] = """Out-of-range indexed add leaves SetUniqueList / ListOrderedSet inconsistent

`SetUniqueList.add(int, E)` / `addAll(int, Collection)` and `ListOrderedSet.add(int, E)` / `addAll(int, Collection)` throw `IndexOutOfBoundsException` for an out-of-range index, as expected — but the collection is left in a corrupted state afterwards:

- `contains(x)` returns `true` although `x` is not in the list;
- `size()` disagrees with `asSet()` / `asList()`;
- a later `add(x)` silently does nothing, because `x` is considered already present.

Expected: an add rejected because of a bad index should leave the collection exactly as it was (as `ListOrderedMap.put(int, K, V)` already does)."""

P["apache__commons-collections__pr714"] = """Flat3Map.entrySet().remove(entry) removes mappings whose value doesn't match

For a `Flat3Map`, `map.entrySet().remove(entry)` removes the mapping for `entry.getKey()` even when `entry.getValue()` is different from the value in the map. `AbstractHashedMap` (and the `Map.entrySet()` contract) only remove when both key and value match.

Expected: `entrySet().remove(e)` should remove a mapping only if the map contains that exact key/value pair, and return `false` otherwise."""

P["apache__commons-collections__pr715"] = """CollectionUtils.collate keeps duplicate nulls when includeDuplicates is false

With a null-tolerant comparator such as `Comparator.nullsFirst(...)`, the input collections may legally contain `null`. Calling `CollectionUtils.collate(a, b, comparator, false)` should drop duplicates, but repeated `null` elements are all kept in the result.

Expected: with `includeDuplicates == false`, `null` should be de-duplicated like any other element."""

P["apache__commons-collections__pr716"] = """TreeList add/remove with a bad index breaks existing iterators

On a `TreeList`, calling `add(int, E)` or `remove(int)` with an out-of-range index throws `IndexOutOfBoundsException` and leaves the list unchanged — yet an iterator obtained before that call now throws `ConcurrentModificationException` on its next use.

Expected: a rejected (out-of-range) `add`/`remove` should be a true no-op and must not invalidate existing iterators, as is already the case for `set(int, E)` and for `AbstractLinkedList`."""

P["apache__commons-collections__pr717"] = """MultiValuedMap get(key) mutators leave keys mapped to empty collections

For multi-valued maps built on `AbstractMultiValuedMap`:

- `map.get(key).addAll(emptyCollection)` on an absent key returns `false` (no change), yet afterwards `key` is present in the map, mapped to an empty collection;
- for list-valued maps (`AbstractListValuedMap`), `map.get(key).add(index, value)` with an out-of-range index throws, and afterwards `key` is present, mapped to an empty list.

Every remove path maintains the invariant that a key never maps to an empty collection, and `put(K, V)` behaves correctly. Expected: an add through `get(key)` that changes nothing, or that is rejected, should leave the map untouched."""

P["apache__commons-collections__pr718"] = """SplitMapUtils.readableMap view can be modified through remove

`SplitMapUtils.readableMap(Get)` returns a map that implements `Unmodifiable` and rejects `clear`, `put` and `putAll` — but `remove(Object)` goes through to the underlying map and deletes from it. The `Map` default methods inherit the hole, so `remove(k, v)`, `computeIfPresent`, `compute` and `merge` also modify the underlying map. Wrapping it with `UnmodifiableMap.unmodifiableMap(...)` doesn't help, since that returns the same object because it is already `Unmodifiable`.

Expected: like every other `Unmodifiable` implementation in the library, the view should throw `UnsupportedOperationException` for all mutators, including `remove`."""

P["apache__commons-collections__pr719"] = """OrderedProperties keySet() and values() get out of sync with the properties

For an `OrderedProperties`:

- `keySet().remove(k)` returns `true` and the key disappears from `keys()`, `entrySet()` and `store()` output, but `getProperty(k)` still returns the value;
- `keySet().add(k)` succeeds, although a key-set view must reject `add`;
- removing through `values()` deletes the mapping but leaves the key behind, after which `toString()` throws.

Expected: `keySet()` and `values()` should behave like the views of a normal `Properties`/`Map`: removals through them remove the mapping everywhere, and `add` on the key set is unsupported."""

P["apache__commons-lang__pr1591"] = """ClassUtils.getShortClassName(Class) misinterprets '$' in legitimate class names

`ClassUtils.getShortClassName(String)` operates on JVM binary names and necessarily relies on heuristics. As documented in its Javadoc, it cannot reliably distinguish package names, outer classes, and inner classes in all cases when given only a `String`.

However, these limitations should not apply to `getShortClassName(Class)` (and `getShortClassName(Object)`), where the `Class` is available. Currently, legitimate `$` characters in class identifiers are interpreted as inner-class separators. `$` is a valid character in Java identifiers and is used in practice (generated code, DSL-heavy libraries, test fixtures, Selenide's `$` and `$$`).

Reproducer:
```java
class $trange {}
class Pa$$word {}

class ClassUtilsShortClassNameTest {
    class $Inner {}
    class Inner {
        class Ne$ted {}
    }

    @Test
    void testDollarSignImmediatelyAfterPackage() {
        assertEquals("$trange", ClassUtils.getShortClassName($trange.class));
        // Actual: ".trange"
    }

    @Test
    void testDollarSignWithinName() {
        assertEquals("Pa$$word", ClassUtils.getShortClassName(Pa$$word.class));
        // Actual: "Pa..word"
    }

    @Test
    void testMultipleDollarSigns() {
        assertEquals(getClass().getSimpleName() + ".$Inner",
                     ClassUtils.getShortClassName($Inner.class));
        // Actual: "ClassUtilsShortClassNameTest..Inner"
    }

    @Test
    void testNe$tedClassName() {
        assertEquals(getClass().getSimpleName() + ".Inner.Ne$ted",
                     ClassUtils.getShortClassName(Inner.Ne$ted.class));
        // Actual: "ClassUtilsShortClassNameTest.Inner.Ne.ted"
    }
}
```
Existing results for local and anonymous classes, and the behavior of `getShortClassName(String)`, should stay as they are.

(LANG-1818)"""

P["apache__commons-lang__pr1631"] = """Wrong property name in SystemProperties.JDK_XML_ENTITY_REPLACEMENT_LIMIT

The constant `SystemProperties.JDK_XML_ENTITY_REPLACEMENT_LIMIT` contains a typo: its value is not the name of the JDK XML entity-replacement-limit system property it is meant to represent, so looking the property up through it does not find the JDK's setting.

Expected: the constant's value should be the property name exactly as the JDK defines it."""

P["apache__commons-lang__pr1655"] = """WordUtils.wrap mishandles wrapOn patterns that match more or less than one character

`WordUtils.wrap(str, wrapLength, newLineStr, wrapLongWords, wrapOn)` produces wrong output when the `wrapOn` regex matches something other than exactly one character:

- if `wrapOn` matches several characters, the extra separator characters are left in the wrapped output instead of being consumed;
- if `wrapOn` matches zero characters (a zero-width match), one character of the input is lost at each wrap.

Expected: the separator matched by `wrapOn` should be consumed exactly, whatever its length, including zero-width matches."""

P["apache__commons-lang__pr1670"] = """ClassUtils.getClass accepts malformed array class names

`ClassUtils.getClass(ClassLoader, String, boolean)` (through `ClassUtils.toCleanName(String)`) accepts class names with malformed array suffixes — for example stray or unbalanced brackets after the type name — and resolves them to some class instead of rejecting them.

Expected: a malformed array suffix should be rejected with an exception rather than resolved."""

P["apache__commons-lang__pr1699"] = """StringUtils.mid / StrBuilder.midString throw for very large lengths

Repro: `StringUtils.mid("foobar", 3, Integer.MAX_VALUE)` and `new StrBuilder("hello goodbye hello").midString(14, Integer.MAX_VALUE)`.
Expected: the tail of the string (`"bar"`, `"hello"`), per the Javadoc that says the rest is returned when the length exceeds what is available.
Actual: `StringIndexOutOfBoundsException`."""

P["apache__commons-lang__pr1703"] = """RandomStringUtils.random rejects a range that contains digits when letters and digits are requested

Repro: `RandomStringUtils.random(10, '0', 'A', true, true, null, rng)` throws `IllegalArgumentException`.
Expected: a string of digits, the same as the digits-only call over that range.
Actual: it throws, even though `RandomStringUtils.random(10, '0', 'A', false, true, null, rng)` succeeds on the identical range. Requesting letters in addition to digits should only widen the set of acceptable characters, never make a valid range fail."""

P["apache__commons-lang__pr1709"] = """Fraction.add / subtract report overflow for results that fit

`Fraction.add(Fraction)` and `Fraction.subtract(Fraction)` throw `ArithmeticException` (overflow) for some pairs of fractions whose denominators are coprime, even though the exact result is representable as a `Fraction` with `int` numerator and denominator.

Expected: an overflow exception only when the reduced result genuinely does not fit; otherwise the correct fraction."""

P["apache__commons-lang__pr1713"] = """StringUtils.getCommonPrefix / difference split surrogate pairs

Repro: `StringUtils.getCommonPrefix("𐐀", "𐐁")` returns the lone high surrogate `\\uD801`, and `StringUtils.difference("𐐀", "𐐁")` returns the lone low surrogate `\\uDC01`. Both are malformed UTF-16. `StringUtils.indexOfDifference("𐐀", "𐐁")` reports `1`, an index inside the surrogate pair.

Expected: when two strings differ within a supplementary character, the difference should be reported at the start of that character (index `0` here), so that `getCommonPrefix` and `difference` return well-formed strings."""

P["apache__commons-lang__pr1720"] = """DurationFormatUtils.formatPeriod gives wrong output for very long periods

`DurationFormatUtils.formatPeriod(startMillis, endMillis, format)` produces incorrect results — negative or wrapped field values — when the period between the two instants is very long.

Expected: correct field values for any valid `startMillis <= endMillis`."""

P["apache__commons-lang__pr1733"] = """NumberUtils.min / max varargs lose the sign of zero

Repro: `NumberUtils.max(-0.0d, 0.0d)` returns `-0.0` (so `1 / result` is `-Infinity`); `NumberUtils.min(0.0d, -0.0d)` returns `0.0`. The `float` overloads behave the same way.

Expected: the same results as `Math.max` / `Math.min`, the three-argument `NumberUtils.min`/`max` overloads and `IEEE754rUtils`, which return `0.0` for max and `-0.0` for min here. Existing `NaN` handling should stay the same."""

P["apache__commons-lang__pr1750"] = """ArrayUtils.reverse throws for an end index of Integer.MIN_VALUE

Repro: `ArrayUtils.reverse(new int[]{1, 2, 3}, 0, Integer.MIN_VALUE)`.
Expected: no change, since the `endIndexExclusive` Javadoc documents an undervalue (< start index) as no change.
Actual: `ArrayIndexOutOfBoundsException: Index 2147483647 out of bounds for length 3`.
All the primitive and `Object` range overloads of `reverse` behave this way."""

P["FasterXML__jackson-databind__pr6113"] = """DOM Node / Document cannot be serialized with polymorphic typing

Serializing a DOM `Node` or `Document` while type information is enabled fails:

```
InvalidDefinitionException: Type id handling not implemented for type
org.w3c.dom.Node (by DOMSerializer)
```

This happens for any holder typed with `@JsonTypeInfo`, or globally with `activateDefaultTyping(NON_FINAL)` when the holder class is non-final (e.g. a `Document`/`Node` field on a polymorphic bean).

```java
ObjectMapper polyMapper = jsonMapperBuilder()
        .activateDefaultTyping(NoCheckSubTypeValidator.instance, DefaultTyping.NON_FINAL)
        .build();
Document doc = DocumentBuilderFactory.newInstance().newDocumentBuilder()
        .parse(new InputSource(new StringReader("<root xmlns='http://foo'/>")));
polyMapper.writeValueAsString(doc); // throws InvalidDefinitionException
```

Expected: the document is written (as its XML text, with a type id), and reading it back as `Object` round-trips to the same XML."""

P["expressjs__express__pr7459"] = """res.send() no longer sets ETag when Transfer-Encoding is set

When a response already has a `Transfer-Encoding` header, `res.send(body)` no longer generates an automatic `ETag`, although ETag generation is enabled. Not adding `Content-Length` in that case is correct, but the missing `ETag` is a regression.

Expected: `res.send()` generates the `ETag` as usual whether or not `Transfer-Encoding` is present, while still omitting `Content-Length` when `Transfer-Encoding` is set."""

P["gin-gonic__gin__pr4695"] = """Context.Copy() drops Errors and Accepted

From issue #771, "Context.Copy does not copy Context.Errors":

> Is there a reason for this (appart from performance) ?
> It seems to me that it might be a usual case wanting to send errors to
> a logging platform or service which takes time, and a good way of doing
> that may be copying the context. Of course it can be done manually, but
> it seems to me that the semantics of Copy include copying .Errors.

The same applies to `Accepted`: content-negotiation state set by middleware via `c.SetAccepted(...)` is lost in the copy. Today `c.Copy()` returns a context whose `Errors` and `Accepted` are always `nil`, regardless of the original, while `Keys` and `Params` are copied correctly.

Expected: the copy carries `Errors` and `Accepted` from the original, as independent slices, so that changes on the copy do not affect the original context."""


def main():
    ids = set(P) | {"FasterXML__jackson-databind__pr6035"}
    seen = set()
    for f in sorted(glob.glob("tasks/**/*.json", recursive=True)):
        try:
            t = json.loads(Path(f).read_text())
        except Exception:
            continue
        if not isinstance(t, dict) or t.get("instance_id") not in ids:
            continue
        iid = t["instance_id"]
        if iid == "FasterXML__jackson-databind__pr6035":
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from build_task import _issue_text
            new, src = _issue_text(t["repo"], 6031), "issue"
        else:
            new, src = P[iid], "manual"
        if t.get("prompt_source") in ("manual",) or (src == "issue" and t.get("prompt_source") == "issue"):
            print(f"  (skip) {f}"); seen.add(iid); continue
        t.setdefault("problem_statement_title_only", t["problem_statement"])
        t["problem_statement"] = new
        t["prompt_source"] = src
        Path(f).write_text(json.dumps(t, indent=2))
        seen.add(iid)
        print(f"  [{src:6}] {f}")
    missing = ids - seen
    if missing:
        print("NOT FOUND:", sorted(missing))


if __name__ == "__main__":
    main()
