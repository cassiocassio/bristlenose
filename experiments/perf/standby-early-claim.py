#!/usr/bin/env python3
"""A claim sent while the standby is still booting: what does the study wait?

    .venv/bin/python experiments/perf/standby-early-claim.py <study-copy> [--reps 5]

The restored-window case: the window asks for its study d seconds after the standby was spawned.
For each d, the claim line is written at spawn + d WITHOUT waiting for `standby-ready` (Python
reads it once its imports finish). Reports spawn -> Report: and the wait the study sees, which is
that minus d. d = 0 is "claim at once"; the cold row is a plain `serve <study>`. Interleaved.
Always BRISTLENOSE_LLM_PROVIDER=local; give it a COPY of a study.
"""
from __future__ import annotations

import json
import os
import signal
import statistics
import subprocess
import sys
import time

study = sys.argv[1]
reps = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 5
OFFSETS = [0.0, 0.15, 0.3, 0.45, 0.6, 0.9]
env = {k: v for k, v in os.environ.items() if not k.startswith("_BRISTLENOSE_")}
env["BRISTLENOSE_LLM_PROVIDER"] = "local"
env["BRISTLENOSE_SCREEN_TEXT"] = "0"
base = [sys.executable, "-m", "bristlenose", "serve", "--no-open", "--port", "0"]


def spawn(*a):
    return subprocess.Popen(base + list(a), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, env=env)


def until(p, needle):
    for line in p.stdout:
        if needle in line:
            return time.monotonic()
    raise SystemExit(f"never saw {needle!r}")


def stop(p):
    p.send_signal(signal.SIGINT)
    try:
        p.wait(timeout=15)
    except subprocess.TimeoutExpired:
        p.kill()
    for f in (p.stdin, p.stdout):
        f and f.close()


cold = []
early = {d: [] for d in OFFSETS}
for i in range(reps + 1):  # first pass is a warm-up
    t0 = time.monotonic()
    p = spawn(study)
    t = until(p, "Report:") - t0
    stop(p)
    if i:
        cold.append(t)
    for d in OFFSETS:
        t0 = time.monotonic()
        p = spawn("--standby")
        time.sleep(d)
        p.stdin.write(json.dumps({"v": 1, "project": study, "mcp_token": ""}) + "\n")
        p.stdin.flush()
        t = until(p, "Report:") - t0
        stop(p)
        if i:
            early[d].append(t)

m = statistics.median
print(f"cold (the study waits for all of it): {m(cold):.3f} s   n={len(cold)}")
print("claim sent d s after spawn  ->  spawn->Report   study waits (that minus d)   saved vs cold")
for d in OFFSETS:
    tot = m(early[d])
    print(f"  d = {d:4.2f}                    {tot:6.3f}          {tot - d:6.3f}                  {m(cold) - (tot - d):6.3f}")
