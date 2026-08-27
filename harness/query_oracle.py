#!/usr/bin/env python3
"""Offline recall oracle for prism's context-assembly engine.

For each gold-validated task: index the base worktree, run the query engine,
and score the delivered context against the GOLD patch — the ground truth for
what a correct fix actually needed. Deterministic, no agents, immune to the
~50% per-cell agent-noise floor that invalidated delivery A/Bs (2026-08-26).

Two term modes per task, separating the two ways the engine can fail:
  realistic — identifier-like tokens from the issue TITLE (what an agent
              would plausibly pass). End-to-end score.
  oracle    — the gold hunks' enclosing symbol names (perfect terms).
              Engine ceiling: expansion/windowing quality alone.

Metrics per task and aggregate:
  recall     — fraction of gold hunks whose region (any stripped source line
               within ±3 of the hunk start) appears in the delivered context
  oversupply — delivered bytes / should-need bytes (gold regions ±30 lines)

Usage: python3 query_oracle.py [--prism BIN] [--slice slice-java12.json] [--out FILE]
"""
import json, re, subprocess, os, sys, tempfile, shutil, argparse
import faulthandler
# The wedge diagnostic: if any stage blocks >120s, dump every thread's exact
# Python stack and exit — turns a silent hang into a stack trace.
faulthandler.dump_traceback_later(420, exit=True)

H = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser('~/.cache/prism-research/swebench-repos')


def run_capped(cmd, cwd=None, timeout=180):
    """subprocess.run with FILE capture. Pipe capture deadlocks with prism:
    the CLI's persistent-ledger daemon inherits the pipe fds and holds them
    open after the CLI exits, so communicate() blocks forever — the cause of
    all three oracle hangs (2026-08-26). A file handle cannot block."""
    import tempfile as _tf
    with _tf.TemporaryFile() as out, _tf.TemporaryFile() as err:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=err)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait()
            raise RuntimeError(f'timeout after {timeout}s: {cmd[1]}')
        out.seek(0); err.seek(0)
        return rc, out.read().decode(errors='replace'), err.read().decode(errors='replace')

def run_query(prism, cwd, task, terms, timeout=180):
    """CLI query with a hard timeout. The MCP-client driver hung twice
    (blocked readline; un-timeouted cleanup); the CLI does the same engine
    work with none of the protocol surface to wedge. Requires the
    2026-08-26 renderer fix (50f06c3) — before it, --format text printed
    file paths and discarded the content."""
    rc, out, err = run_capped([prism, 'query', task, '--terms', ','.join(terms), '--format', 'text'],
                              cwd=cwd, timeout=timeout)
    if rc != 0:
        raise RuntimeError((err or 'query failed')[:100])
    return out

def show(repo, sha, path):
    r = subprocess.run(['git', '-C', repo, 'show', f'{sha}:{path}'], capture_output=True, text=True, timeout=60)
    return r.stdout

