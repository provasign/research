"""Oops-pair miner: real-world recall for prism verify.

Find NATURALLY-OCCURRING incomplete changes — a commit A that changed a
method signature, followed (within a window) by a commit B that fixed a
CALL SITE of that same method A forgot. B is the human noticing "oops, I
missed a caller." At commit A, the tree is genuinely incomplete: the
contract changed, the caller B later fixes is still on the old shape.

For each pair we replay verify AT commit A against A's parent and ask: does
verify flag the site B later fixed? That is the real-world recall number —
would the gate have caught this before it merged, days before the human did.

No seeding, no synthetic edits. The ground truth is what a real developer
actually forgot and had to come back for.

Usage: python oops_pairs.py <repo-path> [--window 8] [--max 400] [--lang java|go]
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

PRISM = str(Path.home() / "bin" / "prism")


def git(repo, *a, **kw):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, **kw).stdout


# A method/function DECLARATION whose parameter list we can extract. Java:
# "<modifiers> ret name(...)". Go: "func (recv) name(...)" or "func name(...)".
JAVA_DECL = re.compile(r"^\s*(?:public|private|protected|static|final|abstract|synchronized|\s)+[\w<>\[\],.\s]+?\b(\w+)\s*\(")
GO_DECL = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(")


TS_DECL = re.compile(r"^\s*(?:public|private|protected|static|async|abstract|readonly|export|\s)*\b(\w+)\s*\(")

def decl_name(line, lang):
    m = {"go": GO_DECL, "ts": TS_DECL}.get(lang, JAVA_DECL).match(line)
    if not m:
        return None
    name = m.group(1)
    if name in {"if", "for", "while", "switch", "catch", "return", "func",
                "function", "constructor", "get", "set", "new"}:
        return None
    # Reject CALLS: name preceded by '.', or an assignment / return before it.
    head = line[:m.start(1)]
    if head.rstrip().endswith("."):
        return None
    if "=" in head or "return " in line:
        return None
    # A real decl carries a type/modifier token before the name (Java/TS) or
    # is `func` (Go, already matched). Bare `name(` is a call statement.
    if lang != "go" and len(head.split()) < 1 and "(" in line[:line.find(name)+len(name)+2]:
        pass
    return name


def paramsig(line):
    i = line.find("(")
    if i < 0:
        return None
    depth, out = 0, []
    for c in line[i:]:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return re.sub(r"\s+", "", "".join(out))
        elif depth == 1:
            out.append(c)
    return None


def commit_diff(repo, sha):
    return git(repo, "show", "--no-color", "--unified=0", sha)


def sig_changes(repo, sha, lang):
    """Methods whose parameter list changed in this commit: name -> (old,new)."""
    diff = commit_diff(repo, sha)
    removed, added = {}, {}
    for ln in diff.splitlines():
        if ln.startswith("---") or ln.startswith("+++") or ln.startswith("@@"):
            continue
        if ln.startswith("-"):
            body = ln[1:]
            n = decl_name(body, lang)
            if n:
                p = paramsig(body)
                if p is not None:
                    removed[n] = p
        elif ln.startswith("+"):
            body = ln[1:]
            n = decl_name(body, lang)
            if n:
                p = paramsig(body)
                if p is not None:
                    added[n] = p
    out = {}
    for n in removed:
        if n in added and removed[n] != added[n]:
            out[n] = (removed[n], added[n])
    return out


CALL_RE_CACHE = {}


def call_site_files(repo, sha, method):
    """Files where THIS commit changed lines that CALL `method(` without
    changing method's own declaration."""
    diff = commit_diff(repo, sha)
    files, cur = set(), None
    call = re.compile(r"[^\w.]" + re.escape(method) + r"\s*\(")
    for ln in diff.splitlines():
        if ln.startswith("+++ b/"):
            cur = ln[6:]
        elif (ln.startswith("+") or ln.startswith("-")) and cur and not ln.startswith("+++") and not ln.startswith("---"):
            body = ln[1:]
            if decl_name(body, "java") == method or decl_name(body, "go") == method:
                continue  # this line is the declaration, not a call
            if call.search(" " + body):
                files.add(cur)
    return files


