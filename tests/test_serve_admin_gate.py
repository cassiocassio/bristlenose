"""/admin on a bundled beta build opens only with the server token or a single-use code (T21).

The Debug menu cannot send a bearer header from a browser, so the app fetches a one-time code
from an authenticated endpoint and opens ``/admin/?t=<code>``; the middleware swaps the code for a
cookie scoped to ``/admin``. ``serve --dev`` is unchanged. Owner call, 7 Nov 2026.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_HOST = "http://127.0.0.1:8150"
_TOKEN = "test-admin-gate-token"


def _app(tmp_path: Path, *, dev: bool):
    (tmp_path / "bristlenose-output").mkdir(exist_ok=True)
    with patch.dict("os.environ", {"_BRISTLENOSE_ADMIN_PANEL": "1"}, clear=False):
        app = create_app(project_dir=tmp_path, dev=dev, db_url="sqlite://")
    app.state.auth_token = _TOKEN
    return app


@pytest.fixture
def beta(tmp_path: Path):
    app = _app(tmp_path, dev=False)
    with TestClient(app, base_url=_HOST, follow_redirects=False) as client:
        yield app, client


def _code(client: TestClient) -> str:
    r = client.post("/api/admin/open", headers={"Authorization": f"Bearer {_TOKEN}"})
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    assert path.startswith("/admin/?t=")
    return path.split("t=", 1)[1]


def test_admin_answers_401_without_a_token_or_code(beta) -> None:
    _, client = beta
    assert client.get("/admin/").status_code == 401
    assert client.get("/admin/user/list").status_code == 401
    assert client.get("/admin").status_code == 401


def test_the_code_endpoint_needs_the_server_token(beta) -> None:
    _, client = beta
    assert client.post("/api/admin/open").status_code == 401
    assert client.post("/api/admin/open", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_a_code_is_swapped_for_a_scoped_cookie_and_leaves_the_address(beta) -> None:
    _, client = beta
    code = _code(client)
    r = client.get(f"/admin/?t={code}")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/", "the code must not stay in the address"
    cookie = r.headers["set-cookie"].lower()
    assert "bristlenose_admin=" in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/admin" in cookie
    assert client.get("/admin/").status_code != 401, "the cookie opens the panel"


def test_a_code_works_once(beta) -> None:
    _, client = beta
    code = _code(client)
    assert client.get(f"/admin/?t={code}").status_code == 303
    client.cookies.clear()
    assert client.get(f"/admin/?t={code}").status_code == 401


def test_an_unknown_or_expired_code_is_refused(beta) -> None:
    app, client = beta
    assert client.get("/admin/?t=not-a-code").status_code == 401
    app.state.admin_gate._ttl = -1.0
    expired = _code(client)
    assert client.get(f"/admin/?t={expired}").status_code == 401


def test_the_admin_cookie_opens_nothing_under_api(beta) -> None:
    app, client = beta
    code = _code(client)
    client.get(f"/admin/?t={code}")
    assert client.get("/api/projects").status_code == 401


def test_the_server_token_opens_admin_directly(beta) -> None:
    _, client = beta
    assert client.get("/admin/", headers={"Authorization": f"Bearer {_TOKEN}"}).status_code != 401


def test_a_path_that_only_starts_with_admin_is_not_the_panel(beta) -> None:
    _, client = beta
    assert client.get("/administrator").status_code != 401


def test_serve_dev_is_unchanged(tmp_path: Path) -> None:
    app = _app(tmp_path, dev=True)
    assert getattr(app.state, "admin_gate", None) is None
    with TestClient(app, base_url=_HOST, follow_redirects=False) as client:
        assert client.get("/admin/").status_code != 401
        assert client.post("/api/admin/open", headers={"Authorization": f"Bearer {_TOKEN}"}).status_code in (404, 405)
