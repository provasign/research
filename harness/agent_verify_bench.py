"""Agent-level verify-moment bench: bare Opus vs mason+local on the SAME
seeded incomplete refactors. Per task/trial: mutate declaration, update a
seeded ~50% of ground-truth files, leave the rest forgotten; ask each agent
to list what the diff missed. Score: forgotten-file catch + false flags.
Seeding logic copied from verify_bench.py (engine-level bench)."""
import json, random, re, subprocess, sys
from pathlib import Path
HARNESS = Path.home()/"Projects/provasign/research/harness"
sys.path.insert(0, str(HARNESS))
from schema import Answer
OUT = HARNESS/"runs/agent-verify"; OUT.mkdir(parents=True, exist_ok=True)
MASON = "/tmp/mason-bench"
LOCAL = "ollama:qwen3-coder:30b"
CFG = {
 "jackson-jsonnode-get": (
   "src/main/java/com/fasterxml/jackson/databind/JsonNode.java",
   r"public abstract JsonNode get\(int index\);",
   "public abstract JsonNode get(int zzNewParam, int index);", "get", "// upd"),
 "jackson-settable-set": (
   "src/main/java/com/fasterxml/jackson/databind/deser/SettableBeanProperty.java",
   r"public abstract void set\(Object instance, Object value\)",
   "public abstract void set(int zzNewParam, Object instance, Object value)", "set", "// upd"),
 "jackson-writetypeprefix": (
   "src/main/java/com/fasterxml/jackson/databind/jsontype/TypeSerializer.java",
   r"public abstract WritableTypeId writeTypePrefix\(JsonGenerator g,",
   "public abstract WritableTypeId writeTypePrefix(int zzNewParam, JsonGenerator g,", "writeTypePrefix", "// upd"),
 "jackson-serialize": (
   "src/main/java/com/fasterxml/jackson/databind/JsonSerializer.java",
   r"public abstract void serialize\(T value, JsonGenerator gen, SerializerProvider serializers\)",
   "public abstract void serialize(int zzNewParam, T value, JsonGenerator gen, SerializerProvider serializers)", "serialize", "// upd"),
 "guava-forwarding-delegate": (
   "src/com/google/common/collect/ForwardingObject.java",
   r"protected abstract Object delegate\(\);",
   "protected abstract Object delegate(int zzNewParam);", "delegate", "// upd"),
 "grafana-checkhealth-impact": (
   "pkg/plugins/plugins.go",
   r"func \(p \*Plugin\) CheckHealth\(ctx context\.Context,",
   "func (p *Plugin) CheckHealth(zzNewParam int, ctx context.Context,", "CheckHealth", "// upd"),
 "grafana-querydata-impact": (
   "pkg/plugins/plugins.go",
   r"func \(p \*Plugin\) QueryData\(ctx context\.Context,",
   "func (p *Plugin) QueryData(zzNewParam int, ctx context.Context,", "QueryData", "// upd"),
 "typeorm-driver-escape": (
   "src/driver/Driver.ts",
   r"escape\(name: string\): string",
   "escape(zzNewParam: number, name: string): string", "escape", "// upd"),
 "django-quotename": (
   "django/db/backends/base/operations.py",
   r"def quote_name\(self, name\):",
   "def quote_name(self, name, zz_new=0):", "quote_name", "# upd"),
}

