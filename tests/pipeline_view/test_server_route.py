"""GET /api/pipeline — auth gate + payload shape."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient


@pytest.fixture()
def client() -> TestClient:
    app = create_app(dev=True, db_url="sqlite://")
    return AuthTestClient(app)


@pytest.fixture()
def unauth_client() -> TestClient:
    app = create_app(dev=True, db_url="sqlite://")
    return TestClient(app)


def test_pipeline_endpoint_returns_payload(client: TestClient) -> None:
    res = client.get("/api/pipeline")
    assert res.status_code == 200
    payload = res.json()
    assert "catalogue" in payload
    assert "host" in payload
    ids = [s["id"] for s in payload["catalogue"]]
    assert "quote_extraction" in ids
    assert "transcription" in ids
    assert "apple_foundation_models" in ids


def test_pipeline_endpoint_requires_auth(unauth_client: TestClient) -> None:
    """No bearer token → 401, proving BearerTokenMiddleware applies."""
    res = unauth_client.get("/api/pipeline")
    assert res.status_code == 401


def test_pipeline_endpoint_host_split_present(client: TestClient) -> None:
    res = client.get("/api/pipeline")
    payload = res.json()
    host = payload["host"]
    assert "os" in host
    assert "keys_present" in host
    assert host["apple_fm_status"] == "unknown"
