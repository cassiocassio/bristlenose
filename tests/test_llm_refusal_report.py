"""The sidecar's refusal line: what is printed, when, and what it must never carry."""

from __future__ import annotations

import asyncio
import json
import socket
import ssl

import httpx
import pytest

from bristlenose.llm import refusal_report
from bristlenose.llm.refusal_report import LINE_PREFIX, phase_of, report_refusal, set_refusal_sink


class _ReplyError(Exception):
    def __init__(self, status, body, text="a provider body that echoes: participant said 'my secret plan'"):
        super().__init__(text)
        self.status_code = status
        self.body = body


@pytest.fixture
def lines():
    out: list[str] = []
    set_refusal_sink(out.append)
    yield out
    set_refusal_sink(None)


def _parse(line: str) -> dict:
    assert line.startswith(LINE_PREFIX)
    return json.loads(line[len(LINE_PREFIX):])


def test_no_sink_prints_nothing():
    set_refusal_sink(None)
    report_refusal("anthropic", RuntimeError("x"))  # must not raise


def test_a_credit_refusal_is_one_line_of_codes(lines):
    exc = _ReplyError(400, {"type": "error", "error": {
        "type": "invalid_request_error", "message": "Your credit balance is too low"}},
        text="Your credit balance is too low. my secret plan")
    report_refusal("anthropic", exc)
    assert len(lines) == 1
    p = _parse(lines[0])
    assert p["kind"] == "out_of_credit" and p["provider"] == "anthropic"
    assert p["http_status"] == 400 and p["phase"] == "http" and p["provider_signature"] is True
    assert "\n" not in lines[0] and len(lines[0].encode()) <= 480


def test_the_line_never_carries_the_exception_text(lines):
    report_refusal("anthropic", _ReplyError(401, {"error": {"type": "authentication_error"}}))
    assert "secret plan" not in lines[0]
    lines.clear()
    refusal_report._last.clear()
    report_refusal("anthropic", _ReplyError(
        400, {"type": "error", "error": {"type": "invalid_request_error"}},
        text="Your credit balance is too low. my secret plan"))
    assert "secret plan" not in lines[0] and "participant" not in lines[0]


def test_the_same_refusal_is_said_once_in_the_window(lines):
    for _ in range(5):
        report_refusal("anthropic", _ReplyError(401, {"error": {"type": "authentication_error"}}))
    assert len(lines) == 1
    report_refusal("openai", _ReplyError(401, {"error": {"code": "invalid_api_key"}}))
    assert len(lines) == 2


def test_a_dropped_connection_is_network_with_no_status(lines):
    report_refusal("openai", httpx.ConnectError("boom"))
    p = _parse(lines[0])
    assert p["kind"] == "network" and p["http_status"] is None and p["phase"] == "connect"


class TestPhase:
    def test_a_name_that_will_not_resolve_is_dns_not_connect(self):
        try:
            try:
                raise socket.gaierror(8, "nodename nor servname provided")
            except OSError as inner:
                raise httpx.ConnectError("x") from inner
        except httpx.ConnectError as e:
            assert phase_of(e, None) == "dns"

    def test_a_refused_certificate_is_tls_not_connect(self):
        try:
            try:
                raise ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")
            except ssl.SSLError as inner:
                raise httpx.ConnectError("x") from inner
        except httpx.ConnectError as e:
            assert phase_of(e, None) == "tls"

    def test_a_timeout_waiting_for_the_reply(self):
        assert phase_of(httpx.ReadTimeout("x"), None) == "response"

    def test_a_status_is_http(self):
        assert phase_of(RuntimeError("x"), 503) == "http"


def test_analyze_reports_from_its_one_failure_path(lines, monkeypatch):
    """The hook is in LLMClient.analyze, so every serve call is covered, not one site."""
    from pydantic import BaseModel

    from bristlenose.config import BristlenoseSettings
    from bristlenose.llm.client import LLMClient

    class M(BaseModel):
        x: int = 0

    client = LLMClient(BristlenoseSettings(llm_provider="anthropic", anthropic_api_key="k"))

    async def boom(*a, **k):
        raise _ReplyError(401, {"type": "error", "error": {"type": "authentication_error"}})

    monkeypatch.setattr(client, "_analyze_anthropic", boom)
    with pytest.raises(_ReplyError):
        asyncio.run(client.analyze("s", "u", M))
    assert _parse(lines[0])["kind"] == "invalid_key"
    assert refusal_report._sink is not None


class TestServeRegistersTheSink:
    """Only the desktop-hosted serve prints refusal lines; a CLI serve and a run print none."""

    def _app(self, monkeypatch):
        from pathlib import Path

        from bristlenose.server.app import create_app

        monkeypatch.setattr(
            "bristlenose.server.lifecycle.install_handshake_cleanup", lambda _id: None)
        fixture = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
        return create_app(project_dir=fixture, dev=True, db_url="sqlite://")

    def test_a_desktop_hosted_serve_prints_the_line(self, monkeypatch, capsys):
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        set_refusal_sink(None)
        self._app(monkeypatch)
        capsys.readouterr()
        try:
            report_refusal("anthropic", _ReplyError(
                401, {"type": "error", "error": {"type": "authentication_error"}}))
            out = capsys.readouterr().out
        finally:
            set_refusal_sink(None)
        assert out.startswith(LINE_PREFIX) and out.endswith("\n")

    def test_a_cli_serve_registers_nothing(self, monkeypatch, capsys):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        set_refusal_sink(None)
        self._app(monkeypatch)
        capsys.readouterr()
        report_refusal("anthropic", _ReplyError(401, {"error": {}}))
        assert capsys.readouterr().out == ""
