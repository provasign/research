#!/usr/bin/env python3
"""Score `grove change-impact` (the real engine op) against the Spoon-oracle
ground truth for the 6 jackson tasks. Eval scope matches GT scope (src/main)."""
import json, subprocess, sys

GROVE = "/Users/tapabratapal/bin/grove"
CORPUS = "/Users/tapabratapal/gvg-corpus/jackson-databind"
TASKDIR = "/Users/tapabratapal/Projects/provasign/research/harness/tasks"

TASKS = [
    ("jackson-jsonnode-get", "JsonNode.get(int)"),
    ("jackson-settable-set", "SettableBeanProperty.set(Object, Object)"),
    ("jackson-writetypeprefix", "TypeSerializer.writeTypePrefix(JsonGenerator, WritableTypeId)"),
    ("jackson-serializewithtype", "JsonSerializer.serializeWithType(T, JsonGenerator, SerializerProvider, TypeSerializer)"),
    ("jackson-deserialize", "JsonDeserializer.deserialize(JsonParser, DeserializationContext)"),
    ("jackson-serialize", "JsonSerializer.serialize(T, JsonGenerator, SerializerProvider)"),
]

def leaf(qualified):
    return qualified.rsplit(".", 1)[-1]

print(f"{'task':28s} {'query':>4s} {'GT':>4s} {'pred':>5s} {'hit':>4s} {'recall':>7s} {'prec':>6s}")
rows = []
for taskfile, query in TASKS:
    task = json.load(open(f"{TASKDIR}/{taskfile}.json"))
    gt = set()
    for site in task["ground_truth"]:
        f, m = site.rsplit(":", 1)
        gt.add((f, m))

    out = subprocess.run([GROVE, "change-impact", query, CORPUS],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print(f"{taskfile:28s} ERROR: {out.stderr.strip()[:80]}")
        continue
    r = json.loads(out.stdout)
    pred = set()
    for group in ("Declarations", "Family", "Callers"):
        for s in r.get(group) or []:
            if "/test/" in s["filePath"]:
                continue  # GT scope is src/main; tests are correct-but-unscored
            pred.add((s["filePath"], leaf(s["qualifiedName"])))

    hit = gt & pred
    recall = len(hit) / len(gt) if gt else 0
    prec = len(hit) / len(pred) if pred else 0
    rows.append((taskfile, len(gt), recall, prec))
    print(f"{taskfile:28s} {'':4s} {len(gt):4d} {len(pred):5d} {len(hit):4d} {recall:7.3f} {prec:6.3f}")
    for f, m in sorted(gt - pred)[:6]:
        print(f"    MISS {f.split('/')[-1]}:{m}")
    extra = sorted(pred - gt)
    if extra:
        print(f"    ({len(extra)} extra, e.g. {', '.join(f.split('/')[-1]+':'+m for f,m in extra[:4])})")

if rows:
    mr = sum(r[2] for r in rows) / len(rows)
    mp = sum(r[3] for r in rows) / len(rows)
    print(f"\nmean recall {mr:.3f} | mean precision {mp:.3f}")
