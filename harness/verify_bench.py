"""Verify-moment benchmark: does `prism verify` catch deliberately incomplete
edits on the 9 real oracle-scored corpora? Engine-level, no LLM.

Simulation per trial (file granularity — the dominant real miss pattern is a
forgotten FILE): mutate the target declaration's parameter list (registers as
a signature change), then "update" a random ~50% subset of the ground-truth
FILES by touching every call line naming the method (line-count-preserving
comment append); the rest are FORGOTTEN. Run `prism verify --json` and score:

  catch    — forgotten GT file flagged with >=1 missed site
  false    — fully-updated GT file flagged
Plus one complete-update control trial per task (all files touched):
anything flagged there in a GT file is a false positive; verdict should not
be "incomplete" on account of GT files.
"""
import json, random, re, subprocess, sys
from pathlib import Path

HARNESS = Path.home()/"Projects/provasign/research/harness"
PRISM = "/tmp/prism-task"
OUT = HARNESS/"runs/verify-bench"; OUT.mkdir(parents=True, exist_ok=True)

# task -> (decl_relpath, decl_regex, decl_replacement, method_leaf, comment)
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

def run_trial(task, corpus, gt_files, decl, decl_re, decl_new, method, comment, updated_files):
    # 1. mutate the declaration
    dp = corpus/decl
    src = dp.read_text(encoding="utf-8", errors="replace")
    new = re.sub(decl_re, decl_new, src, count=1)
    assert new != src, f"{task}: decl pattern did not match"
    dp.write_text(new, encoding="utf-8")
    # 2. "update" chosen files
    for f in updated_files:
        touch_calls(corpus/f, method, comment)
    # 3. index + verify
    sh([PRISM, "index", "."], corpus)
    r = sh([PRISM, "verify", ".", "--json"], corpus)
    try:
        v = json.loads(r.stdout)
    except Exception:
        return {"error": (r.stdout + r.stderr)[-400:]}
    missed_files = set()
    for ms in v.get("missedSites") or []:
        missed_files.add(ms["file"])
    return {"verdict": v.get("verdict"), "missedFiles": sorted(missed_files),
            "nMissedSites": len(v.get("missedSites") or []),
            "unverified": len(v.get("unverifiedSeeds") or [])}

def main():
    results = []
    for task, (decl, decl_re, decl_new, method, comment) in CFG.items():
        tj = json.loads((HARNESS/f"tasks/{task}.json").read_text())
        corpus = Path(tj["workdir"] or tj["repo"])
        sh(["git", "checkout", "-q", tj["pin"]], corpus)
        sh(["git", "checkout", "-q", "--", "."], corpus)
        gt_files = sorted({s.rsplit(":", 1)[0] for s in tj["ground_truth"]} - {decl})
        rng = random.Random(hash(task) & 0xffff)
        trials = []
        for trial in range(3):
            sh(["git", "checkout", "-q", "--", "."], corpus)
            upd = sorted(f for f in gt_files if rng.random() < 0.5)
            forgot = [f for f in gt_files if f not in upd]
            rec = run_trial(task, corpus, gt_files, decl, decl_re, decl_new, method, comment, upd)
            if "error" in rec:
                trials.append({"trial": trial, "error": rec["error"]}); continue
            mf = {Path(f).name for f in rec["missedFiles"]}
            caught = [f for f in forgot if Path(f).name in mf]
            false_ = [f for f in upd if Path(f).name in mf]
            trials.append({"trial": trial, "verdict": rec["verdict"],
                           "forgot": len(forgot), "caught": len(caught),
                           "falseFlag": len(false_), "falseFiles": false_[:4],
                           "unverified": rec["unverified"]})
            print(f"{task:28} t{trial}: verdict={rec['verdict']:<11} forgot={len(forgot):>2} "
                  f"caught={len(caught):>2} false={len(false_)}", flush=True)
        # control: update everything
        sh(["git", "checkout", "-q", "--", "."], corpus)
        rec = run_trial(task, corpus, gt_files, decl, decl_re, decl_new, method, comment, gt_files)
        if "error" not in rec:
            mf = {Path(f).name for f in rec["missedFiles"]}
            false_ = [f for f in gt_files if Path(f).name in mf]
            trials.append({"trial": "control", "verdict": rec["verdict"], "falseFlag": len(false_)})
            print(f"{task:28} control: verdict={rec['verdict']:<11} falseGTflags={len(false_)}", flush=True)
        else:
            trials.append({"trial": "control", "error": rec["error"]})
            print(f"{task:28} control: ERROR {rec['error'][:120]}", flush=True)
        sh(["git", "checkout", "-q", "--", "."], corpus)
        results.append({"task": task, "gtFiles": len(gt_files), "trials": trials})
    (OUT/"results.json").write_text(json.dumps(results, indent=1))
    # summary
    tot_f = tot_c = tot_x = 0
    for r in results:
        for t in r["trials"]:
            if t.get("trial") == "control" or "error" in t: continue
            tot_f += t["forgot"]; tot_c += t["caught"]; tot_x += t["falseFlag"]
    print(f"\nTOTAL: forgotten-file catch {tot_c}/{tot_f}  false flags on updated files: {tot_x}")

main()
