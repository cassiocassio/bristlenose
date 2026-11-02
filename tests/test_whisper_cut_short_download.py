"""N43: a Whisper download cut short on the command line is never used as complete.

Chart row N43 said the terminal path has no completeness check after a
download (R32 review, LOW 8; the app path has one). The row's worry is that a
download stopped halfway is then treated as the model. That needs
``snapshot_download`` to return normally with a file missing, so this drives the
real ``huggingface_hub`` against a loopback server that promises a model file
and cuts the connection part-way through, then asks what the preflight's own
probe makes of the cache.

A subprocess, because ``huggingface_hub`` freezes its endpoint and cache
location at import. The server is on 127.0.0.1; nothing leaves the machine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

_SCRIPT = textwrap.dedent(
    r'''
    import json, os, sys, threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    REPO = "Systran/faster-whisper-tiny"
    SHA = "a" * 40
    FILES = {"config.json": b'{"x": 1}', "model.bin": b"W" * 4096}
    CUT = sys.argv[1] == "cut"
    seen = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _file_headers(self, name):
            body = FILES[name]
            self.send_response(200)
            self.send_header("ETag", '"%s"' % ("e" + str(len(body))))
            self.send_header("X-Repo-Commit", SHA)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return body

        def do_HEAD(self):
            name = self.path.rsplit("/", 1)[-1].split("?")[0]
            seen.append(("HEAD", self.path))
            if name in FILES:
                self._file_headers(name)
            else:
                self.send_response(404); self.end_headers()

        def do_GET(self):
            seen.append(("GET", self.path))
            path = self.path.split("?")[0]
            if "/tree/" in path:
                body = json.dumps([
                    {"type": "file", "path": n, "size": len(b), "oid": "o" + n}
                    for n, b in FILES.items()
                ]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            if path.startswith("/api/models/%s" % REPO):
                body = json.dumps({
                    "id": REPO, "sha": SHA,
                    "siblings": [{"rfilename": n, "size": len(b)} for n, b in FILES.items()],
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            name = path.rsplit("/", 1)[-1]
            if name not in FILES:
                self.send_response(404); self.end_headers(); return
            body = self._file_headers(name)
            if CUT and name == "model.bin":
                self.wfile.write(body[: len(body) // 3])
                self.wfile.flush()
                self.connection.close()
                return
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    os.environ["HF_ENDPOINT"] = "http://127.0.0.1:%d" % port
    os.environ["HF_HUB_CACHE"] = sys.argv[2]
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "5"

    from bristlenose.preflight.whisper import cache_state
    from bristlenose.utils.package_install import PackageInstallError, ensure_hf_model

    out = {"before": cache_state(REPO)}
    try:
        ensure_hf_model(REPO)
        out["fetch"] = "returned"
    except PackageInstallError as exc:
        out["fetch"] = "PackageInstallError"
        out["why"] = str(exc)[:300]
    out["after"] = cache_state(REPO)
    out["requests"] = [f"{m} {p}" for m, p in seen][:12]
    print(json.dumps(out))
    '''
)


def _run(tmp_path: Path, mode: str) -> dict:
    script = tmp_path / "fake_hub.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "BRISTLENOSE_SKIP_PREFLIGHT": "1",
           "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    if sys.platform == "win32":
        # Without SystemRoot a Windows Python cannot start Winsock (WinError
        # 10106), and the script's first act is a local server. The rest stays
        # isolated: the profile and temp folders are the test's own.
        env.update(
            SYSTEMROOT=os.environ.get("SYSTEMROOT", r"C:\Windows"),
            USERPROFILE=str(tmp_path), TEMP=str(tmp_path), TMP=str(tmp_path),
        )
    proc = subprocess.run(
        [sys.executable, str(script), mode, str(tmp_path / "hub")],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_a_complete_download_reads_as_cached(tmp_path: Path) -> None:
    """The harness itself: an uncut transfer lands and the probe says cached."""
    out = _run(tmp_path, "whole")
    assert out["before"] == "missing"
    assert out["fetch"] == "returned", out
    assert out["after"] == "cached", out


def test_a_cut_short_download_raises_and_is_never_cached(tmp_path: Path) -> None:
    out = _run(tmp_path, "cut")
    assert out["before"] == "missing"
    # The fetch fails loudly ...
    assert out["fetch"] == "PackageInstallError", out
    # ... and what it left behind is not the model: the probe the next run
    # starts from says so, so the banner and a fresh fetch come back.
    assert out["after"] in {"partial", "missing"}, out
