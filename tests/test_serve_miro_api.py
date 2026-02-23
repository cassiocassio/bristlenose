"""Tests for the Miro integration API endpoints.

Exercises connection status, connect, and disconnect endpoints.
Uses in-memory SQLite with smoke-test data. No real Miro API calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Patch targets — where the names are bound (the routes module imports them)
_PATCH_GET_CREDENTIAL = "bristlenose.server.routes.miro.get_credential"
_PATCH_VALIDATE_TOKEN = "bristlenose.server.routes.miro.validate_miro_token"
_PATCH_GET_STORE = "bristlenose.server.routes.miro.get_credential_store"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """Test client with imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /projects/{id}/miro/status
# ---------------------------------------------------------------------------


class TestMiroStatus:
    """Tests for the Miro connection status endpoint."""

    def test_not_connected(self, client: TestClient) -> None:
        """Should return connected=False when no token is configured."""
        with patch(_PATCH_GET_CREDENTIAL, return_value=None):
            resp = client.get("/api/projects/1/miro/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert data["user_name"] is None

    def test_connected(self, client: TestClient) -> None:
        """Should return connected=True when a token exists."""
        with patch(_PATCH_GET_CREDENTIAL, return_value="valid-token"):
            resp = client.get("/api/projects/1/miro/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True

    def test_project_not_found(self, client: TestClient) -> None:
        """Should return 404 for non-existent project."""
        resp = client.get("/api/projects/999/miro/status")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/connect
# ---------------------------------------------------------------------------


class TestMiroConnect:
    """Tests for the Miro token connection endpoint."""

    def test_valid_token(self, client: TestClient) -> None:
        """Should store a valid token and return connected=True."""
        with patch(_PATCH_VALIDATE_TOKEN, return_value=(True, None)):
            with patch(_PATCH_GET_STORE) as mock_store:
                mock_store.return_value.set.return_value = None
                resp = client.post(
                    "/api/projects/1/miro/connect",
                    json={"token": "valid-miro-token"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["connected"] is True
                mock_store.return_value.set.assert_called_once_with(
                    "miro", "valid-miro-token"
                )

    def test_invalid_token(self, client: TestClient) -> None:
        """Should return 401 for an invalid token."""
        with patch(
            _PATCH_VALIDATE_TOKEN,
            return_value=(False, "invalid or expired token"),
        ):
            resp = client.post(
                "/api/projects/1/miro/connect",
                json={"token": "bad-token"},
            )
            assert resp.status_code == 401
            assert "invalid" in resp.json()["detail"].lower()

    def test_network_error(self, client: TestClient) -> None:
        """Should return 502 when Miro API is unreachable."""
        with patch(
            _PATCH_VALIDATE_TOKEN,
            return_value=(None, "network error: Connection refused"),
        ):
            resp = client.post(
                "/api/projects/1/miro/connect",
                json={"token": "some-token"},
            )
            assert resp.status_code == 502

    def test_empty_token(self, client: TestClient) -> None:
        """Should return 400 for empty token."""
        resp = client.post(
            "/api/projects/1/miro/connect",
            json={"token": "  "},
        )
        assert resp.status_code == 400

    def test_project_not_found(self, client: TestClient) -> None:
        """Should return 404 for non-existent project."""
        resp = client.post(
            "/api/projects/999/miro/connect",
            json={"token": "valid-token"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/disconnect
# ---------------------------------------------------------------------------


class TestMiroDisconnect:
    """Tests for the Miro token disconnection endpoint."""

    def test_disconnect(self, client: TestClient) -> None:
        """Should delete token and return connected=False."""
        with patch(_PATCH_GET_STORE) as mock_store:
            mock_store.return_value.delete.return_value = None
            resp = client.post("/api/projects/1/miro/disconnect")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            mock_store.return_value.delete.assert_called_once_with("miro")

    def test_disconnect_project_not_found(self, client: TestClient) -> None:
        """Should return 404 for non-existent project."""
        resp = client.post("/api/projects/999/miro/disconnect")
        assert resp.status_code == 404
