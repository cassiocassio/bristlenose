#!/usr/bin/env python3
"""Cold `serve` against a claimed `serve --standby`, interleaved: how long from "the user clicks" to
a serving study, in dev (same bundle, Python half only; the app's sandbox is not in this).

    .venv/bin/python experiments/perf/standby-ab.py <study-copy> [--reps 8] [--screens]

Cold: spawn `serve <study>`, time to the `Report:` line. Standby: spawn `serve --standby`, wait for
`standby-ready` (NOT counted: that is the time the user spends choosing), then write the claim and
time claim -> `Report:`. Also reports the standby's own spawn -> ready. Arms alternate A,B,A,B.
Always BRISTLENOSE_LLM_PROVIDER=local. Give it a COPY of a study: serving writes its database.
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
reps = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 8
env = {k: v for k, v in os.environ.items() if not k.startswith("_BRISTLENOSE_")}
env["BRISTLENOSE_LLM_PROVIDER"] = "local"
env["BRISTLENOSE_SCREEN_TEXT"] = "1" if "--screens" in sys.argv else "0"
base = [sys.executable, "-m", "bristlenose", "serve", "--no-open", "--port", "0"]


def until(proc, needle):
    for line in proc.stdout:
        if needle in line:
            return time.monotonic()
    raise SystemExit(f"never saw {needle!r}")


def stop(proc):
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    for p in (proc.stdin, proc.stdout):
        p and p.close()


def spawn(*args):
    return subprocess.Popen(base + list(args), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, env=env)


cold, claimed, ready = [], [], []
for i in range(reps + 1):  # the first pair is a warm-up and is dropped
    t0 = time.monotonic()
    p = spawn(study)
    t = until(p, "Report:") - t0
    stop(p)
    (cold if i else []).append(t)

    t0 = time.monotonic()
    p = spawn("--standby")
    r = until(p, "standby-ready") - t0
    time.sleep(1.0)  # the user is choosing
    p.stdin.write(json.dumps({"v": 1, "project": study, "mcp_token": ""}) + "\n")
    p.stdin.flush()
    t1 = time.monotonic()
    t = until(p, "Report:") - t1
    stop(p)
    if i:
        claimed.append(t)
        ready.append(r)


def row(name, xs):
    xs = sorted(xs)
    print(f"{name:34} p50 {statistics.median(xs):.3f}  min {xs[0]:.3f}  max {xs[-1]:.3f}  n={len(xs)}  all: "
          + " ".join(f"{x:.2f}" for x in xs))


print(f"screens={'on' if env['BRISTLENOSE_SCREEN_TEXT'] == '1' else 'off'}  study={study}")
row("cold: spawn -> Report: (s)", cold)
row("standby: claim -> Report: (s)", claimed)
row("standby: spawn -> ready (hidden, s)", ready)
print(f"saving at p50: {statistics.median(cold) - statistics.median(claimed):.3f} s")
