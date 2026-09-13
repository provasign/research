"""change_impact(symbol) -- a HIGH-ALTITUDE code-graph tool.

The whole point (see run_local*.py findings): weak/local models can't orchestrate
a multi-turn graph traversal over primitives (references/lookup/query) -- neither
as a CLI nor as MCP tools. So collapse the traversal into ONE call: given a method,
return the complete change-impact set (declaration + override/implementation family
+ resolved call sites) as "<relpath>:<Method>" strings. A flaky model then needs a
single correct action, not a 40-turn dance.

VALIDITY NOTE (read before citing any number). This prototype computes the set with
the Spoon type-resolution engine -- the SAME engine that produces the study's ground
truth. So scoring a change_impact-fed answer against that ground truth is
tautological (recall -> 1.0 by construction). That is fine for what this
demonstrates -- *that a weak model can consume a high-altitude tool in one call and
relay a complete set* (contrast: the same model on graph PRIMITIVES scores 0.0) --
but it is NOT a graph-vs-text measurement. For a scored claim, this resolution must
live inside Grove/Prism (a real product capability) and be scored against an
INDEPENDENT oracle. Here it stands in for that not-yet-built Grove capability.

Usage:
  python change_impact.py --repo ~/gvg-corpus/jackson-databind "JsonNode.get(int)"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE / "java-oracle" / "target" / "oracle.jar"
CP = HERE / "java-oracle" / "jackson-cp.txt"
JAVA = "/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home/bin/java"


def resolve_fqn(symbol: str, repo: Path) -> str:
    """Turn a loose 'Class.method' / 'Class.method(params)' / 'pkg.Class.method'
    into the oracle's 'FQN#method(params)' by locating the class source file."""
    m = re.match(r"^\s*([\w.]+?)\.(\w+)\s*(\(.*\))?\s*$", symbol.strip())
    if not m:
        raise ValueError(f"cannot parse symbol: {symbol!r} (want Class.method[(params)])")
    owner, method, params = m.group(1), m.group(2), (m.group(3) or "")
    cls = owner.split(".")[-1]  # last segment is the class name
    src = repo / "src" / "main" / "java"
    hits = list(src.rglob(f"{cls}.java"))
    if not hits:
        raise ValueError(f"class source not found: {cls}.java")
    rel = hits[0].relative_to(src)
    fqn = ".".join(rel.with_suffix("").parts)
    return f"{fqn}#{method}{params}"


def change_impact(symbol: str, repo: Path) -> dict:
    target = resolve_fqn(symbol, repo)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        out = Path(tf.name)
    subprocess.run([JAVA, "-jar", str(ORACLE),
                    "--src", str(repo / "src" / "main" / "java"),
                    "--repo", str(repo), "--cp", str(CP),
                    "--target", target, "--out", str(out)],
                   check=True, capture_output=True, text=True)
    res = json.loads(out.read_text())
    return {"target": target, "sites": res["ground_truth"], "count": len(res["ground_truth"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("symbol")
    args = ap.parse_args()
    r = change_impact(args.symbol, Path(args.repo).expanduser())
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
