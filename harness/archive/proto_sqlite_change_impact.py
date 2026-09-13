#!/usr/bin/env python3
"""Throwaway prototype: can a traversal over Grove's existing index (grove.db)
reconstruct the Spoon-oracle ground truth for the 6 jackson tasks?

Algorithm (what graph-native change_impact would do):
  1. resolve root class + method (+ optional arity) -> declaration symbol(s)
  2. subtype closure over extends/implements edges (down the hierarchy)
  3. family = methods named <method> contained in closure classes,
     arity-filtered where the signature is parseable
  4. callers = inbound `calls` edges to declaration or any family member
  5. sites = {declaration, family, caller-enclosing-methods} as (file, method)

Scored vs task ground_truth (file:method).
"""
import json, re, sqlite3, sys
from collections import defaultdict

DB = "/Users/tapabratapal/gvg-corpus/jackson-databind/.grove/grove.db"
TASKDIR = "/Users/tapabratapal/Projects/provasign/research/harness/tasks"

TASKS = [
    # (task file, root class, method, arity or None)
    ("jackson-jsonnode-get", "JsonNode", "get", 1),   # get(int) -- overload!
    ("jackson-settable-set", "SettableBeanProperty", "set", None),
    ("jackson-writetypeprefix", "TypeSerializer", "writeTypePrefix", None),
    ("jackson-serializewithtype", "JsonSerializer", "serializeWithType", None),
    ("jackson-deserialize", "JsonDeserializer", "deserialize", 2),  # abstract 2-arg
    ("jackson-serialize", "JsonSerializer", "serialize", None),
]

con = sqlite3.connect(DB)
cur = con.cursor()

def leaf(qualified):
    return qualified.rsplit(".", 1)[-1]

def sig_arity(sig):
    """Best-effort param count from signature text; None if unparseable."""
    if not sig:
        return None
    m = re.search(r"\(([^)]*)\)", sig)
    if not m:
        return None  # truncated or '@Override'
    inner = m.group(1).strip()
    if not inner:
        return 0
    # strip generics so commas inside <> don't split
    depth, parts, cur_s = 0, 1, inner
    for ch in cur_s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 0:
            parts += 1
    return parts

def class_symbols(name):
    cur.execute(
        "SELECT id FROM symbols WHERE (qualified_name=? OR name=?) "
        "AND kind IN ('class','interface','type','struct')", (name, name))
    return [r[0] for r in cur.fetchall()]

def subtype_closure(roots):
    seen = set(roots)
    frontier = list(roots)
    while frontier:
        qmarks = ",".join("?" * len(frontier))
        cur.execute(
            f"SELECT DISTINCT from_node FROM edges WHERE edge_type IN "
            f"('extends','implements') AND to_node IN ({qmarks})", frontier)
        nxt = [r[0] for r in cur.fetchall() if r[0] not in seen]
        seen.update(nxt)
        frontier = nxt
    return seen

def contained_methods(class_ids, method):
    out = []
    ids = list(class_ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        qmarks = ",".join("?" * len(chunk))
        cur.execute(
            f"SELECT e.to_node, s.signature FROM edges e JOIN symbols s ON s.id=e.to_node "
            f"WHERE e.edge_type='contains' AND e.from_node IN ({qmarks}) "
            f"AND s.name=? AND s.kind IN ('method','function')", chunk + [method])
        out.extend(cur.fetchall())
    return out

def callers_of(target_ids):
    out = []
    ids = list(target_ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        qmarks = ",".join("?" * len(chunk))
        cur.execute(
            f"SELECT DISTINCT from_node FROM edges WHERE edge_type='calls' "
            f"AND to_node IN ({qmarks})", chunk)
        out.extend(r[0] for r in cur.fetchall())
    return out

def sym_site(sym_id):
    """symbol id -> (file, leaf method name)"""
    file_part, rest = sym_id.split("::", 1)
    qname = rest.rsplit("@", 1)[0]
    return (file_part, leaf(qname))

print(f"{'task':28s} {'GT':>4s} {'pred':>5s} {'hit':>4s} {'recall':>7s} {'prec':>6s}")
all_miss = {}
for taskfile, root, method, arity in TASKS:
    task = json.load(open(f"{TASKDIR}/{taskfile}.json"))
    gt = set()
    for site in task["ground_truth"]:
        f, m = site.rsplit(":", 1)
        gt.add((f, m))

    roots = class_symbols(root)
    closure = subtype_closure(roots)
    fam = contained_methods(closure, method)
    # arity filter: keep unparseable signatures (don't drop on missing info)
    fam_ids = [fid for fid, sig in fam
               if arity is None or sig_arity(sig) in (arity, None)]
    call_srcs = callers_of(fam_ids)

    pred = set()
    for fid in fam_ids:
        pred.add(sym_site(fid))
    for cid in call_srcs:
        pred.add(sym_site(cid))

    hit = gt & pred
    recall = len(hit) / len(gt) if gt else 0
    prec = len(hit) / len(pred) if pred else 0
    print(f"{taskfile:28s} {len(gt):4d} {len(pred):5d} {len(hit):4d} "
          f"{recall:7.3f} {prec:6.3f}")
    all_miss[taskfile] = sorted(gt - pred)

print("\n-- misses (GT sites the traversal did NOT find) --")
for t, misses in all_miss.items():
    if misses:
        print(f"\n{t}: {len(misses)} missed")
        for f, m in misses[:10]:
            print(f"   {f.split('/')[-1]}:{m}")
        if len(misses) > 10:
            print(f"   ... +{len(misses)-10} more")
