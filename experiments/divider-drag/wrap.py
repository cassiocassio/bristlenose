#!/usr/bin/env python3
# Throwaway dev-sidecar stand-in: runs the real `bristlenose serve`, fronts it with a probe-injecting proxy.
import http.server, socketserver, urllib.request, urllib.error, sys, os, re, subprocess, threading, signal
REAL = os.environ.get("BN_BIN") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../.venv/bin/bristlenose")
args = sys.argv[1:]
if "--standby" in args: os.execv(REAL, [REAL] + args)
PROBE = b"""<script>(function(){var buf=[];var lw=-1,wb=[];function tick(ts){var e=performance.timeOrigin+ts;buf.push(e);if(window.innerWidth!==lw){lw=window.innerWidth;wb.push([e,lw]);}requestAnimationFrame(tick);}
requestAnimationFrame(tick);setInterval(function(){if(!buf.length)return;var b=buf;buf=[];try{navigator.sendBeacon('/__lab/ts',JSON.stringify(b));if(wb.length){navigator.sendBeacon('/__lab/w',JSON.stringify(wb));wb=[];}}catch(e){}},500);})();</script>"""
up = {"port": None}; lock = threading.Lock(); mem = []; memw = []
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        if self.path == "/__lab/w":
            with lock: memw.append(body.decode())
            self.send_response(204); self.end_headers(); return
        if self.path == "/__lab/ts":
            with lock: mem.append(body.decode())
            self.send_response(204); self.end_headers(); return
        self.fwd(body)
    def do_GET(self):
        if self.path == "/__lab/dumpw":
            with lock: d = ("\n".join(memw)).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d); return
        if self.path == "/__lab/dump":
            with lock: d = ("\n".join(mem)).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d); return
        self.fwd(None)
    do_PUT = do_PATCH = do_DELETE = do_POST
    def fwd(self, body):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (up["port"], self.path), data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "accept-encoding", "connection"): req.add_header(k, v)
        try: r = urllib.request.urlopen(req, timeout=60); code = r.status; hdr = r.headers; data = r.read()
        except urllib.error.HTTPError as e: code = e.code; hdr = e.headers; data = e.read()
        except Exception: self.send_response(502); self.end_headers(); return
        if "text/html" in (hdr.get("Content-Type") or "") and b"<head>" in data: data = data.replace(b"<head>", b"<head>" + PROBE, 1)
        self.send_response(code)
        for k, v in hdr.items():
            if k.lower() not in ("content-length", "transfer-encoding", "connection", "content-encoding"): self.send_header(k, v)
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
srv = S(("127.0.0.1", 0), H); pport = srv.server_address[1]
child = subprocess.Popen([REAL] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
def term(*a): child.terminate(); sys.exit(0)
signal.signal(signal.SIGTERM, term); signal.signal(signal.SIGINT, term)
for line in child.stdout:
    m = re.search(r"(http://127\.0\.0\.1:)(\d+)(/)", line)
    if m and "Report:" in line and up["port"] is None:
        up["port"] = int(m.group(2)); threading.Thread(target=srv.serve_forever, daemon=True).start()
        line = line.replace(m.group(0), "%s%d/" % (m.group(1), pport))
    sys.stdout.write(line); sys.stdout.flush()
sys.exit(child.wait())
