"""An Azure deployment's output ceiling is learned from Azure's own refusal.

Observed live on 12 Nov 2026 against a real Foundry resource, on both the
`openai.azure.com` and `services.ai.azure.com` hosts: a `gpt-4.1-mini` deployment
answered the run's default `max_tokens` of 64000 with HTTP 400, code `invalid_value`,

    max_tokens is too large: 64000. This model supports at most 32768 completion
    tokens, whereas you provided 64000.

`_clamp_max_tokens` is keyed on the model NAME and an Azure request model is the
customer's own deployment name, so nothing clamped it: the run, its preflight and
`bristlenose doctor` all failed for such a deployment. The fix reads the ceiling out of
the refusal and retries ONCE at it. Every test here uses that real wording (never an
invented message) and asserts the `max_tokens` of the request that was actually sent,
because a bare mock accepts any keyword and so cannot see a request-shape break.
"""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest
from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings
from bristlenose.llm.client import (
    LLMClient,
    azure_error_message,
    azure_output_ceiling,
    forget_azure_ceilings,
    learned_azure_ceiling,
    remember_azure_ceiling,
    request_params,
)
from bristlenose.preflight.api_key import _validate_azure

# Azure's words, copied from the live probe.
REAL = (
    "max_tokens is too large: 64000. This model supports at most 32768 completion tokens, "
    "whereas you provided 64000."
)
ENDPOINT = "https://x.openai.azure.com/"
DEPLOYMENT = "my-research-deployment"


@pytest.fixture(autouse=True)
def _forget_ceilings():
    forget_azure_ceilings()
    yield
    forget_azure_ceilings()


def _refusal(message: str = REAL, code: str = "invalid_value") -> openai.BadRequestError:
    """A real SDK exception carrying Azure's structured 400 body."""
    body = {"error": {"code": code, "message": message}}
    response = httpx.Response(400, request=httpx.Request("POST", ENDPOINT), json=body)
    return openai.BadRequestError(message=message, response=response, body=body)


def _http_400(message: str = REAL, code: str = "invalid_value") -> urllib.error.HTTPError:
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    return urllib.error.HTTPError(ENDPOINT, 400, "Bad Request", {}, io.BytesIO(body))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Reading the ceiling
# ---------------------------------------------------------------------------


class TestReadingTheCeiling:
    def test_the_observed_wording_names_the_ceiling(self) -> None:
        assert azure_output_ceiling(REAL, 64000) == 32768

    @pytest.mark.parametrize("requested", [32768, 16000, 1])
    def test_a_ceiling_not_below_the_request_is_not_a_retry(self, requested: int) -> None:
        # Retrying at the same value would only repeat the refusal.
        assert azure_output_ceiling(REAL, requested) is None

    @pytest.mark.parametrize(
        "message",
        [
            None,
            "",
            "Invalid 'temperature': decimal above maximum value. Expected a value <= 2, but got 9 instead.",
            "The API deployment for this resource does not exist.",
            # The `max_completion_tokens` spelling has not been seen live; it is not matched.
            "max_completion_tokens is too large: 64000. This model supports at most 32768 "
            "completion tokens, whereas you provided 64000.",
            "max_tokens is too large: 64000.",
        ],
    )
    def test_anything_else_is_not_a_ceiling(self, message) -> None:
        assert azure_output_ceiling(message, 64000) is None

    def test_a_non_positive_request_is_never_a_retry(self) -> None:
        assert azure_output_ceiling(REAL, 0) is None

    def test_the_message_is_read_from_the_structured_body(self) -> None:
        assert azure_error_message(_refusal()) == REAL

    def test_without_a_body_it_falls_back_to_the_exception_text(self) -> None:
        assert azure_error_message(RuntimeError("boom")) == "boom"


# ---------------------------------------------------------------------------
# The run (LLMClient._analyze_azure)
# ---------------------------------------------------------------------------


class _Answer(BaseModel):
    answer: str


def _reply() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content='{"answer": "hi"}', refusal=None),
        )],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        model="gpt-4.1-mini-2025-04-14",
    )


