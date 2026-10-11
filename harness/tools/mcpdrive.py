#!/usr/bin/env python3
"""Drive `prism mcp` over stdio and print the header of a change_impact answer.
usage: mcpdrive.py <repo-dir> <name> [symbol_file]"""
import json, subprocess, sys, os

root = sys.argv[1]; name = sys.argv[2]; sfile = sys.argv[3] if len(sys.argv) > 3 else None
p = subprocess.Popen(["prism", "mcp"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True)
def send(obj):
    p.stdin.write(json.dumps(obj) + "\n"); p.stdin.flush()
def recv(want_id):
    while True:
        line = p.stdout.readline()
        if not line:
            sys.stderr.write(p.stderr.read()[-2000:]); raise SystemExit("mcp exited")
        try: m = json.loads(line)
        except Exception: continue
        if m.get("id") == want_id: return m
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "drive", "version": "0"}}})
recv(1)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
args = {"name": name}
if sfile: args["symbol_file"] = sfile
send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "prism", "arguments": {"op": "change_impact", "args": args}}})
r = recv(2)
text = "".join(c.get("text", "") for c in r.get("result", {}).get("content", []))
print(text[:900])
p.stdin.close(); p.wait(timeout=10)