def sh(cmd, cwd, timeout=900):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def touch_calls(path: Path, method: str, comment: str) -> int:
    """Append a comment to every line naming the method — line-count preserving."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    pat = re.compile(re.escape(method) + r"\s*\(")
    n = 0
    for i, ln in enumerate(lines):
        if pat.search(ln) and comment not in ln and "\\" != ln.rstrip()[-1:]:
            lines[i] = ln + "  " + comment
            n += 1
    path.write_text("\n".join(lines), encoding="utf-8")
    return n

def touch_calls(path: Path, method: str, comment: str) -> int:
    """Append a comment to every line naming the method — line-count preserving."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    pat = re.compile(re.escape(method) + r"\s*\(")
    n = 0
    for i, ln in enumerate(lines):
        if pat.search(ln) and comment not in ln and "\\" != ln.rstrip()[-1:]:
            lines[i] = ln + "  " + comment
            n += 1
    path.write_text("\n".join(lines), encoding="utf-8")
    return n


CONTRACT = ('When done, output ONLY a single JSON object: {"sites": ["<relpath>:<Symbol>", ...], '
            '"complete": true|false, "unresolved": []}. One entry per site that still needs the update. '
            'No prose after the JSON.\n\n')

def prompt_for(method, decl):
    return (f"The signature of `{method}` (declared in {decl}) was just changed in this working tree, "
            f"and its call sites and overrides were being updated to match -- but the update is INCOMPLETE: "
            f"some sites were missed. Examine the working tree and list EVERY site (override, implementation, "
            f"or call site) that still needs to be updated for this signature change.")

def files_of(sites):
    return {s.rsplit(":", 1)[0] for s in sites}

def run_opus(corpus, method, decl):
    p = ("TOOLS: ripgrep/grep/find and file reads only.\n" + prompt_for(method, decl) + "\n" + CONTRACT)
    try:
        r = sh(["claude", "-p", p, "--model", "opus", "--output-format", "json",
            "--dangerously-skip-permissions", "--allowedTools",
            "Read", "Grep", "Glob", "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)", "Bash(git:*)"], corpus, timeout=1200)
    except subprocess.TimeoutExpired:
        return {"sites": [], "error": "timeout-1200s"}
    try:
        j = json.loads(r.stdout)
        ans = Answer.parse(j.get("result", ""))
        u = j.get("usage") or {}
        return {"sites": [f"{s.relpath}:{s.symbol}" for s in ans.sites],
                "tokens": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0),
                "turns": j.get("num_turns")}
    except Exception as e:
        return {"sites": [], "error": str(e)[:200]}

def run_mason(corpus, method, decl):
    try:
        r = sh([MASON, "--dir", str(corpus), "--model", LOCAL, "--yes", "--json",
                "--max-turns", "20", CONTRACT + prompt_for(method, decl)], corpus, timeout=1500)
    except subprocess.TimeoutExpired:
        return {"sites": [], "error": "timeout-1500s"}
    sites = []
    for ln in (r.stderr or "").split("\n"):
        m = re.match(r"^\s{2,}(\S+\.(?:java|go|ts|py))\s{2,}(\S+)$", ln)
        if m:
            sites.append(f"{m.group(1)}:{m.group(2).rsplit('.',1)[-1]}")
    try:
        j = json.loads(r.stdout)
        ans = Answer.parse(j.get("reply", ""))
        for s in ans.sites:
            e = f"{s.relpath}:{s.symbol}"
            if e not in sites: sites.append(e)
        u = j.get("usage") or {}
        return {"sites": sites, "tokens": (u.get("inputTokens") or 0) + (u.get("cacheRead") or 0)}
    except Exception as e:
        return {"sites": sites, "error": str(e)[:200]}

def main():
    for task, (decl, decl_re, decl_new, method, comment) in CFG.items():
        tj = json.loads((HARNESS/f"tasks/{task}.json").read_text())
        corpus = Path(tj["workdir"] or tj["repo"])
        gt_files = sorted({s.rsplit(":", 1)[0] for s in tj["ground_truth"]} - {decl})
        rng = random.Random((hash(task) & 0xffff) ^ 7)
        for trial in (1, 2):
            outf = OUT/f"{task}.t{trial}.json"
            upd = sorted(f for f in gt_files if rng.random() < 0.5)  # consume rng deterministically FIRST
            if outf.exists():
                print(f"cached {outf.name}", flush=True); continue
            forgot = [f for f in gt_files if f not in upd]
            sh(["git", "checkout", "-q", tj["pin"]], corpus)
            sh(["git", "checkout", "-q", "--", "."], corpus)
            dp = corpus/decl
            srct = dp.read_text(encoding="utf-8", errors="replace")
            new = re.sub(decl_re, decl_new, srct, count=1)
            assert new != srct, f"{task}: decl pattern did not match"
            dp.write_text(new, encoding="utf-8")
            for f in upd:
                touch_calls(corpus/f, method, comment)
            rec = {"task": task, "trial": trial, "forgot": len(forgot), "updated": len(upd)}
            for arm, fn in (("opus", run_opus),):  # mason arm dropped: wrapper artifact (see diagnosis); engine verify is the product path
                res = fn(corpus, method, decl)
                rep = files_of(res["sites"])
                rec[arm] = {"caught": len([f for f in forgot if f in rep]),
                            "false": len([f for f in upd if f in rep]),
                            "n_sites": len(res["sites"]), "tokens": res.get("tokens"),
                            "error": res.get("error")}
                print(f"{task} t{trial} {arm}: caught {rec[arm]['caught']}/{len(forgot)} false {rec[arm]['false']} tok {res.get('tokens')}", flush=True)
            sh(["git", "checkout", "-q", "--", "."], corpus)
            outf.write_text(json.dumps(rec, indent=2))
    print("done")

main()
