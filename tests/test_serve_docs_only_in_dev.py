"""Swagger and the schema exist only on ``serve --dev`` (T24, owner 7 Nov 2026).

``/api/docs`` and ``/openapi.json`` answered with no token on every serve, and Swagger loads its
page from a CDN when opened. They are a developer convenience, so a normal serve has neither:
nothing token-free to document and nothing fetched from a third party.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


def _client(*, dev: bool) -> TestClient:
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=dev, db_url="sqlite://"))


@pytest.mark.parametrize("path", ["/api/docs", "/openapi.json"])
def test_a_normal_serve_has_no_docs_or_schema_route(path: str) -> None:
    assert _client(dev=False).get(path).status_code == 404


@pytest.mark.parametrize("path", ["/api/docs", "/openapi.json"])
def test_a_dev_serve_keeps_them(path: str) -> None:
    assert _client(dev=True).get(path).status_code == 200


def test_the_schema_is_still_readable_in_process() -> None:
    """The export-coverage and trust gates read ``app.openapi()``, not the URL."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=False, db_url="sqlite://")
    assert "/api/health" in app.openapi()["paths"]
