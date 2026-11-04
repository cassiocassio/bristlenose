#!/usr/bin/env python3
"""Serve a project folder for the page-side perf harness, on your own port, prod bundle.

    .venv/bin/python experiments/perf/serve-fixture.py <project-dir> [--port N]

Starts ``bristlenose serve`` WITHOUT ``--dev`` (so the built bundle in
``bristlenose/server/static/`` is used and the lazy chunks are real chunks), on an
ephemeral port, with a token minted here. Prints ``BN_URL=...`` once ``/api/health``
answers, then runs until killed. It never touches :8484. Point the harness at it with
``BN_URL=http://127.0.0.1:<port>``.

Serving imports the folder and writes its database: give it a COPY, never a real study.
A synthetic fixture needs a ``pipeline-events.jsonl`` with a completed run, or /report/
shows the "not analysed yet" status page instead of the SPA.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
folder = Path(sys.argv[1]).resolve()
port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 0
if not port:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
env = {**os.environ, "_BRISTLENOSE_AUTH_TOKEN": secrets.token_urlsafe(32),
       "BRISTLENOSE_SERVER_TIMING": "1"}  # Server-Timing on every response: the harness reads it from resource timing
srv = subprocess.Popen(
    [str(REPO / ".venv/bin/bristlenose"), "serve", str(folder), "--port", str(port), "--no-open"],
    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
base = f"http://127.0.0.1:{port}"
try:
    for _ in range(240):
        try:
            if urllib.request.urlopen(base + "/api/health", timeout=1).status == 200:
                break
        except Exception:
            time.sleep(0.25)
    time.sleep(2)  # let the startup import settle
    print(f"BN_URL={base}", flush=True)
    srv.wait()
finally:
    srv.terminate()
