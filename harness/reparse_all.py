import json,glob,sys
from pathlib import Path
sys.path.insert(0,'.')
from schema import Answer, Task
from score import score
tasks={p.stem:Task.load(p) for p in Path('tasks').glob('*.json')}
changed=0; total=0
for f in glob.glob('runs/**/[TGV].t?.json',recursive=True):
    d=json.load(open(f))
    if d.get('status')!='ok': continue
    t=tasks.get(d['task_id'])
    if not t: continue
    tf=f[:-5]+'.transcript.txt'
    if not Path(tf).exists(): continue
    total+=1
    ans=Answer.parse(Path(tf).read_text())
    card=score(t, ans, d['arm'], d['trial']); old=d['recall']
    if abs(card.recall-old)>1e-9:
        changed+=1; d.update(card.to_dict())
        d['answer']={'sites':[str(s) for s in ans.sites],'complete':ans.complete,'unresolved':ans.unresolved}
        Path(f).write_text(json.dumps(d,indent=2)+'\n')
        print(f"  FIXED {f}: recall {old} -> {card.recall}")
print(f"reparsed {total} ok runs, {changed} changed")
