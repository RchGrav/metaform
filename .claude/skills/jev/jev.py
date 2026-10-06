#!/usr/bin/env python3
"""Ask Jev (typesafe/jev-1.13) typed questions about some state, through OpenRouter.

Usage: python3 jev.py request.json    (or pipe the JSON on stdin)
The request is {"state": ..., "questions": {...}}; "model" defaults to typesafe/jev-1.13.
Prints the full response JSON plus elapsed_seconds. On failure prints the HTTP status and body and exits 1.
"""
import json, os, sys, time, urllib.error, urllib.request

URL = "https://openrouter.ai/api/alpha/decisions"

req = json.load(open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin)
req.setdefault("model", "typesafe/jev-1.13")
http = urllib.request.Request(
    URL,
    data=json.dumps(req).encode(),
    headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"},
)
start = time.perf_counter()
try:
    with urllib.request.urlopen(http, timeout=60) as r:
        out = json.load(r)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code} after {time.perf_counter() - start:.3f}s\n{e.read().decode(errors='replace')}", file=sys.stderr)
    sys.exit(1)
out["elapsed_seconds"] = round(time.perf_counter() - start, 3)
print(json.dumps(out, indent=2))
