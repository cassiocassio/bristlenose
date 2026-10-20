#!/usr/bin/env python3
"""run_summary.py < run-end.json — one line for the walk log from the run's terminus event."""

import json
import sys

d = json.loads(sys.stdin.read())
parts = [d["event"], str(d.get("outcome")),
         f"tokens {d.get('input_tokens')} in / {d.get('output_tokens')} out"]
for stage, v in (d.get("summary") or {}).items():
    if isinstance(v, dict) and "attempted" in v:
        parts.append(f"{stage} {v.get('succeeded')}/{v.get('attempted')}")
print(" · ".join(parts))
