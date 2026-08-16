#!/usr/bin/env python3
"""Why can't these tasks be scored? Run gold against the explicit F2P node
ids in the official image and classify the failure. Docker only, no API."""
import json,sys,tempfile,subprocess,os,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import docker_eval as de

sc=json.load(open(sys.argv[1])); tasks={t['instance_id']:t for t in json.load(open(sys.argv[2]))}
bad=[k for k,v in sc.items() if not v['scoreable']]
out={}
for i,tid in enumerate(bad,1):
    t=tasks[tid]; nodes=' '.join(f"'{n}'" for n in t['FAIL_TO_PASS'][:20])
    img=de.official_image(tid)
    script=(f"cd /testbed; git checkout -f -q {t['base_commit']} 2>&1|tail -1; "
            "git apply --3way /tmp/test.patch >/dev/null 2>&1; git apply --3way /tmp/gold.patch >/dev/null 2>&1; "
            f"python -m pytest {nodes} --tb=line -q -p no:cacheprovider -o addopts='' 2>&1 | tail -25")
    d=tempfile.mkdtemp()
    open(os.path.join(d,'test.patch'),'w').write(t.get('test_patch') or '')
    open(os.path.join(d,'gold.patch'),'w').write(t['patch'])
    try:
        r=subprocess.run(['docker','run','--rm','--platform','linux/amd64',
            '-v',f'{d}/test.patch:/tmp/test.patch:ro','-v',f'{d}/gold.patch:/tmp/gold.patch:ro',
            img,'bash','-lc',script],capture_output=True,text=True,timeout=1500).stdout
    except Exception as e:
        r=f"HARNESS ERROR {e}"
    passed = re.search(r'(\d+) passed', r)
    if 'No module named' in r or 'ModuleNotFoundError' in r: cat='missing dependency'
    elif re.search(r'networking\.py|ConnectionError|getaddrinfo|Temporary failure|api\.telegram|NewConnectionError|Max retries', r): cat='TEST NEEDS NETWORK'
    elif 'no tests ran' in r or 'ERROR' in r and 'error' in r.lower() and not passed: cat='collection error'
    elif passed and not re.search(r'\d+ failed', r): cat='PASSES (was a module-scope problem)'
    elif re.search(r'\d+ failed', r): cat='gold genuinely fails F2P'
    else: cat='other'
    out[tid]=cat
    print(f"[{i:2}/{len(bad)}] {cat:34} {tid}", flush=True)
    json.dump(out, open(sys.argv[3],'w'), indent=1)
import collections
print("\n"+str(dict(collections.Counter(out.values()))))