def gold_hunks(t):
    """[(file, anchor_line)] for src hunks; skips release-notes etc.

    anchor = the MIDDLE of the old-file range, not its start: a hunk that
    inserts a method starts on the blank line after the previous method, and
    scanning up from there attributed a fix to the WRONG neighbour
    (EnumDeserializer: extractor said _getToStringLookup, the fix was in
    useNullForUnknownEnum one method down — cost a perfect cell)."""
    out, cur = [], None
    for line in t['patch'].split('\n'):
        m = re.match(r'^\+\+\+ b/(.+)$', line)
        if m: cur = m.group(1); continue
        m = re.match(r'^@@ -(\d+),?(\d*)', line)
        if m and cur and ('/src/' in '/' + cur or cur.startswith('src/')):
            start = int(m.group(1)); n = int(m.group(2) or 1)
            out.append((cur, start + max(n // 2, 1)))
    return out

def title_terms(t):
    toks = re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', t['problem_statement'].split('\n')[0])
    return [x for x in toks if any(c.isupper() for c in x[1:]) or '_' in x][:3]

def oracle_terms(repo, sha, hunks):
    """Enclosing symbol names for each gold hunk, from a crude signature scan
    upward from the hunk line (method/class declaration lines)."""
    # LINEAR scan only. The first version used
    #   ^\s*(?:public|...|\w[\w<>\[\],\s]*)*\s*(\w+)\(
    # — a nested quantifier over overlapping alternatives, which went
    # EXPONENTIAL on a line in jackson-core-1309's gold file and spun the
    # regex engine for 10+ minutes. That single line was every "hang" in
    # oracle runs 1-6 (confirmed by faulthandler stack dump, 2026-08-26);
    # three infrastructure theories were wrong. Never put a repeated group
    # around an alternation whose branches can match the same text.
    # QUALIFIED terms (Type.member): bare names like `clear` fan out across
    # the whole repo and the gold declaration loses the seed race; the file's
    # primary type disambiguates. Declaration detection requires a
    # DECLARATION-shaped line (modifier-led), not merely "contains ident(" —
    # the looser rule walked past the real method into a neighbour and
    # produced terms like writeEndElement for a writeNumber fix.
    names = []
    kw = {'if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'throw',
          'else', 'do', 'super', 'this', 'assert'}
    decl = re.compile(r'^(?:public|protected|private)\b[^=;{]*?([A-Za-z_][A-Za-z0-9_]*)\s*\(')
    for f, ln in hunks:
        body = show(repo, sha, f).split('\n')
        typ = f.rsplit('/', 1)[-1].removesuffix('.java')
        found = None
        for i in range(min(ln, len(body)) - 1, -1, -1):
            st = body[i].strip()
            m = decl.match(st)
            if m and m.group(1) not in kw:
                found = m.group(1)
                break
            if st.startswith(('class ', 'interface ', 'enum ')) or ' class ' in st.split('//')[0]:
                break
        term = f"{typ}.{found}" if found else typ
        if term not in names:
            names.append(term)
    return names[:8]

def score(repo, sha, hunks, ctx):
    """(recall, delivered_bytes, need_bytes)"""
    covered = 0
    need = 0
    per_file_lines = {}
    for f, ln in hunks:
        body = per_file_lines.setdefault(f, show(repo, sha, f).split('\n'))
        probes = [l.strip() for l in body[max(0, ln - 3):ln + 4] if len(l.strip()) > 20]
        if any(p in ctx for p in probes): covered += 1
        for i in range(max(1, ln - 30), min(ln + 35, len(body) + 1)):
            need += len(body[i - 1]) + 1
    return (covered / max(len(hunks), 1), len(ctx), need)

def fmtrow(x):
    if not x: return '-'
    if 'error' in x: return 'ERR:' + x['error'][:30]
    return f"r={x['recall']} {x['oversupply']}x"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prism', default=os.path.expanduser('~/bin/prism'))
    ap.add_argument('--slice', default=os.path.join(H, 'runs/swebench-live/slice-java12.json'))
    ap.add_argument('--out', default=os.path.join(H, 'runs/swebench-live/query-oracle.json'))
    ap.add_argument('--only', default=None, help='run a single instance_id (per-task isolation driver)')
    a = ap.parse_args()
    tasks = json.load(open(a.slice))
    if a.only:
        tasks = [t for t in tasks if t['instance_id'] == a.only]
    results = []
    for t in tasks:
        hunks = gold_hunks(t)
        if not hunks:
            continue
        repo = os.path.join(CACHE, t['repo'].replace('/', '__'))
        wt = tempfile.mkdtemp(prefix='qoracle-')
        try:
            subprocess.run(['git', '-C', repo, 'worktree', 'add', '--detach', '--force', wt, t['base_commit']],
                           capture_output=True, check=True, timeout=120)
            print(f"  [{t['instance_id'][-25:]}] indexing…", flush=True)
            run_capped([a.prism, 'index', '.'], cwd=wt, timeout=600)
            row = {'instance_id': t['instance_id'], 'hunks': len(hunks)}
            for mode, terms in (('realistic', title_terms(t)),
                                ('oracle', oracle_terms(repo, t['base_commit'], hunks))):
                if not terms:
                    row[mode] = None; continue
                try:
                    ctx = run_query(a.prism, wt, t['problem_statement'].split('\n')[0][:80], terms)
                except Exception as e:
                    row[mode] = {'terms': terms, 'error': str(e)[:80]}
                    continue
                rec, dl, need = score(repo, t['base_commit'], hunks, ctx)
                row[mode] = {'terms': terms, 'recall': round(rec, 3),
                             'delivered': dl, 'need': need,
                             'oversupply': round(dl / max(need, 1), 1)}
            results.append(row)
            r, o = row.get('realistic'), row.get('oracle')
            print(f"{t['instance_id'][:40]:40} "
                  f"real: {fmtrow(r)}   oracle: {fmtrow(o)}", flush=True)
        finally:
            subprocess.run(['git', '-C', repo, 'worktree', 'remove', '--force', wt], capture_output=True, timeout=120)
            shutil.rmtree(wt, ignore_errors=True)
    agg = {}
    for mode in ('realistic', 'oracle'):
        rows = [r[mode] for r in results if r.get(mode) and 'recall' in r[mode]]
        if rows:
            agg[mode] = {'mean_recall': round(sum(x['recall'] for x in rows) / len(rows), 3),
                         'mean_oversupply': round(sum(x['oversupply'] for x in rows) / len(rows), 1),
                         'n': len(rows)}
    if a.only:
        with open(a.out + 'l', 'a') as fh:
            for r in results:
                fh.write(json.dumps(r) + '\n')
        return
    json.dump({'results': results, 'aggregate': agg}, open(a.out, 'w'), indent=1)
    print(f"\nAGGREGATE: {json.dumps(agg)}")
    print(f"wrote {a.out}")

if __name__ == '__main__':
    main()
