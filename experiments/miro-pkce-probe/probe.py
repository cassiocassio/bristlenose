"""Does Miro accept an OAuth code exchange with PKCE and no client secret?

Miro documents no PKCE: its token exchange lists `client_secret` as required
(Miro developer docs, read 19 Oct 2026). If Miro silently accepts a PKCE
exchange anyway, Bristlenose can sign in to Miro with no server of its own.
If it refuses, the route is a broker on bristlenose.app that holds the secret.
This probe answers that with one sign-in.

Before running: in the Miro app's settings, add this redirect URI exactly:

    http://127.0.0.1:8765/callback

Then:

    python3 experiments/miro-pkce-probe/probe.py <client_id>

A browser opens on Miro's consent screen. Sign in and approve. The probe
prints Miro's HTTP status and the *names* of the fields it returned, never a
token's value. A 200 with `access_token` among them means PKCE works with no
secret. It also says whether the token expires (`expires_in`) and whether a
refresh token came back.

Standard library only, no secrets read or written.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"
AUTHORIZE = "https://miro.com/oauth/authorize"
TOKEN = "https://api.miro.com/v1/oauth/token"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    client_id = sys.argv[1]

    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(16)
    result: dict[str, str] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Received. You can close this tab.")
            done.set()

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = AUTHORIZE + "?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    print("Opening Miro's consent screen. Sign in and approve.")
    webbrowser.open(url)
    if not done.wait(timeout=300):
        print("No callback within 5 minutes.")
        return 1
    server.shutdown()

    if result.get("state") != state:
        print("State mismatch: not our callback. Stopping.")
        return 1
    if "error" in result:
        print(f"Miro refused at the authorize step: {result['error']}"
              f" ({result.get('error_description', '')})")
        return 1
    code = result.get("code")
    if not code:
        print(f"No code in the callback (fields: {sorted(result)})")
        return 1

    params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    req = urllib.request.Request(
        TOKEN + "?" + urllib.parse.urlencode(params), data=b"", method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read()

    print(f"Token exchange without a secret: HTTP {status}")
    try:
        data = json.loads(body)
    except ValueError:
        print("Body is not JSON (not shown, in case it carries a token).")
        return 1
    print(f"Fields returned: {sorted(data)}")
    if "access_token" in data:
        print("PKCE with no client secret WORKS.")
        print(f"Expires: {'expires_in=' + str(data['expires_in']) if 'expires_in' in data else 'no expires_in (non-expiring token)'}")
        print(f"Refresh token: {'yes' if 'refresh_token' in data else 'no'}")
        print("Revoke this test grant afterwards: Miro ▸ Settings ▸ Your apps.")
    else:
        for key in ("error", "message", "status", "code", "type"):
            if key in data:
                print(f"{key}: {data[key]}")
        print("PKCE with no client secret was REFUSED: the broker route stands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
