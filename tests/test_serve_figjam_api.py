"""The FigJam board download — `GET /api/projects/{id}/export/figjam-board.json`.

Smoke-test fixture: one session, four quotes (q-p1-10, q-p1-26, q-p1-46,
q-p1-66). No network: FigJam is a download, not a push.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import Project
from tests.conftest import LOOPBACK_BASE_URL, AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_URL = "/api/projects/1/export/figjam-board.json"


@pytest.fixture()
def client() -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def _quotes(doc: dict) -> list[dict]:
    return [q for f in doc["frames"] for c in f["columns"] for q in c["quotes"]]


def test_downloads_the_board_document(client: TestClient) -> None:
    resp = client.get(_URL)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert disposition.endswith('-figjam-board.json"')
    doc = resp.json()
    assert (doc["format"], doc["version"]) == ("bristlenose-board", 1)
    assert len(_quotes(doc)) == 4
    assert doc["palette"]["light_pink"] == "#FFA8DB"


def test_scope_is_the_selected_quotes(client: TestClient) -> None:
    doc = client.get(_URL, params={"quote_ids": "q-p1-10,q-p1-46"}).json()
    assert [q["attribution"] for q in _quotes(doc)] == ["— P1 · 00:10", "— P1 · 00:46"]


def test_hidden_quotes_stay_off_the_board(client: TestClient) -> None:
    client.put("/api/projects/1/hidden", json={"q-p1-10": True})
    doc = client.get(_URL).json()
    assert "— P1 · 00:10" not in [q["attribution"] for q in _quotes(doc)]
    assert len(_quotes(doc)) == 3


def test_nothing_selected_is_a_reason_the_clients_already_translate(client: TestClient) -> None:
    resp = client.get(_URL, params={"quote_ids": "q-p9-999"})
    assert resp.status_code == 404
    assert resp.json()["reason"] == "no_quotes_selected"


def test_unknown_project_is_404(client: TestClient) -> None:
    assert client.get("/api/projects/99/export/figjam-board.json").status_code == 404


def test_the_board_speaks_lang(client: TestClient) -> None:
    en = client.get(_URL).json()
    es = client.get(_URL, params={"lang": "es"}).json()
    assert es["locale"] == "es"
    assert es["frames"][0]["title"] != en["frames"][0]["title"]


def test_a_project_named_outside_latin_1_still_downloads(client: TestClient) -> None:
    """Starlette encodes headers as Latin-1, so a bare `filename="駅…"` is a 500.
    The name goes in `filename*`, percent-encoded."""
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        db.get(Project, 1).name = "駅の調査 Łódź"
        db.commit()
    finally:
        db.close()
    resp = client.get(_URL)
    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert disposition.isascii()
    star = disposition.split("filename*=UTF-8''", 1)[1]
    assert unquote(star) == "駅の調査 Łódź-figjam-board.json"
    assert "駅の調査" in json.loads(resp.content)["title"]


def test_needs_the_token(client: TestClient) -> None:
    bare = TestClient(client.app, base_url=LOOPBACK_BASE_URL)
    assert bare.get(_URL).status_code == 401
