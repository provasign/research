#!/usr/bin/env python3
"""Census: how often does a real signature change require edits OUTSIDE the
compile/test feedback loop (examples/, docs/, benchmarks/, scripts/ ...)?

Prism's real wins on the wide bed were sites agents skip because nothing
fails when they are missed (click examples/ overrides). A harder wide bed
only makes sense if such changes are common in real history.

For each non-merge commit in the last --max commits:
  - find callables whose definition line changed parameters but kept the
    name (Python def, JS/TS function/method, Go func, Java method, Rust fn);
  - linked files = changed files whose changed lines mention that name;
  - classify each linked file: src | test | feedback-gap (examples, docs,
    benchmarks, scripts, tutorials, playground, samples, demo, README).
A candidate has >= --min-linked linked files, >= 1 src and >= 1 gap file.

Memory: one `git log -p` stream per repo, one commit held at a time. A commit
stops being stored once it exceeds MAX_FILES files or MAX_CHANGED_LINES lines
(repo-wide reformats run to hundreds of MB), lines over MAX_LINE_LEN chars are
dropped, and the run aborts if its own RSS passes --max-rss-mb. Results are
written after every repo, so an abort keeps what finished.
Usage: census_feedback_gap.py <repo>... [--max 3000] [--out file.json]
"""
import json, os, re, resource, subprocess, sys, argparse
from collections import Counter

