#!/usr/bin/env python3
"""Local stub that answers like the providers do when they refuse a call, plus the
non-provider replies a hostile or captive network produces. Keyless, loopback only.

    stub_provider.py [--port 0] [--tls-port 0] [--cert cert.pem --key key.pem]

Prints one line per listener: `plain http://127.0.0.1:PORT` and (with a cert) `tls
https://127.0.0.1:PORT`. Routes are /<family>/<case>; GET or POST both answer.

Bodies follow the shapes bristlenose/llm/failure_classifier.py reads:
  Anthropic  {"type":"error","error":{"type":...,"message":...},"request_id":...}
             out of credit is a 400 invalid_request_error "credit balance is too low"
  OpenAI     {"error":{"message","type","code"}}   insufficient_quota is a 429
  Gemini     {"error":{"code","message","status","details":[{"reason":...}]}}
  Azure      {"error":{"code","message"}}
Provider-signature cases send a `request-id` header (what a real Anthropic reply carries and
a proxy block page does not); `proxy/*` and `portal/*` cases do not.
"""
import argparse, json, socket, ssl, struct, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REQ = "req_stub0000000000000000"


def anth(t, m, status):
    return status, {"content-type": "application/json", "request-id": REQ, "server": "stub"}, json.dumps(
        {"type": "error", "error": {"type": t, "message": m}, "request_id": REQ})


def oai(code, typ, m, status):
    return status, {"content-type": "application/json", "x-request-id": REQ, "server": "stub"}, json.dumps(
        {"error": {"message": m, "type": typ, "param": None, "code": code}})


def gem(status, st, m, reason=None):
    err = {"code": status, "message": m, "status": st}
    if reason:
        err["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}]
    return status, {"content-type": "application/json; charset=UTF-8", "server": "stub"}, json.dumps({"error": err})


def az(status, code, m):
    return status, {"content-type": "application/json", "apim-request-id": REQ, "server": "stub"}, json.dumps(
        {"error": {"code": code, "message": m}})


HTML403 = "<html><head><title>Access Denied</title></head><body><h1>Blocked by network policy</h1></body></html>"
PORTAL = "<html><head><title>Wi-Fi sign in</title></head><body><form>Accept terms to continue</form></body></html>"

ROUTES = {
    "anthropic/401": lambda: anth("authentication_error", "invalid x-api-key", 401),
    "anthropic/credit400": lambda: anth("invalid_request_error",
        "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.", 400),
    "anthropic/402": lambda: anth("billing_error", "Billing issue", 402),
    "anthropic/429": lambda: anth("rate_limit_error", "Number of request tokens has exceeded your rate limit", 429),
    "anthropic/500": lambda: anth("api_error", "Internal server error", 500),
    "anthropic/529": lambda: anth("overloaded_error", "Overloaded", 529),
    "openai/401": lambda: oai("invalid_api_key", "invalid_request_error", "Incorrect API key provided: sk-stub", 401),
    "openai/insufficient_quota": lambda: oai("insufficient_quota", "insufficient_quota",
        "You exceeded your current quota, please check your plan and billing details.", 429),
    "openai/429": lambda: oai("rate_limit_exceeded", "requests", "Rate limit reached for requests", 429),
    "openai/503": lambda: oai(None, "server_error", "The server is overloaded or not ready yet.", 503),
    "gemini/keyinvalid400": lambda: gem(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.", "API_KEY_INVALID"),
    "gemini/403": lambda: gem(403, "PERMISSION_DENIED", "Your API key was reported as leaked."),
    # what the real endpoint says to a request with no key at all (measured 2 Nov 2026)
    "gemini/keyless403": lambda: gem(403, "PERMISSION_DENIED",
        "Method doesn't allow unregistered callers (callers without established identity). Please use API Key or other form of API consumer identity to call this API."),
    "gemini/429": lambda: gem(429, "RESOURCE_EXHAUSTED", "Resource has been exhausted (e.g. check quota)."),
    "gemini/503": lambda: gem(503, "UNAVAILABLE", "The model is overloaded. Please try again later."),
    "azure/401": lambda: az(401, "401", "Access denied due to invalid subscription key or wrong API endpoint."),
    "azure/404": lambda: az(404, "DeploymentNotFound", "The API deployment for this resource does not exist."),
    "azure/429": lambda: az(429, "429", "Requests to the ChatCompletions_Create Operation have exceeded token rate limit"),
    "azure/500": lambda: az(500, "500", "Internal server error"),
    # not the provider: what a proxy or portal puts in its place (no request-id)
    "proxy/403html": lambda: (403, {"content-type": "text/html", "server": "BlueProxy"}, HTML403),
    "proxy/407": lambda: (407, {"proxy-authenticate": 'Basic realm="corp"', "content-type": "text/html"}, "<html>proxy auth</html>"),
    "proxy/502html": lambda: (502, {"content-type": "text/html", "server": "nginx"}, "<html>Bad Gateway</html>"),
    "portal/hotspot": lambda: (200, {"content-type": "text/html"}, PORTAL),
    "portal/redirect": lambda: (302, {"location": "http://login.stub.invalid/portal", "content-type": "text/html"}, ""),
    "ok/success": lambda: (200, {"content-type": "text/html"}, "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"),
}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _go(self):
        n = int(self.headers.get("content-length") or 0)
        if n:
            self.rfile.read(n)
        key = self.path.split("?")[0].strip("/")
        if key == "hang":
            time.sleep(60)
            return
        if key == "reset":     # RST instead of a reply: linger 0, then drop every reference
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self.close_connection = True
            self.rfile.close(); self.wfile.close(); self.connection.close()
            return
        if key == "close":     # clean FIN, no bytes
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        if key == "garbage":
            self.connection.sendall(b"\x00\x01not http at all\r\n\r\n")
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        if key not in ROUTES:
            body = json.dumps({"routes": sorted(ROUTES) + ["hang", "reset", "close", "garbage"]}).encode()
            self.send_response(404); self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        status, headers, body = ROUTES[key]()
        b = body.encode()
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    do_GET = do_POST = _go


def serve(port, ctx=None):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    if ctx:
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--tls-port", type=int, default=0)
    ap.add_argument("--cert")
    ap.add_argument("--key")
    ap.add_argument("--list", action="store_true", help="print the route names and exit")
    a = ap.parse_args()
    if a.list:
        print("\n".join(sorted(ROUTES) + ["hang", "reset", "close", "garbage"])); sys.exit(0)
    print(f"plain http://127.0.0.1:{serve(a.port)}", flush=True)
    if a.cert and a.key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert, a.key)
        print(f"tls https://127.0.0.1:{serve(a.tls_port, ctx)}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
