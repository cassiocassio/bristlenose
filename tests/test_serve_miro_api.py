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
from tests.conftest import AuthTestClient

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
    return AuthTestClient(app)


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
            # disconnect clears BOTH the access token and the OAuth refresh token
            # (the refresh token is stored on the OAuth callback path) — leaving a
            # live refresh token behind after disconnect would defeat the disconnect.
            assert mock_store.return_value.delete.call_count == 2
            mock_store.return_value.delete.assert_any_call("miro")
            mock_store.return_value.delete.assert_any_call("miro_refresh")

    def test_disconnect_project_not_found(self, client: TestClient) -> None:
        """Should return 404 for non-existent project."""
        resp = client.post("/api/projects/999/miro/disconnect")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/miro/callback — the OAuth path's persistence seam
# ---------------------------------------------------------------------------
#
# `CredentialStore.set` returning cleanly is not evidence that anything was
# written. `MacOSCredentialStore.set` swallows every subprocess failure by
# design (under App Sandbox `/usr/bin/security` is unreachable), so the write
# is a silent no-op. The Swift side has the same shape one layer over:
# `KeychainHelper.serviceNames` is an allowlist, and `CloudGrantStore` shipped
# against an unregistered key persisting nothing at all, with no error
# anywhere. These pin the Python half of that lesson — a store that no-ops
# must not be reported as success.


class _NoOpStore:
    """A store shaped like `MacOSCredentialStore` under App Sandbox.

    `set` accepts and discards; `get` finds nothing. Nothing raises, which is
    exactly what makes the failure invisible without a read-back.
    """

    def __init__(self) -> None:
        self.sets: list[tuple[str, str]] = []

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str) -> None:
        self.sets.append((key, value))

    def delete(self, key: str) -> None:
        pass


class _WorkingStore:
    """A store that actually persists — the CLI Mac / Linux happy path."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


_PATCH_EXCHANGE = "bristlenose.miro_client.exchange_code_for_tokens"
_PATCH_TOKEN_INFO = "bristlenose.miro_client.get_token_info"


def _begin_oauth(state: str = "test-state") -> None:
    """Seed the in-flight OAuth state the callback pops."""
    from bristlenose.server.routes.miro import _OAUTH_STATES

    _OAUTH_STATES[state] = ("test-verifier", 1)


class TestMiroCallbackPersistence:
    """The callback must not claim a durable copy it has not verified."""

    def test_no_op_store_is_not_reported_as_connected(self, client: TestClient) -> None:
        """A silently-discarding store must not produce the bare 'Connected ✓'.

        This is the seam: `set` raised nothing, so the pre-fix code returned the
        tick while the token existed in no store at all — and every other
        surface (status, export, Settings ▸ Accounts) disagreed, with nothing
        anywhere to explain it.
        """
        _begin_oauth()
        store = _NoOpStore()
        with patch(_PATCH_GET_STORE, return_value=store), \
             patch(_PATCH_EXCHANGE, return_value={"access_token": "tok-abc"}), \
             patch(_PATCH_TOKEN_INFO, return_value={"user_name": None,
                                                    "team_name": None,
                                                    "org_name": None}):
            resp = client.get("/api/miro/callback?code=c&state=test-state")

        assert resp.status_code == 200
        assert "Connected to Miro ✓" not in resp.text
        assert "not saved" in resp.text
        # It did attempt the write — the point is that it checked afterwards.
        assert ("miro", "tok-abc") in store.sets

    def test_no_op_store_still_leaves_the_session_usable(self, client: TestClient) -> None:
        """The in-session fallback the paste path has always had.

        Persistence failing must not mean the token is nowhere: the connection
        works until restart, which is what the page now says.
        """
        _begin_oauth()
        with patch(_PATCH_GET_STORE, return_value=_NoOpStore()), \
             patch(_PATCH_EXCHANGE, return_value={"access_token": "tok-abc"}), \
             patch(_PATCH_TOKEN_INFO, return_value={"user_name": "Ada",
                                                    "team_name": "Research",
                                                    "org_name": None}):
            client.get("/api/miro/callback?code=c&state=test-state")
            assert client.app.state.miro_session_token == "tok-abc"

            # …and the rest of the app agrees, rather than contradicting the page.
            with patch(_PATCH_GET_CREDENTIAL, return_value=None):
                status = client.get("/api/projects/1/miro/status")
        assert status.json()["connected"] is True
        assert status.json()["user_name"] == "Ada"

    def test_working_store_returns_the_tick(self, client: TestClient) -> None:
        """A real round-trip still gets the unqualified success page."""
        _begin_oauth()
        store = _WorkingStore()
        with patch(_PATCH_GET_STORE, return_value=store), \
             patch(_PATCH_EXCHANGE, return_value={"access_token": "tok-abc",
                                                  "refresh_token": "ref-xyz"}), \
             patch(_PATCH_TOKEN_INFO, return_value={"user_name": None,
                                                    "team_name": None,
                                                    "org_name": None}):
            resp = client.get("/api/miro/callback?code=c&state=test-state")

        assert "Connected to Miro ✓" in resp.text
        assert "not saved" not in resp.text
        assert store.data["miro"] == "tok-abc"
        assert store.data["miro_refresh"] == "ref-xyz"


class TestConnectPathsAgree:
    """The paste path and the OAuth path must not disagree about persistence."""

    def test_both_paths_verify_the_write(self, client: TestClient) -> None:
        """Neither path may treat a clean `set()` as proof of persistence.

        Pinned behaviourally rather than by asserting `get` was called: what
        matters is that a no-op store is never reported as durable, whichever
        door the token came through.
        """
        # Paste path — reports connected (correct: the session cache and the
        # native `store-miro-token` bridge both cover it) but logs the truth.
        with patch(_PATCH_GET_STORE, return_value=_NoOpStore()), \
             patch(_PATCH_VALIDATE_TOKEN, return_value=(True, None)), \
             patch(_PATCH_TOKEN_INFO, return_value={"user_name": None,
                                                    "team_name": None,
                                                    "org_name": None}):
            paste = client.post("/api/projects/1/miro/connect",
                                json={"token": "tok-abc"})
        assert paste.status_code == 200
        assert client.app.state.miro_session_token == "tok-abc"

        # OAuth path — same store, same in-session outcome. Before the fix this
        # path set no session token at all.
        client.app.state.miro_session_token = None
        _begin_oauth("state-2")
        with patch(_PATCH_GET_STORE, return_value=_NoOpStore()), \
             patch(_PATCH_EXCHANGE, return_value={"access_token": "tok-abc"}), \
             patch(_PATCH_TOKEN_INFO, return_value={"user_name": None,
                                                    "team_name": None,
                                                    "org_name": None}):
            client.get("/api/miro/callback?code=c&state=state-2")
        assert client.app.state.miro_session_token == "tok-abc"
