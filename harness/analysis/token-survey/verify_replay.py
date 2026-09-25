"""Offline sizing for "verify runs the covering tests" (2026-09-24). No LLM cost.

Two questions, answered from existing transcripts (sessions with session_id only):

A. Turn sizing. How many API turns would one verify call absorb? A "check turn" is an
   assistant turn whose tool calls are all build/test/env/repro Bash. A chain is a run of
   consecutive check turns with no source edit between them (read/search turns in between
   break the chain -- conservative). Collapsing a chain of k turns to one verify call saves
   k-1. Reported three ways:
     upper   = every check chain collapses (env + build + test + ad-hoc repro)
     suite   = only chains made of repo build/test runs (verify knows the repo's test
               command; it cannot absorb the agent's own ad-hoc repro scripts)
     final   = only the chain after the LAST source edit (the "am I done" verification)
   Token estimate = the avoided turns' own request context (check outputs are small, so
   later turns' context barely changes).

Result 2026-09-24 (209 sessions): upper 19% of turns, suite-only 7%, post-last-edit 16%.
Sampling the chains showed most multi-turn chains are the agent failing to get the runner
working (python vs python3, pytest-asyncio plugin, -Djacoco.skip/-Drat.skip, JAVA_HOME).
Same-tool, same-target reruns with no edit between: 1.43/session = 8.8% of turns (python
13.5%, java 9.2%, go 5.3%, c 2.0%). B: reproduced-before-editing is rare and NOT higher in
resolved cells (4% resolved vs 9% failed) -- the before/after "vacuous check" signal does
not separate outcomes on this bed.

B. Distinguishing check. On this bed the gold tests are absent from the checkout and test
   edits are forbidden, so any repo test the agent runs passes on base by construction.
   The only check that can tell base from fix is one the agent observed BEFORE editing and
   again AFTER. Proxy per session: agent ran a check before its first source edit
   ("reproduced") and re-ran a check after. Split by resolved/failed.
"""
import json, re, sys
from pathlib import Path
from collections import Counter, defaultdict

RES = Path(__file__).resolve().parents[2] / "results"
PROJ = Path.home() / ".claude" / "projects"
SETS = [("search-body-ab", ("native", "prism")), ("guard-hook-ab", ("native", "prism")),
        ("residency-ab", ("native", "prism")),
        # h3 treatment arm mandated verify -- behavior not natural, control arm only
        ("h3-ab/pass1", ("native",)), ("h3-ab/pass2", ("native",)), ("h3-ab/pass3", ("native",))]

TEST = re.compile(r"\b(mvn|mvnw|gradlew?|go test|pytest|py\.test|-m pytest|-m unittest|npm (run )?test|"
                  r"npx (jest|mocha|vitest)|yarn test|cargo test|make (test|check)|ctest|tox|jest|mocha|"
                  r"vitest|runtests|manage\.py test)\b")
BUILD = re.compile(r"\b(go build|go vet|cmake|make\b|cargo (build|check)|npm run build|tsc\b|javac|gcc|clang|cc )")
ENV = re.compile(r"(-m venv|pip3? install|uv (pip|venv|sync)|npm (ci|install)|yarn install|apt-get|"
                 r"brew install|source .*activate|mvn .*(install|dependency:))")
REPRO = re.compile(r"(python3? (-c|/tmp|- <<|<<)|node (-e|/tmp)|/tmp/\S+\.(py|js|c|java|go|sh)|go run|"
                   r"jshell|java /tmp|ruby -e|php -r)")
SRC_EXT = re.compile(r"\.(py|java|go|js|ts|tsx|jsx|mjs|cjs|c|h|cc|cpp|rs|php|rb|kt|scala|cs)$")


def transcript(sid):
    hits = list(PROJ.glob(f"*/{sid}.jsonl"))
    return hits[0] if hits else None


def classify(cmd):
    if TEST.search(cmd): return "test"
    if REPRO.search(cmd): return "repro"
    if ENV.search(cmd): return "env"
    if BUILD.search(cmd): return "build"
    return None


def is_src_edit(name, inp):
    if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        p = str(inp.get("file_path") or inp.get("notebook_path") or "")
        return not p.startswith(("/tmp", "/private/tmp")) and bool(SRC_EXT.search(p))
    if name == "Bash":
        c = str(inp.get("command", ""))
        return bool(re.search(r"\bsed -i|\bperl -pi", c)) and "/tmp/" not in c
    return False


def turns_of(path):
    """Ordered API turns: [(ctx_tokens, [(tool, input), ...])]. One turn per message.id."""
    order, byid = [], {}
    for line in path.read_text(errors="ignore").splitlines():
        try: j = json.loads(line)
        except Exception: continue
        if j.get("type") != "assistant": continue
        m = j.get("message") or {}
        mid = m.get("id")
        if mid not in byid:
            u = m.get("usage") or {}
            ctx = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + \
                  (u.get("cache_creation_input_tokens") or 0)
            byid[mid] = [ctx, []]; order.append(mid)
        for c in m.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                byid[mid][1].append((c.get("name"), c.get("input") or {}))
    return [tuple(byid[m]) for m in order]