FIXUP = re.compile(r"\b(fix|missed|forgot|also update|also fix|follow.?up|remaining|left over|leftover|overlooked|straggler|adjust caller|update caller|broken build|compile)\b", re.I)


def mine(repo, lang, window, maxc):
    shas = git(repo, "log", "--first-parent", f"-n{maxc}", "--format=%H").split()
    # newest first; index by position for windowing
    pairs = []
    # Pre-compute signature changes per commit (bounded).
    sigc = {}
    for s in shas:
        sc = sig_changes(repo, s, lang)
        if sc:
            sigc[s] = sc
    for i, sA in enumerate(shas):
        if sA not in sigc:
            continue
        for method, (oldp, newp) in sigc[sA].items():
            # look at LATER commits (earlier in the newest-first list => smaller i)
            for j in range(max(0, i - window), i):
                sB = shas[j]
                if sB in sigc and method in sigc[sB]:
                    continue  # B re-changed the decl; not a pure caller fix
                subj = git(repo, "log", "-1", "--format=%s", sB).strip()
                cf = call_site_files(repo, sB, method)
                if not cf:
                    continue
                if len(method) < 4 or method in {"async","await","expect","stats","props","value","items","index","event","error","result","options","params","config","data"}:
                    continue
                pairs.append({"A": sA, "B": sB, "method": method,
                              "oldParams": oldp, "newParams": newp,
                              "bSubject": subj[:100], "bFixesFiles": sorted(cf),
                              "fixupWord": bool(FIXUP.search(subj)),
                              "gap": i - j})
    return pairs


def replay(repo, pair, lang):
    """Checkout commit A (contract change, callers B fixes still unfixed),
    run verify vs A^, check whether B's fixed files appear as missed."""
    sA = pair["A"]
    with tempfile.TemporaryDirectory() as td:
        wt = str(Path(td) / "wt")
        git(repo, "worktree", "add", "-q", "--detach", wt, sA)
        try:
            subprocess.run([PRISM, "index", wt], capture_output=True, timeout=600)
            r = subprocess.run([PRISM, "verify", wt, "--base", sA + "^", "--json"],
                               capture_output=True, text=True, timeout=600)
            try:
                v = json.loads(r.stdout)
            except Exception:
                return {"error": (r.stdout + r.stderr)[-200:]}
            missed_files = {ms["file"] for ms in v.get("missedSites") or []}
            missed_methods = {ms.get("symbol") for ms in v.get("missedSites") or []}
            want = set(pair["bFixesFiles"])
            hit = {f for f in want if any(f.endswith(m) or m.endswith(f) or Path(f).name == Path(m).name for m in missed_files)}
            return {"verdict": v.get("verdict"),
                    "verifyFlagged": pair["method"] in missed_methods or len(hit) > 0,
                    "bFilesHitByVerify": sorted(hit), "bFilesTotal": len(want),
                    "nMissed": len(v.get("missedSites") or [])}
        finally:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt],
                           capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--window", type=int, default=8)
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--lang", default="java")
    ap.add_argument("--replay", action="store_true")
    a = ap.parse_args()
    pairs = mine(a.repo, a.lang, a.window, a.max)
    print(f"# {len(pairs)} candidate oops-pairs in last {a.max} commits "
          f"({sum(p['fixupWord'] for p in pairs)} with fixup-word subjects)", flush=True)
    for p in pairs:
        print(f"  {p['method']:24} A={p['A'][:9]} B={p['B'][:9]} gap={p['gap']} "
              f"fixup={p['fixupWord']} | {p['bSubject']}", flush=True)
    if a.replay and pairs:
        print("\n# replaying verify at each A ...", flush=True)
        flagged = total = 0
        for p in pairs:
            res = replay(a.repo, p, a.lang)
            total += 1
            ok = res.get("verifyFlagged")
            flagged += bool(ok)
            print(f"  {p['method']:20} A={p['A'][:9]} verdict={res.get('verdict')} "
                  f"flagged={ok} hit={res.get('bFilesHitByVerify')} err={res.get('error','')}", flush=True)
        print(f"\n# REAL-WORLD RECALL: verify flagged the forgotten site in {flagged}/{total} real oops-pairs", flush=True)


if __name__ == "__main__":
    main()
