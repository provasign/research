#!/usr/bin/env python3
"""Change-impact ceiling benchmark run over the MCP TEXT surface.

ci_invariants.py scores `prism change-impact` CLI JSON. v0.55.6's renderers
made the MCP tools/call result a text rendering instead of JSON — a path no
accuracy benchmark exercises. This runs the SAME ceiling tasks against the
SAME committed ground truth with the SAME scorer, but parses the sites out
of the text the MCP server actually delivers to agents. A dropped site in
the renderer shows up here as a recall regression that ci_invariants cannot
see.
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
import ci_invariants as ci                      # noqa: E402
from schema import Answer, Site, Task           # noqa: E402
from score import score                         # noqa: E402

PRISM = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "bin" / "prism")
CORPUS_ROOT = Path.home() / ".cache" / "prism-research" / "ci-corpus"

SECTION = re.compile(r"^(declarations|supers|family|callers|declaringTypes) \(\d+\):$")
SITE = re.compile(r"^  (\S+)\s+(\S+):(\d+)(?:\s+\(via .*\))?$")


class MCP:
    def __init__(self, cwd: Path):
        self.p = subprocess.Popen([PRISM, "mcp"], cwd=cwd, text=True,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.i = 0
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                "clientInfo": {"name": "bench", "version": "0"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0",
                                       "method": "notifications/initialized"}) + "\n")
        self.p.stdin.flush()

    def rpc(self, method, params):
        self.i += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.i,
                                       "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server died")
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("id") == self.i:
                return m

    def change_impact_text(self, query: str) -> str:
        r = self.rpc("tools/call", {"name": "prism_change_impact",
                                    "arguments": {"query": query}})
        return r["result"]["content"][0]["text"]

    def close(self):
        self.p.kill()


def sites_from_text(text: str) -> list[str]:
    """Mirror of ci_invariants.engine_sites over the text form: union of
    declarations/family/callers/declaringTypes (NOT supers), as file:name
    with the bare leaf name."""
    if text.lstrip().startswith("{"):
        raise RuntimeError("MCP returned JSON — renderer fell back; nothing to test")
    sites, section = [], None
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            section = m.group(1)
            continue
        if section in ("declarations", "family", "callers", "declaringTypes"):
            s = SITE.match(line)
            if s:
                name = s.group(1).rsplit(".", 1)[-1]
                sites.append(f"{s.group(2)}:{name}")
        if line and not line.startswith("  "):
            if not SECTION.match(line):
                section = None
    return sites


def main():
    print(f"MCP-surface ceiling: prism={PRISM}")
    baseline = json.loads((HARNESS / "ci_baseline.json").read_text())
    failures = []

    def check(name, recall, precision, gt, nsites):
        base = baseline["ceilings"][name]
        tol = base.get("tolerance", 0.005)
        ok = recall >= base["recall"] - tol and precision >= base["precision"] - tol
        print(f"  {name:<28} GT={gt:<4} recall={recall:.4f} (base {base['recall']:.4f}) "
              f"precision={precision:.4f} (base {base['precision']:.4f}) "
              f"sites={nsites}  [{'OK' if ok else 'REGRESSION'}]")
        if not ok:
            failures.append(name)

    servers: dict[Path, MCP] = {}

    def server(workdir: Path) -> MCP:
        if workdir not in servers:
            servers[workdir] = MCP(workdir)
        return servers[workdir]

    for task_id, corpus_name in [
        ("jackson-jsonnode-get", "jackson-databind"), ("jackson-settable-set", "jackson-databind"),
        ("jackson-writetypeprefix", "jackson-databind"), ("jackson-serializewithtype", "jackson-databind"),
        ("jackson-deserialize", "jackson-databind"), ("jackson-serialize", "jackson-databind"),
        ("typeorm-driver-escape", "typeorm"), ("django-quotename", "django"),
        ("guava-forwarding-delegate", "guava"),
        ("commons-collections-transformer-transform", "commons-collections"),
    ]:
        task = Task.load(str(HARNESS / "tasks" / f"{task_id}.json"))
        workdir = ci.fetch_corpus(corpus_name, ci.CORPORA[corpus_name], CORPUS_ROOT)
        fqn = task.pr.split(":", 1)[1]
        query = (fqn.split("#", 1)[0].rsplit(".", 1)[-1] + "." + fqn.split("#", 1)[1]
                 if "#" in fqn else fqn)
        raw = sites_from_text(server(workdir).change_impact_text(query))
        card = score(task, Answer(sites=[Site.parse(s) for s in raw],
                                  complete=True, unresolved=[]), "MCP", 0)
        check(task_id, card.recall, card.precision, len(task.ground_truth), len(raw))

    for task_id, queries in ci.GO_QUERIES.items():
        task = Task.load(str(HARNESS / "tasks" / f"{task_id}.json"))
        corpus_key = ci.CORPUS_ALIAS.get(task_id, task_id)
        workdir = ci.fetch_corpus(corpus_key, ci.CORPORA[corpus_key], CORPUS_ROOT)
        seen = {}
        srv = server(workdir)
        for q in queries:
            for s in sites_from_text(srv.change_impact_text(q)):
                seen[s] = True
        raw = list(seen)
        card = score(task, Answer(sites=[Site.parse(s) for s in raw],
                                  complete=True, unresolved=[]), "MCP", 0)
        check(task_id, card.recall, card.precision, len(task.ground_truth), len(raw))

    for s in servers.values():
        s.close()
    print("\n" + ("ALL MCP-SURFACE CEILINGS HELD" if not failures
                  else f"REGRESSIONS: {failures}"))
    sys.exit(1 if failures else 0)


main()
