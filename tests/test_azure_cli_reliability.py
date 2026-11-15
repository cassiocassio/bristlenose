"""Azure failure handling in the CLI paths (preflight and doctor).

Three defects from ``docs/design-azure-state-matrix.md`` section 3 (disagreements
3, 4 and 8), each reproduced against the real code:

F1. Preflight read only the OUTER exception's class name, so the openai SDK's
    ``APIConnectionError`` / ``APITimeoutError`` (cause: httpx ConnectError and
    friends) fell to the generic "credit-balance" copy instead of ``network``.
F2. Doctor reported Azure 429 / 500 / 503 as a good key with no detail at all.
F3. A redirect passed silently. Preflight took an HTML 200 (after a followed
    redirect) as a chat completion and cached the pass for 24 hours; doctor's
    urllib followed a 301/302 (POST becoming GET) to a 200.

The openai errors are produced by the SDK's own path (a patched transport under a
real ``AzureOpenAI`` client), never hand-built.
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import openai._base_client as _sdk
import pytest
from rich.console import Console

from bristlenose.config import BristlenoseSettings
from bristlenose.preflight.api_key import (
    ApiKeyPreflightAbortedError,
    _validate_azure,
    preflight_api_key,
    read_state,
)

# The SDK's own HTTP library: httpx, or httpx2 where the SDK has moved to it. Exceptions
# and responses must come from the one the SDK catches, so build them from it.
httpx = getattr(_sdk, "httpx2", None) or _sdk.httpx
# Patch the base client class, not the SDK's wrapper: our Azure clients pass
# their own (redirects refused), so a patch on the wrapper would miss them and
# the test would reach the real network.
_Client = httpx.Client

ENDPOINT = "https://x.openai.azure.com/"
DEPLOYMENT = "my-research-deployment"


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    # The SDK retries a connection failure twice with a backoff sleep.
    monkeypatch.setattr("openai._base_client.time.sleep", lambda _s: None)


def _validate():
    return _validate_azure("az-key", ENDPOINT, DEPLOYMENT, "2024-10-21")


# ---------------------------------------------------------------------------
# F1: offline / DNS / timeout are "network" in preflight
# ---------------------------------------------------------------------------


class TestPreflightClassifiesTransportFailures:
    def test_connect_error_through_the_sdk_is_network(self) -> None:
        def boom(self, request, **kw):
            raise httpx.ConnectError("[Errno 8] nodename nor servname provided", request=request)

        with patch.object(_Client, "send", boom):
            result = _validate()
        assert not result.ok
        assert result.error_class == "network"

    def test_timeout_through_the_sdk_is_network(self) -> None:
        def boom(self, request, **kw):
            raise httpx.ConnectTimeout("timed out", request=request)

        with patch.object(_Client, "send", boom):
            result = _validate()
        assert not result.ok
        assert result.error_class == "network"

    def test_a_provider_answer_is_still_not_network(self) -> None:
        # A 403 is Azure answering: it must keep its own words, not become "network".
        def answer(self, request, **kw):
            return httpx.Response(403, json={"error": {"message": "blocked"}}, request=request)

        with patch.object(_Client, "send", answer):
            result = _validate()
        assert not result.ok
        assert result.error_class != "network"


# ---------------------------------------------------------------------------
# F2: doctor says so when it could not validate
# ---------------------------------------------------------------------------


@pytest.fixture
def azure_server() -> Iterator[dict]:
    """A plain-HTTP fake Azure on localhost whose reply is set per test."""
    state: dict = {"status": 200, "headers": {}, "body": b"{}", "hits": []}

    class Handler(http.server.BaseHTTPRequestHandler):
        def _reply(self) -> None:
            state["hits"].append((self.command, self.path))
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self.send_response(state["status"])
            for k, v in state["headers"].items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(state["body"])))
            self.end_headers()
            self.wfile.write(state["body"])

        do_POST = do_GET = _reply  # noqa: N815

        def log_message(self, *a) -> None:  # noqa: ANN002
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["endpoint"] = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


def _doctor(endpoint: str) -> tuple[bool | None, str]:
    from bristlenose.doctor import _validate_azure_key

    return _validate_azure_key(endpoint, "test-key", DEPLOYMENT, "2024-10-21")


class TestDoctorDoesNotSilentlyPass:
    @pytest.mark.parametrize("code", [429, 500, 503, 502])
    def test_a_throttled_or_down_azure_is_ok_but_says_it_could_not_validate(
        self, azure_server, code
    ) -> None:
        azure_server["status"] = code
        valid, detail = _doctor(azure_server["endpoint"])
        # Still not a FAIL: the key is not known to be bad...
        assert valid is None
        # ...but not a silent pass either.
        assert detail == f"HTTP {code}"


# ---------------------------------------------------------------------------
# F3: a redirect is not a pass
# ---------------------------------------------------------------------------


class TestDoctorDoesNotFollowRedirects:
    @pytest.mark.parametrize("code", [301, 302, 307])
    def test_a_redirect_is_could_not_validate_and_is_not_followed(
        self, azure_server, code
    ) -> None:
        azure_server["status"] = code
        azure_server["headers"] = {"Location": "/portal-login"}
        valid, detail = _doctor(azure_server["endpoint"])
        assert valid is None
        assert detail == f"HTTP {code}"
        # Followed, the POST would have been repeated as a GET of /portal-login.
        assert [m for m, _ in azure_server["hits"]] == ["POST"]


class TestTheSdkClientsDoNotFollowRedirects:
    """The openai SDK's own httpx client follows redirects, and the ``api-key``
    header (httpx strips only ``Authorization``) and the transcript in the body
    would go wherever a 3xx points. Both of our Azure clients refuse."""

    @pytest.mark.parametrize("code", [302, 307, 308])
    def test_preflight_check_is_not_ok_and_sends_nothing_onward(
        self, azure_server, code
    ) -> None:
        azure_server["status"] = code
        azure_server["headers"] = {"Location": "/elsewhere"}
        result = _validate_azure("az-key", azure_server["endpoint"], DEPLOYMENT, "2024-10-21")
        assert not result.ok
        assert len(azure_server["hits"]) == 1, azure_server["hits"]

    @pytest.mark.parametrize("code", [302, 307, 308])
    def test_the_runs_client_raises_and_sends_nothing_onward(
        self, azure_server, code
    ) -> None:
        import asyncio

        import openai

        from bristlenose.llm.client import LLMClient

        azure_server["status"] = code
        azure_server["headers"] = {"Location": "/elsewhere"}
        settings = BristlenoseSettings(
            llm_provider="azure", azure_api_key="az-key",
            azure_endpoint=azure_server["endpoint"], azure_deployment=DEPLOYMENT,
        )
        client = LLMClient(settings)._ensure_azure_client()

        async def call() -> None:
            await client.chat.completions.create(
                model=DEPLOYMENT, messages=[{"role": "user", "content": "hi"}], max_tokens=1,
            )

        with pytest.raises(openai.APIStatusError):
            asyncio.run(call())
        assert len(azure_server["hits"]) == 1, azure_server["hits"]


def _html_200(self, request, **kw):
    return httpx.Response(
        200, text="<html><body>Sign in</body></html>",
        headers={"content-type": "text/html"}, request=request,
    )


class TestPreflightDoesNotTakeAnHtmlPageForAPass:
    def test_a_non_completion_reply_is_not_ok(self) -> None:
        with patch.object(_Client, "send", _html_200):
            result = _validate()
        assert not result.ok

    def test_and_the_pass_is_not_cached(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr("bristlenose.preflight.api_key.state_path",
                            lambda: tmp_path / "state.json")
        monkeypatch.setattr("bristlenose.preflight.api_key.sys.stdin.isatty", lambda: False)
        monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)
        settings = BristlenoseSettings(
            llm_provider="azure", azure_api_key="az-key",
            azure_endpoint=ENDPOINT, azure_deployment=DEPLOYMENT,
        )
        with patch.object(_Client, "send", _html_200), pytest.raises(
            ApiKeyPreflightAbortedError
        ):
            preflight_api_key(settings=settings, console=Console(quiet=True))
        assert "azure" not in read_state().get("providers", {})
