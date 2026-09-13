"""file_sections: delivered context is credited per file, and a section ends
at the next bold header of ANY kind.

Run: cd research/harness && python -m pytest -p no:asyncio -p no:pytest_asyncio tests/test_query_oracle.py -q
"""

import sys as _sys, os as _os
_H = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _d in (_H, _os.path.join(_H, "runners"), _os.path.join(_H, "aggregate"),
           _os.path.join(_H, "build"), _os.path.join(_H, "scoring")):
    if _d not in _sys.path:
        _sys.path.insert(0, _d)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query_oracle import file_sections  # noqa: E402

CTX = """**Context for: x**

**Anchors — callers (verify before editing)**
- `foo` (src/a/A.java:10)

**Source** — current on-disk

**`src/a/A.java`** — tab-indented file
```java
10	public void foo() { return this.alpha_only_line_in_a; }
```

**Family — related declarations**

**`src/b/B.java`**
```java
20	public void bar() { return this.beta_only_line_in_b; }
```

**Related tests**
```java
1	class ATest { void t() { unique_test_line_here(); } }
```
"""


def test_sections_are_per_file():
    s = file_sections(CTX)
    assert set(s) == {"src/a/A.java", "src/b/B.java"}
    assert "alpha_only_line_in_a" in s["src/a/A.java"]
    assert "beta_only_line_in_b" in s["src/b/B.java"]


def test_appendix_does_not_accrue_to_previous_file():
    # Reviewer probe 2026-09-05: b.java content credited toward a.java
    # because only a file header ended a section.
    s = file_sections(CTX)
    assert "beta_only_line_in_b" not in s["src/a/A.java"]
    assert "unique_test_line_here" not in s["src/b/B.java"]


if __name__ == "__main__":
    test_sections_are_per_file()
    test_appendix_does_not_accrue_to_previous_file()
    print("2 passed")