def _client(create: AsyncMock) -> LLMClient:
    client = LLMClient(BristlenoseSettings(  # type: ignore[arg-type]
        llm_provider="azure", azure_api_key="test-key", azure_endpoint=ENDPOINT,
        azure_deployment=DEPLOYMENT, llm_max_tokens=64000,
    ))
    fake = MagicMock()
    fake.chat.completions.create = create
    client._azure_client = fake
    return client


def _caps(create: AsyncMock) -> list[int]:
    return [call.kwargs["max_tokens"] for call in create.call_args_list]


class TestTheRun:
    def test_a_refused_cap_is_retried_once_at_the_ceiling_azure_named(self) -> None:
        create = AsyncMock(side_effect=[_refusal(), _reply()])
        result = asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert result.answer == "hi"
        assert _caps(create) == [64000, 32768]

    def test_the_ceiling_is_remembered_so_the_next_call_starts_there(self) -> None:
        create = AsyncMock(side_effect=[_refusal(), _reply(), _reply()])
        client = _client(create)
        asyncio.run(client.analyze("sys", "usr", _Answer))
        asyncio.run(client.analyze("sys", "usr", _Answer))
        # The second analyse never asks for 64000 again.
        assert _caps(create) == [64000, 32768, 32768]
        assert learned_azure_ceiling(ENDPOINT, DEPLOYMENT) == 32768

    def test_a_ceiling_learned_elsewhere_in_the_process_is_used_first(self) -> None:
        # The preflight (another client) learned it; the run must not 400 again.
        remember_azure_ceiling(ENDPOINT, DEPLOYMENT, 32768)
        create = AsyncMock(side_effect=[_reply()])
        asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert _caps(create) == [32768]

    def test_a_learned_ceiling_never_raises_a_smaller_request(self) -> None:
        remember_azure_ceiling(ENDPOINT, DEPLOYMENT, 32768)
        create = AsyncMock(side_effect=[_reply()])
        asyncio.run(_client(create).analyze("sys", "usr", _Answer, max_tokens=4000))
        assert _caps(create) == [4000]

    def test_the_ceiling_is_read_from_the_structured_body_not_only_the_exception_text(self) -> None:
        # The SDK's own text for a 400 may not carry Azure's sentence; the body does.
        body = {"error": {"code": "invalid_value", "message": REAL}}
        response = httpx.Response(400, request=httpx.Request("POST", ENDPOINT), json=body)
        refusal = openai.BadRequestError(message="Error code: 400", response=response, body=body)
        create = AsyncMock(side_effect=[refusal, _reply()])
        asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert _caps(create) == [64000, 32768]

    def test_another_400_is_not_retried(self) -> None:
        refusal = _refusal("Invalid 'temperature': decimal above maximum value.", "decimal_above_max_value")
        create = AsyncMock(side_effect=[refusal])
        with pytest.raises(openai.BadRequestError):
            asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert len(create.call_args_list) == 1

    def test_a_retry_that_is_refused_again_is_reported_not_looped(self) -> None:
        create = AsyncMock(side_effect=[_refusal(), _refusal(
            "Invalid 'temperature': decimal above maximum value.", "decimal_above_max_value")])
        with pytest.raises(openai.BadRequestError):
            asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert _caps(create) == [64000, 32768]

    def test_the_deployment_name_does_not_decide_the_ceiling(self) -> None:
        # The table is keyed on model names; an arbitrary deployment name gets none.
        remember_azure_ceiling(ENDPOINT, "a-different-deployment", 8192)
        create = AsyncMock(side_effect=[_refusal(), _reply()])
        asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert _caps(create) == [64000, 32768]


# ---------------------------------------------------------------------------
# The run's preflight (preflight.api_key._validate_azure)
# ---------------------------------------------------------------------------


