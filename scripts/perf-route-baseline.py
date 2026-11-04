"""Per-route baseline: Server-Timing and wire size, gzip vs identity, on a synthetic study.

    .venv/bin/python scripts/perf-route-baseline.py [QUOTES]      (default 1500)

Generates (once, under the temp dir) a synthetic study, serves it on an ephemeral port with
a token it mints itself, and prints time to first byte, the SQL statement count and the wire
size for each hot route, then the HTML export. It never touches a real study or the :8484
dev server. ``ttfb`` is the server's own ``Server-Timing`` ``bn`` value, which includes gzip.
Part of the perf ledger: docs/design-perf-ledger.md.
"""
from __future__ import annotations

import os
import re
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
RUNS = 12
FIX = Path(tempfile.gettempdir()) / f"bn-route-baseline-{N}"

if not FIX.exists():
    subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "scripts/generate-stress-fixture.py"),
                    "--quotes", str(N), "--output", str(FIX)], check=True, capture_output=True)

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
token = secrets.token_urlsafe(32)
env = {**os.environ, "_BRISTLENOSE_AUTH_TOKEN": token, "BRISTLENOSE_SERVER_TIMING": "1"}
db = FIX / "bristlenose-output" / ".bristlenose" / "bristlenose.db"
for p in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
    p.unlink(missing_ok=True)

t0 = time.perf_counter()
srv = subprocess.Popen([str(REPO / ".venv/bin/bristlenose"), "serve", str(FIX), "--port", str(port), "--no-open"],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
base = f"http://127.0.0.1:{port}"
try:
    for _ in range(200):
        try:
            if httpx.get(base + "/api/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.25)
    ready = time.perf_counter() - t0
    print(f"serve ready to health: {ready:.2f}s (n={N})")
    time.sleep(2)  # let the startup import settle
    H = {"Authorization": f"Bearer {token}"}
    routes = ["/api/projects/1/quotes", "/api/projects/1/sessions", "/api/projects/1/dashboard",
              "/api/projects/1/signals/snapshot", "/api/projects/1/tapestry"]
    rows = []
    with httpx.Client(base_url=base, headers=H, timeout=120) as c:
        for r in routes:
            for enc in ("gzip", "identity"):
                bn, dbq, wall, size = [], [], [], 0
                code = 0
                for _ in range(RUNS):
                    t = time.perf_counter()
                    with c.stream("GET", r, headers={"Accept-Encoding": enc}) as resp:
                        wire = sum(len(chunk) for chunk in resp.iter_raw())
                    wall.append((time.perf_counter() - t) * 1000)
                    code = resp.status_code
                    size = wire
                    st = resp.headers.get("server-timing", "")
                    m = re.search(r"bn;dur=([\d.]+), db;dur=([\d.]+);desc=\"(\d+)", st)
                    if m:
                        bn.append(float(m.group(1)))
                        dbq.append(int(m.group(3)))
                if bn:
                    rows.append((r, enc, code, size, statistics.median(bn[2:] or bn), statistics.median(wall[2:] or wall), max(dbq)))
        for r, enc, code, size, bn, wall, q in rows:
            print(f"{code} {r:38s} {enc:8s} {size:>9,d} B  ttfb {bn:7.1f} ms  wall {wall:7.1f} ms  queries {q}")
        t = time.perf_counter()
        resp = c.get("/api/projects/1/export", timeout=300, headers={"Accept-Encoding": "identity"})
        print(f"export {resp.status_code} {len(resp.content):,d} B in {(time.perf_counter()-t):.1f}s  {resp.headers.get('server-timing')}")
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except Exception:
        srv.kill()
