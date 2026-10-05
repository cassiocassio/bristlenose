"""serve must refuse any Host that is not loopback — the DNS-rebinding gate.

Under DNS rebinding an attacker's page (``http://rebind.attacker.example:8150``)
has its name re-resolved to 127.0.0.1, so the browser treats the loopback serve
as same-origin with the attacker. CORS cannot see it — there is no cross-origin
request — and the bearer token is no defence either, because ``/report/`` hands
the token out in the SPA HTML (``window.__BRISTLENOSE_AUTH_TOKEN__``) and sets
the auth cookie. The one thing the browser cannot forge is the ``Host`` header:
it carries the attacker's name. So the whole app answers only to 127.0.0.1,
localhost and [::1], on any port.

Every legitimate client sends a loopback Host: the macOS WKWebView and every
Swift/``.mcpb`` fetch use ``http://127.0.0.1:<port>``, the CLI prints that URL,
and the ``serve --dev`` Vite proxy forwards the browser's ``localhost:5173``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.middleware import AUTH_COOKIE_NAME, is_loopback_host

_VITE_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head><script type="module" crossorigin src="/assets/main-abc123.js"></script></head>
  <body><div id="bn-app-root" data-project-id="1"></div></body>
</html>
"""

_SMOKE_EVENTS = (
    Path(__file__).parent
    / "fixtures/smoke-test/input/bristlenose-output/.bristlenose/pipeline-events.jsonl"
)

_FOREIGN_HOSTS = [
    "rebind.attacker.example:8150",
    "rebind.attacker.example",
    "localhost.attacker.example:8150",
    "127.0.0.1.nip.io:8150",
    "evil-localhost:8150",
    "0.0.0.0:8150",
    "192.168.1.10:8150",
]

_LOOPBACK_HOSTS = [
    "127.0.0.1:8150",
    "127.0.0.1",
    "localhost:8150",
    "localhost:5173",  # the serve --dev Vite proxy forwards the browser's Host
    "LocalHost:8150",
    "[::1]:8150",
    "[::1]",
]


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """A prod-mount app whose /report/ serves the token-bearing SPA HTML."""
    monkeypatch.delenv("_BRISTLENOSE_DEV", raising=False)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "interview.mp4").write_bytes(b"fake-mp4")
    # A completed-run terminus, or /report/ serves the status page, not the SPA.
    internal = project_dir / "bristlenose-output" / ".bristlenose"
    internal.mkdir(parents=True)
    (internal / "pipeline-events.jsonl").write_text(_SMOKE_EVENTS.read_text(encoding="utf-8"), encoding="utf-8")
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text(_VITE_INDEX_HTML, encoding="utf-8")
    (static_dir / "assets" / "main-abc123.js").write_text("// bundle", encoding="utf-8")
    with patch("bristlenose.server.app._STATIC_DIR", static_dir):
        yield create_app(project_dir=project_dir, dev=False, db_url="sqlite://")


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8150")


class TestForeignHostRefused:
    @pytest.mark.parametrize("host", _FOREIGN_HOSTS)
    def test_report_spa_refused_and_carries_no_token(self, app, client, host: str) -> None:
        resp = client.get("/report/", headers={"host": host})
        assert resp.status_code == 400
        assert app.state.auth_token not in resp.text
        assert AUTH_COOKIE_NAME not in resp.headers.get("set-cookie", "")

    @pytest.mark.parametrize(
        "path",
        [
            "/api/health",
            "/api/projects/1/sessions",
            "/media/interview.mp4",
            "/admin/",
            "/mcp/",
            "/report/assets/bristlenose-theme.css",
        ],
    )
    def test_every_route_refused_even_with_the_token(self, app, client, path: str) -> None:
        # A rebinding page that scraped the token (or rides the cookie) must
        # still be refused: the gate is the Host, not the credential.
        token = app.state.auth_token
        resp = client.get(
            path,
            headers={
                "host": "rebind.attacker.example:8150",
                "authorization": f"Bearer {token}",
                "cookie": f"{AUTH_COOKIE_NAME}={token}",
            },
        )
        assert resp.status_code == 400


class TestAdminPanelBehindTheGate:
    """The .dmg build mounts a read-only /admin showing Person.full_name."""

    def test_mounted_admin_refuses_a_foreign_host(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("_BRISTLENOSE_ADMIN_PANEL", "1")
        monkeypatch.delenv("_BRISTLENOSE_DEV", raising=False)
        app = create_app(project_dir=None, dev=False, db_url="sqlite://")
        client = TestClient(app, base_url="http://127.0.0.1:8150")
        # Control: the panel is really mounted and reachable on loopback.
        assert client.get("/admin/", follow_redirects=True).status_code == 200
        resp = client.get(
            "/admin/", headers={"host": "rebind.attacker.example:8150"}
        )
        assert resp.status_code == 400


class TestLoopbackHostAccepted:
    @pytest.mark.parametrize("host", _LOOPBACK_HOSTS)
    def test_health(self, client, host: str) -> None:
        assert client.get("/api/health", headers={"host": host}).status_code == 200

    @pytest.mark.parametrize("host", ["127.0.0.1:8150", "localhost:8150"])
    def test_report_spa_still_served_with_token(self, app, client, host: str) -> None:
        resp = client.get("/report/", headers={"host": host})
        assert resp.status_code == 200
        assert app.state.auth_token in resp.text

    def test_media_still_served(self, client) -> None:
        resp = client.get("/media/interview.mp4", headers={"host": "127.0.0.1:8150"})
        assert resp.status_code == 200

    def test_project_api_passes_the_host_gate(self, app, client) -> None:
        resp = client.get(
            "/api/projects/1/sessions",
            headers={
                "host": "127.0.0.1:8150",
                "authorization": f"Bearer {app.state.auth_token}",
            },
        )
        assert resp.status_code != 400


class TestIsLoopbackHost:
    @pytest.mark.parametrize("host", _LOOPBACK_HOSTS)
    def test_accepts(self, host: str) -> None:
        assert is_loopback_host(host)

    @pytest.mark.parametrize(
        "host",
        [*_FOREIGN_HOSTS, "", ":8150", "[::1", "[::1]evil", "localhost.", "testserver"],
    )
    def test_refuses(self, host: str) -> None:
        assert not is_loopback_host(host)
