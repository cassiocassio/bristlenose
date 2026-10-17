"""Tests for the Miro API client — token validation."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

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


class _Resp:
    def __init__(self, status: int, body: object) -> None:
        import json as _json

        self.status_code = status
        self._body = body
        self.content = _json.dumps(body).encode()
        self.text = _json.dumps(body)

    def json(self) -> object:
        return self._body


def test_a_frame_refused_with_500_is_retried_and_never_made_twice(monkeypatch) -> None:
    from bristlenose import miro_client as mc

    calls: list[tuple[str, str]] = []
    answers = iter([
        _Resp(500, {"message": "Internal error occurred"}),  # POST: refused
        _Resp(200, {"data": []}),                             # GET: not there
        _Resp(500, {"message": "Internal error occurred"}),  # POST: refused again
        _Resp(200, {"data": [{"id": "f1", "data": {"title": "P1 · Home"},  # GET: it landed after all
                              "position": {"x": 10.0, "y": 20.0}}]}),
    ])

    def fake(method: str, url: str, **_: object) -> _Resp:
        calls.append((method, url))
        return next(answers)

    monkeypatch.setattr(mc.httpx, "request", fake)
    monkeypatch.setattr(mc.time, "sleep", lambda _s: None)
    assert mc.create_frame("t", "b", "P1 · Home", 10, 20, 100, 100)["id"] == "f1"
    assert [m for m, _ in calls] == ["POST", "GET", "POST", "GET"]  # no third POST


def test_a_frame_error_other_than_500_is_not_retried(monkeypatch) -> None:
    from bristlenose import miro_client as mc

    calls: list[str] = []

    def fake(method: str, url: str, **_: object) -> _Resp:
        calls.append(method)
        return _Resp(400, {"message": "bad"})

    monkeypatch.setattr(mc.httpx, "request", fake)
    with pytest.raises(mc.MiroError):
        mc.create_frame("t", "b", "x", 0, 0, 1, 1)
    assert calls == ["POST"]


def test_the_frame_check_is_itself_retried_when_miro_refuses_it(monkeypatch) -> None:
    from bristlenose import miro_client as mc

    answers = iter([
        _Resp(500, {"message": "Internal error occurred"}),   # POST frame: refused
        _Resp(500, {"code": "3.0016"}),                       # GET items: refused too
        _Resp(200, {"data": []}),                             # GET items: not there
        _Resp(201, {"id": "f2"}),                             # POST frame: made
    ])
    calls: list[str] = []

    def fake(method: str, url: str, **_: object) -> _Resp:
        calls.append(method)
        return next(answers)

    monkeypatch.setattr(mc.httpx, "request", fake)
    monkeypatch.setattr(mc.time, "sleep", lambda _s: None)
    assert mc.create_frame("t", "b", "P1 · Home", 10, 20, 100, 100)["id"] == "f2"
    assert calls == ["POST", "GET", "GET", "POST"]
