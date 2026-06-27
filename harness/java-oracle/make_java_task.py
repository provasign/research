"""Generate a harness Mode-A task from the Spoon change-impact oracle.

Runs the oracle for a target method (FQN#method[(params)]), then writes a task
JSON in the harness format with GT = the oracle's resolved change-sites
(declaration + override family + resolved call sites). Unlike the bare-name
oracle that polluted the commons-lang tasks, every GT site here is type-resolved.

Usage:
  python make_java_task.py --id jackson-deserialize \
    --target 'com.fasterxml.jackson.databind.JsonDeserializer#deserialize(JsonParser,DeserializationContext)' \
    --display 'JsonDeserializer.deserialize'
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
REPO = Path.home() / "gvg-corpus" / "jackson-databind"
JAR = HERE / "target" / "oracle.jar"
CP = HERE / "jackson-cp.txt"
JAVA = "/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home/bin/java"


def pin() -> str:
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def run_oracle(target: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        out = Path(tf.name)
    subprocess.run([JAVA, "-jar", str(JAR),
                    "--src", str(REPO / "src" / "main" / "java"),
                    "--repo", str(REPO), "--cp", str(CP),
                    "--target", target, "--out", str(out)],
                   check=True, capture_output=True, text=True)
    return json.loads(out.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--target", required=True, help="FQN#method[(ParamTypes)]")
    ap.add_argument("--display", required=True, help="e.g. JsonDeserializer.deserialize")
    args = ap.parse_args()

    res = run_oracle(args.target)
    gt = res["ground_truth"]
    task = {
        "id": args.id,
        "repo": str(REPO),
        "lang": "java",
        "pin": pin(),
        "pr": f"oracle-spoon:{args.target}",
        "task_type": "impact",
        "prompt": (f"The {args.display} method signature is changing. List every "
                   f"site in this repository that must change as a result "
                   f"(the declaration, every override/implementation, and every "
                   f"call site)."),
        "ground_truth": gt,
        "workdir": str(REPO),
    }
    out = HARNESS / "tasks" / f"{args.id}.json"
    out.write_text(json.dumps(task, indent=2) + "\n")
    print(f"[task] {args.id}  sites={len(gt)}  stats={res['stats']}")
    print(f"       -> {out}")


if __name__ == "__main__":
    main()
