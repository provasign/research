#!/usr/bin/env python3
"""pq — the single search verb. Graph first; grep ONLY if the graph is empty.

The contract (user spec, 2026-08-04): return the graph answer. If and only if
the graph has nothing for these terms, return a text (ripgrep) result instead.
Never both, never empty-handed. This is the exact rule the local arm's
_tool_prism_query_fb already used; pq.py extracts it so the SONNET arm (which
had been calling raw MCP prism_query with no fallback) tests the identical
behavior.

Usage: pq.py "<task>" "<comma,separated,terms>" [repo_dir]
"""
from __future__ import annotations
import subprocess, sys, os

PRISM = os.path.expanduser("~/bin/prism")


def _run(args, cwd, timeout):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
        return (r.stdout or ""), r.returncode
    except Exception as e:
        return f"(error: {e})", 1


def _graph(task, terms, cwd):
    out, rc = _run([PRISM, "query", task or terms, "--terms", terms,
                    "--include", "graph", "--format", "text"], cwd, 30)
    out = out.strip()
    # "thin" = empty, an error/usage line, or too short to be real context.
    if rc != 0 or not out or out.startswith("query:") or len(out) < 120:
        return None
    return out


def _grep(terms, cwd):
    outs = []
    for t in [x.strip() for x in terms.split(",") if x.strip()][:4]:
        out, _ = _run(["rg", "-n", "--no-heading", t, "."], cwd, 30)
        if out.strip():
            outs.append(f"-- text matches for '{t}' --\n" + out[:1200])
    return "\n".join(outs) or "(no graph hit and no text matches — try other terms)"


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    terms = sys.argv[2] if len(sys.argv) > 2 else ""
    cwd = sys.argv[3] if len(sys.argv) > 3 else "."
    if not terms and task:
        # derive up to 3 identifier-ish anchors from the task
        import re, collections
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", task)
        stop = {"this", "that", "with", "from", "have", "when", "should",
                "return", "returns", "value", "error", "does", "call", "when"}
        ranked = [w for w, _ in collections.Counter(words).most_common()
                  if w.lower() not in stop]
        terms = ",".join(ranked[:3]) or "main"
    g = _graph(task, terms, cwd)
    if g is not None:
        print(g[:5600])
    else:
        print("(graph empty for these terms; text search)\n" + _grep(terms, cwd)[:5600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
