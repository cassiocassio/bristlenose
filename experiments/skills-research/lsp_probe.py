"""Re-run: .venv/bin/python experiments/skills-research/lsp_probe.py  (11 Oct 2026, WP-F).
Minimal LSP client: does sourcekit-lsp resolve a symbol across files in this Xcode project?"""
import json, subprocess, sys, time, threading, queue, pathlib

ROOT = pathlib.Path("/Users/cassio/Code/bristlenose")
SRC = ROOT / "desktop/Bristlenose/Bristlenose"
DEF_FILE, USE_FILE = SRC / "MCPHandshake.swift", SRC / "ServeFleet.swift"
args = ["xcrun", "sourcekit-lsp"] + sys.argv[1:]

p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
inbox: "queue.Queue[dict]" = queue.Queue()

def reader():
    f = p.stdout
    while True:
        hdr = {}
        while True:
            line = f.readline()
            if not line: return
            line = line.decode().strip()
            if not line: break
            k, v = line.split(":", 1); hdr[k.lower()] = v.strip()
        inbox.put(json.loads(f.read(int(hdr["content-length"]))))
threading.Thread(target=reader, daemon=True).start()

nid = 0
def send(method, params, notify=False):
    global nid
    msg = {"jsonrpc": "2.0", "method": method, "params": params}
    if not notify: nid += 1; msg["id"] = nid
    b = json.dumps(msg).encode(); p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b); p.stdin.flush()
    return None if notify else nid

def wait(i, timeout=60):
    end = time.time() + timeout
    diags = []
    while time.time() < end:
        try: m = inbox.get(timeout=1)
        except queue.Empty: continue
        if m.get("method") == "textDocument/publishDiagnostics": diags.append(m["params"])
        if m.get("id") == i and "method" not in m: return m, diags
        if "method" in m and "id" in m: send_resp(m["id"])  # answer server requests
    return None, diags

def send_resp(i):
    b = json.dumps({"jsonrpc": "2.0", "id": i, "result": None}).encode()
    p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b); p.stdin.flush()

def pos(path, needle, line_hint):
    lines = path.read_text().splitlines()
    for ln in range(max(0, line_hint - 3), len(lines)):
        c = lines[ln].find(needle)
        if c >= 0: return {"line": ln, "character": c + 1}
    raise SystemExit(f"needle {needle!r} not found in {path.name}")

r, _ = wait(send("initialize", {"processId": None, "rootUri": ROOT.as_uri(), "capabilities": {}, "workspaceFolders": [{"uri": ROOT.as_uri(), "name": "bn"}]}))
send("initialized", {}, notify=True)
for f in (DEF_FILE, USE_FILE):
    send("textDocument/didOpen", {"textDocument": {"uri": f.as_uri(), "languageId": "swift", "version": 1, "text": f.read_text()}}, notify=True)
time.sleep(8)  # let it settle / index

use_pos = pos(USE_FILE, "MCPHandshake.write", 335)
r, diags = wait(send("textDocument/definition", {"textDocument": {"uri": USE_FILE.as_uri()}, "position": use_pos}))
res = (r or {}).get("result")
locs = res if isinstance(res, list) else ([res] if res else [])
print("definition from ServeFleet ->", [pathlib.Path(l.get("uri", l.get("targetUri","")).replace("file://","")).name + f":{(l.get('range') or l.get('targetRange'))['start']['line']+1}" for l in locs] or "NONE", "| error:", (r or {}).get("error"))

def_pos = pos(DEF_FILE, "MCPHandshake", 41)
r, d2 = wait(send("textDocument/references", {"textDocument": {"uri": DEF_FILE.as_uri()}, "position": def_pos, "context": {"includeDeclaration": True}}))
refs = (r or {}).get("result") or []
files = sorted({pathlib.Path(x["uri"].replace("file://","")).name for x in refs})
print(f"references to MCPHandshake: {len(refs)} in files {files}", "| error:", (r or {}).get("error"))
alld = diags + d2
errs = [(pathlib.Path(d['uri'].replace('file://','')).name, x['message'][:70]) for d in alld for x in d.get('diagnostics', []) if x.get('severity') == 1]
print(f"error diagnostics: {len(errs)}", errs[:4])
send("shutdown", {}); p.kill()
