import json, sys
from pathlib import Path
ROOT = Path.home() / ".claude" / "projects"
sids = {
    "pr6052": "6f0ab867-77b2-4d90-b586-b4acc1619101",
    "pr3504": "170352dc-8681-47d9-9309-bd15e27b21d7",
    "pr6044": "9927efc3-1eb3-4351-9f06-526c0e7dff1f",
    "pr6018": "73a40701-cbaf-4d98-bf93-7c6fe358fd83",
}
def text_of(msg):
    out=[]
    for c in (msg.get("content") or []):
        if isinstance(c, dict):
            if c.get("type")=="text": out.append(c["text"])
            elif c.get("type")=="tool_use": out.append(f"[TOOL_USE {c.get('name')} {json.dumps(c.get('input'))[:200]}]")
            elif c.get("type")=="tool_result":
                ct=c.get("content")
                s = ct if isinstance(ct,str) else json.dumps(ct)[:300] if ct else ""
                out.append(f"[TOOL_RESULT {s[:300]}]")
    return "\n".join(out)

for label, sid in sids.items():
    f = list(ROOT.glob(f"*/{sid}.jsonl"))[0]
    lines = f.read_text(errors="ignore").splitlines()
    print(f"\n{'='*20} {label} ({sid}) — last 6 events {'='*20}")
    events = []
    for line in lines:
        try: j=json.loads(line)
        except Exception: continue
        if j.get("type") in ("assistant","user"):
            events.append(j)
    for j in events[-6:]:
        msg = j.get("message") or {}
        role = msg.get("role","?")
        print(f"--- {role} ---")
        print(text_of(msg)[:600])