def analyse(turns):
    kinds = []  # per turn: "edit" | "check:<cls>" | "other"
    for ctx, tools in turns:
        if any(is_src_edit(n, i) for n, i in tools): kinds.append(("edit", None)); continue
        bash = [classify(str(i.get("command", ""))) for n, i in tools if n == "Bash"]
        if tools and len(bash) == len(tools) and all(bash):
            kinds.append(("check", set(bash)))
        else:
            kinds.append(("other", None))
    n = len(turns)
    chains, cur = [], []
    for idx, (k, cls) in enumerate(kinds):
        if k == "check": cur.append((idx, cls))
        else:
            if cur: chains.append(cur); cur = []
    if cur: chains.append(cur)
    edits = [i for i, (k, _) in enumerate(kinds) if k == "edit"]
    first_edit = edits[0] if edits else None
    last_edit = edits[-1] if edits else None
    out = Counter(turns=n, check_turns=sum(1 for k, _ in kinds if k == "check"))
    tok = Counter()
    for ch in chains:
        save = len(ch) - 1
        if save <= 0: continue
        # tokens saved ~= the avoided turns' own requests; later turns' context barely
        # changes because check outputs are small (verify_estimate: test bytes ~0.8%).
        t = sum(turns[j][0] for j, _ in ch[1:])
        out["upper"] += save; tok["upper"] += t
        if all(c <= {"test", "build"} for _, c in ch):
            out["suite"] += save; tok["suite"] += t
        if last_edit is not None and ch[0][0] > last_edit:
            out["final"] += save; tok["final"] += t
    reproduced = first_edit is not None and any(k == "check" and ("repro" in c or "test" in c)
                                                for k, c in kinds[:first_edit])
    rechecked = first_edit is not None and any(k == "check" for k, _ in kinds[first_edit:])
    any_check = any(k == "check" for k, _ in kinds)
    return out, tok, dict(reproduced=reproduced, distinguishing=reproduced and rechecked,
                          any_check=any_check, edited=first_edit is not None,
                          total_ctx=sum(c for c, _ in turns))


def main():
    agg, tok, n_sessions, missing = Counter(), Counter(), 0, 0
    total_tokens = 0
    by = defaultdict(Counter)
    per_task = defaultdict(list)
    for d, arms in SETS:
        for t in json.loads((RES / d / "results.json").read_text()):
            for a in arms:
                cell = t.get(a) or {}
                sid = cell.get("session_id")
                if not sid or cell.get("error"): continue
                p = transcript(sid)
                if not p: missing += 1; continue
                turns = turns_of(p)
                if not turns: missing += 1; continue
                o, tk, flags = analyse(turns)
                n_sessions += 1; agg += o; tok += tk; total_tokens += flags["total_ctx"]
                g = "resolved" if cell.get("resolved") else "FAILED"
                by[g]["n"] += 1
                for f in ("reproduced", "distinguishing", "any_check", "edited"):
                    by[g][f] += flags[f]
                per_task[t["task"]].append((bool(cell.get("resolved")), flags["distinguishing"]))
    print(f"sessions analysed: {n_sessions} (transcripts missing: {missing})")
    print(f"API turns: {agg['turns']} ({agg['turns']/n_sessions:.1f}/session), "
          f"check turns: {agg['check_turns']} ({agg['check_turns']/n_sessions:.2f}/session)")
    print(f"total input-side tokens (sum of per-turn context): {total_tokens/1e6:.1f}M")
    print("\nA. removable turns if one verify call absorbs a check chain")
    for k, label in (("upper", "every check chain (env+build+test+repro)"),
                     ("suite", "repo build/test chains only"),
                     ("final", "post-last-edit chain only")):
        print(f"  {label:44s} {agg[k]:4d} turns = {agg[k]/n_sessions:.2f}/session = "
              f"{100*agg[k]/agg['turns']:.1f}% of turns, ~{100*tok[k]/total_tokens:.1f}% of tokens")
    print("\nB. distinguishing check (checked before first edit AND after)")
    for g in ("resolved", "FAILED"):
        c = by[g]; n = c["n"]
        print(f"  {g:8s} n={n:3d}: edited {c['edited']}/{n}, any check {c['any_check']}/{n}, "
              f"reproduced before editing {c['reproduced']}/{n} ({100*c['reproduced']/n:.0f}%), "
              f"before+after {c['distinguishing']}/{n} ({100*c['distinguishing']/n:.0f}%)")
    # within-task comparison: tasks with both resolved and failed cells
    w = Counter()
    for task, cells in per_task.items():
        rs = [d for r, d in cells if r]; fs = [d for r, d in cells if not r]
        if rs and fs:
            w["mixed_tasks"] += 1
            w["res_cells"] += len(rs); w["res_dist"] += sum(rs)
            w["fail_cells"] += len(fs); w["fail_dist"] += sum(fs)
    if w["mixed_tasks"]:
        print(f"  within the {w['mixed_tasks']} tasks that both resolved and failed: "
              f"before+after in resolved cells {w['res_dist']}/{w['res_cells']} "
              f"({100*w['res_dist']/w['res_cells']:.0f}%), failed cells {w['fail_dist']}/{w['fail_cells']} "
              f"({100*w['fail_dist']/w['fail_cells']:.0f}%)")


if __name__ == "__main__":
    main()