class TestThePreflight:
    def _patch(self, monkeypatch, side_effect) -> MagicMock:
        client = MagicMock()
        client.chat.completions.create.side_effect = side_effect
        monkeypatch.setattr(openai, "AzureOpenAI", lambda **kw: client)
        return client.chat.completions.create

    def _params(self) -> dict:
        return request_params("azure", DEPLOYMENT, 64000, 0.1)

    def test_a_refused_cap_is_retried_once_at_the_ceiling(self, monkeypatch) -> None:
        create = self._patch(monkeypatch, [_refusal(), MagicMock()])
        result = _validate_azure("k", ENDPOINT, DEPLOYMENT, "2024-10-21", params=self._params())
        assert result.ok
        assert [c.kwargs["max_tokens"] for c in create.call_args_list] == [64000, 32768]
        assert learned_azure_ceiling(ENDPOINT, DEPLOYMENT) == 32768

    def test_a_ceiling_the_run_learned_is_used_first(self, monkeypatch) -> None:
        remember_azure_ceiling(ENDPOINT, DEPLOYMENT, 32768)
        create = self._patch(monkeypatch, [MagicMock()])
        assert _validate_azure("k", ENDPOINT, DEPLOYMENT, "2024-10-21", params=self._params()).ok
        assert [c.kwargs["max_tokens"] for c in create.call_args_list] == [32768]

    def test_another_400_is_not_retried_and_says_azures_words(self, monkeypatch) -> None:
        text = "Invalid 'temperature': decimal above maximum value."
        create = self._patch(monkeypatch, [_refusal(text, "decimal_above_max_value")])
        result = _validate_azure("k", ENDPOINT, DEPLOYMENT, "2024-10-21", params=self._params())
        assert not result.ok
        assert len(create.call_args_list) == 1
        assert "temperature" in (result.raw_message or "")

    def test_a_retry_refused_again_is_reported_not_looped(self, monkeypatch) -> None:
        create = self._patch(monkeypatch, [_refusal(), _refusal(
            "Invalid 'temperature': decimal above maximum value.", "decimal_above_max_value")])
        result = _validate_azure("k", ENDPOINT, DEPLOYMENT, "2024-10-21", params=self._params())
        assert not result.ok
        assert len(create.call_args_list) == 2


# ---------------------------------------------------------------------------
# bristlenose doctor (doctor._validate_azure_key)
# ---------------------------------------------------------------------------


class TestDoctor:
    def _run(self, responses, **kwargs):
        from bristlenose.doctor import _validate_azure_key

        sent: list[int] = []
        queue = list(responses)

        def fake_urlopen(req, **_kw):
            sent.append(json.loads(req.data)["max_tokens"])
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return MagicMock()

        params = request_params("azure", DEPLOYMENT, 64000, 0.1)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _validate_azure_key(
                ENDPOINT, "test-key", DEPLOYMENT, "2024-10-21", params=params, **kwargs)
        return result, sent

    def test_a_refused_cap_is_retried_once_at_the_ceiling(self) -> None:
        result, sent = self._run([_http_400(), None])
        assert result == (True, "")
        assert sent == [64000, 32768]
        assert learned_azure_ceiling(ENDPOINT, DEPLOYMENT) == 32768

    def test_a_ceiling_the_run_learned_is_used_first(self) -> None:
        remember_azure_ceiling(ENDPOINT, DEPLOYMENT, 32768)
        result, sent = self._run([None])
        assert result == (True, "")
        assert sent == [32768]

    def test_another_400_is_not_retried_and_says_azures_words(self) -> None:
        text = "Invalid 'temperature': decimal above maximum value."
        result, sent = self._run([_http_400(text, "decimal_above_max_value")])
        assert sent == [64000]
        assert result == (False, f"HTTP 400: {text}")

    def test_a_retry_refused_again_is_reported_not_looped(self) -> None:
        text = "Invalid 'temperature': decimal above maximum value."
        result, sent = self._run([_http_400(), _http_400(text, "decimal_above_max_value")])
        assert sent == [64000, 32768]
        assert result == (False, f"HTTP 400: {text}")

    def test_an_unreadable_400_body_is_still_a_plain_refusal(self) -> None:
        bad = urllib.error.HTTPError(ENDPOINT, 400, "Bad Request", {}, io.BytesIO(b"<html>proxy</html>"))  # type: ignore[arg-type]
        result, sent = self._run([bad])
        assert sent == [64000]
        assert result == (False, "HTTP 400")