DEF = {
    '.py': re.compile(r'^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\((.*)'),
    '.js': re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:function\s+([A-Za-z_$][\w$]*)|([A-Za-z_$][\w$]*)\s*\()\s*\(?(.*)'),
    '.ts': re.compile(r'^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*(?:function\s+([A-Za-z_$][\w$]*)|([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\()\s*\(?(.*)'),
    '.go': re.compile(r'^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\((.*)'),
    '.java': re.compile(r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized|default)\s+)*[\w<>\[\],.? ]+\s+([a-z]\w*)\s*\((.*)'),
}
DEF['.rs'] = re.compile(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:const\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+([A-Za-z_]\w*)\s*(?:<[^(]*>)?\s*\((.*)')
DEF['.tsx'] = DEF['.ts']; DEF['.mjs'] = DEF['.js']; DEF['.jsx'] = DEF['.js']
KEYWORDS = {'if', 'for', 'while', 'switch', 'catch', 'return', 'function', 'new', 'super', 'this', 'constructor', 'main', 'init', '__init__', 'test', 'setUp', 'run', 'get', 'set'}
GAP = re.compile(r'(^|/)(examples?|docs?|documentation|benchmarks?|bench|scripts?|tutorials?|playground|samples?|demos?|cookbook)(/|$)|(^|/)README(\.(md|rst|txt|markdown|mdx))?$', re.I)
TEST = re.compile(r'(^|/)(tests?|testing|__tests__|spec|testdata)(/|$)|(_test\.go|Test\.java|\.test\.[jt]sx?|\.spec\.[jt]sx?|(^|/)test_[^/]*\.py)$', re.I)

MIN_FILES, MAX_FILES = 3, 60
MAX_CHANGED_LINES = 20000
MAX_LINE_LEN = 400  # minified/generated lines; also bounds regex backtracking
COMMIT = '\x01COMMIT '

def ext(p):
    m = re.search(r'(\.[A-Za-z]+)$', p)
    return m.group(1) if m else ''

def kind(p):
    if GAP.search(p): return 'gap'
    if TEST.search(p): return 'test'
    return 'src'

def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == 'darwin' else r / 1024

def commits(repo, n):
    """Yield (sha, files) per commit; files is None when the commit is skipped for size."""
    p = subprocess.Popen(['git', '-C', repo, 'log', '--no-merges', '-n', str(n), '-p', '--unified=0',
                          '--no-renames', '--no-color', '--no-ext-diff', f'--format={COMMIT}%H'],
                         stdout=subprocess.PIPE, text=True, errors='replace', bufsize=1 << 16)
    sha, files, cur, nlines, skip = None, {}, None, 0, False
    try:
        for line in p.stdout:
            if line.startswith(COMMIT):
                if sha:
                    yield sha, None if skip or len(files) < MIN_FILES else files
                sha, files, cur, nlines, skip = line[len(COMMIT):].strip(), {}, None, 0, False
                continue
            if skip:
                continue
            if line.startswith('+++ '):
                cur = line[6:].rstrip('\n') if line.startswith('+++ b/') else None
                if cur:
                    files[cur] = {'-': [], '+': []}
                    if len(files) > MAX_FILES:
                        skip, files = True, {}
            elif cur and line[:1] in ('+', '-') and not line.startswith('---'):
                nlines += 1
                if nlines > MAX_CHANGED_LINES:
                    skip, files = True, {}
                elif len(line) <= MAX_LINE_LEN:
                    files[cur][line[0]].append(line[1:].rstrip('\n'))
        if sha:
            yield sha, None if skip or len(files) < MIN_FILES else files
    finally:
        p.stdout.close()
        p.kill()
        p.wait()

def analyze(sha, files):
    changed_sigs = set()
    for f, ch in files.items():
        rx = DEF.get(ext(f))
        if not rx: continue
        def sigs(lines):
            d = {}
            for l in lines:
                m = rx.match(l)
                if m:
                    name = next((g for g in m.groups()[:-1] if g), None)
                    if name and name not in KEYWORDS and len(name) > 3:
                        d.setdefault(name, set()).add(re.sub(r'\s+', '', m.groups()[-1])[:120])
            return d
        old, new = sigs(ch['-']), sigs(ch['+'])
        for name in old.keys() & new.keys():
            if old[name] != new[name]:
                changed_sigs.add(name)
    out = []
    for name in changed_sigs:
        word = re.compile(r'\b' + re.escape(name) + r'\b')
        linked = [f for f, ch in files.items() if any(word.search(l) for l in ch['-'] + ch['+'])]
        kinds = Counter(kind(f) for f in linked)
        out.append({'sha': sha, 'name': name, 'linked': len(linked), 'kinds': dict(kinds),
                    'gap_files': [f for f in linked if kind(f) == 'gap'][:6]})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('repos', nargs='+'); ap.add_argument('--max', type=int, default=3000)
    ap.add_argument('--min-linked', type=int, default=3); ap.add_argument('--out')
    ap.add_argument('--max-rss-mb', type=int, default=1024)
    a = ap.parse_args()
    report = json.load(open(a.out)) if a.out and os.path.exists(a.out) else {}
    for repo in a.repos:
        name = repo.rstrip('/').split('/')[-1]
        if name in report:
            print(f'{name:28} already done, skipping', flush=True)
            continue
        n, skipped, sig_changes, cands = 0, 0, 0, []
        for sha, files in commits(repo, a.max):
            n += 1
            if files is None:
                skipped += 1
                continue
            for r in analyze(sha, files):
                if r['linked'] >= a.min_linked:
                    sig_changes += 1
                    if r['kinds'].get('gap') and r['kinds'].get('src'):
                        cands.append(r)
            if n % 200 == 0 and rss_mb() > a.max_rss_mb:
                sys.exit(f'ABORT: rss {rss_mb():.0f} MB > {a.max_rss_mb} MB in {name} after {n} commits')
        report[name] = {'commits': n, 'skipped_size': skipped, 'wide_sig_changes': sig_changes,
                        'with_gap_sites': len(cands), 'candidates': cands}
        print(f'{name:28} commits {n:5}  wide signature changes {sig_changes:4}  with feedback-gap sites {len(cands):3}  '
              f'(peak rss {rss_mb():.0f} MB)', flush=True)
        if a.out:
            json.dump(report, open(a.out, 'w'), indent=1)

if __name__ == '__main__':
    main()
