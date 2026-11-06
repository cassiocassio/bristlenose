#!/usr/bin/env python3
"""fakehub.py <mode> — a stand-in HF_ENDPOINT on 0.0.0.0:8765 (a Tart guest reaches the host at 192.168.64.1).
  429:<n>   n requests answered 429 + Retry-After, then redirected to the real hub
  5xx:<n>   n requests answered 503, then redirected
  portal    always 200 text/html, as a captive portal does
"""
import sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
mode = sys.argv[1]; kind, _, arg = mode.partition(":"); left = [int(arg or 0)]; count = [0]; lock = threading.Lock()
class H(BaseHTTPRequestHandler):
    def _go(self):
        with lock:
            count[0] += 1
            n = left[0]; left[0] = max(0, n - 1)
        if kind == "portal":
            body = b"<html><body>Please sign in to the Wi-Fi network</body></html>"
            self.send_response(200); self.send_header("content-type", "text/html"); self.send_header("content-length", str(len(body))); self.end_headers()
            if self.command != "HEAD": self.wfile.write(body)
        elif n > 0:
            self.send_response(429 if kind == "429" else 503); self.send_header("Retry-After", "1"); self.send_header("content-length", "0"); self.end_headers()
        else:
            self.send_response(307); self.send_header("Location", "https://huggingface.co" + self.path); self.send_header("content-length", "0"); self.end_headers()
        sys.stderr.write(f"req#{count[0]} {self.command} {self.path[:60]}\n"); sys.stderr.flush()
    do_GET = do_HEAD = do_POST = _go
    def log_message(self, *a): pass
ThreadingHTTPServer(("0.0.0.0", 8765), H).serve_forever()
