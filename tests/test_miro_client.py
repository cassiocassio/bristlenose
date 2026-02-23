"""Tests for the Miro API client — token validation."""

from __future__ import annotations

from unittest.mock import patch

import httpx

from bristlenose.miro_client import validate_miro_token


class TestValidateMiroToken:
    """Tests for validate_miro_token."""

    def test_valid_token(self) -> None:
        """Valid token should return (True, None)."""
        mock_response = httpx.Response(200, json={"data": []})
        with patch("bristlenose.miro_client.httpx.get", return_value=mock_response):
            is_valid, error = validate_miro_token("valid-token")
            assert is_valid is True
            assert error is None

    def test_invalid_token_401(self) -> None:
        """Expired/invalid token should return (False, message)."""
        mock_response = httpx.Response(401, json={"message": "Unauthorized"})
        with patch("bristlenose.miro_client.httpx.get", return_value=mock_response):
            is_valid, error = validate_miro_token("bad-token")
            assert is_valid is False
            assert "invalid or expired" in error

    def test_forbidden_token_403(self) -> None:
        """Token with insufficient scopes should return (False, message)."""
        mock_response = httpx.Response(403, json={"message": "Forbidden"})
        with patch("bristlenose.miro_client.httpx.get", return_value=mock_response):
            is_valid, error = validate_miro_token("no-scope-token")
            assert is_valid is False
            assert "scopes" in error

    def test_unexpected_status(self) -> None:
        """Unexpected status code should return (None, message)."""
        mock_response = httpx.Response(500, json={})
        with patch("bristlenose.miro_client.httpx.get", return_value=mock_response):
            is_valid, error = validate_miro_token("some-token")
            assert is_valid is None
            assert "500" in error

    def test_network_error(self) -> None:
        """Network error should return (None, message)."""
        with patch(
            "bristlenose.miro_client.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            is_valid, error = validate_miro_token("some-token")
            assert is_valid is None
            assert "network error" in error

    def test_sends_bearer_token(self) -> None:
        """Should send the token as a Bearer header."""
        mock_response = httpx.Response(200, json={"data": []})
        with patch("bristlenose.miro_client.httpx.get", return_value=mock_response) as mock_get:
            validate_miro_token("my-secret-token")
            call_kwargs = mock_get.call_args
            assert call_kwargs[1]["headers"]["Authorization"] == "Bearer my-secret-token"

    def test_calls_boards_endpoint(self) -> None:
        """Should validate against GET /v2/boards."""
        mock_response = httpx.Response(200, json={"data": []})
        with patch("bristlenose.miro_client.httpx.get", return_value=mock_response) as mock_get:
            validate_miro_token("token")
            url = mock_get.call_args[0][0]
            assert "/v2/boards" in url
