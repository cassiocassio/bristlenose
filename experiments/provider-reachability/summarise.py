#!/usr/bin/env python3
"""One row per request across result files, so network states can be compared side by side.

    ./summarise.py results/*.json            # everything
    ./summarise.py results/*.json --only control-https,anthropic,openai,gemini
"""
import json, sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
only = None
if "--only" in sys.argv:
    only = sys.argv[sys.argv.index("--only") + 1].split(",")
    args = [a for a in args if a != sys.argv[sys.argv.index("--only") + 1]]
docs = [json.load(open(f)) for f in args]
names = []
for d in docs:
    for r in d["requests"]:
        if r["name"] not in names and (only is None or r["name"] in only):
            names.append(r["name"])


def cell(r):
    if r is None:
        return "-"
    if "status" in r:
        h = r.get("headers", {})
        sig = "rid" if ("request-id" in h or "x-request-id" in h) else "no-rid"
        return f"{r['status']} {r['elapsed_ms']}ms {sig}"
    e = r.get("error", {})
    return f"{e.get('code')} {e.get('name', '')} {r.get('elapsed_ms')}ms"


print("state".ljust(28), " | ".join(d["label"][:26].ljust(26) for d in docs))
print("path".ljust(28), " | ".join(f"{d['path'].get('status')} gw={len(d['path'].get('gateways', []))}".ljust(26) for d in docs))
print("gateway tcp".ljust(28), " | ".join(",".join(f"{g['port']}:{g['state']}" for g in d["gateway_tcp"]).ljust(26)[:26] for d in docs))
print("dns anthropic".ljust(28), " | ".join(
    next((", ".join(f"{a['class']}" for a in x.get("addresses", [])) or str(x.get("gai_message")) for x in d["dns"] if x["host"] == "api.anthropic.com"), "-").ljust(26)[:26] for d in docs))
for n in names:
    rows = []
    for d in docs:
        rows.append(cell(next((r for r in d["requests"] if r["name"] == n), None)).ljust(26)[:26])
    print(n.ljust(28)[:28], " | ".join(rows))
