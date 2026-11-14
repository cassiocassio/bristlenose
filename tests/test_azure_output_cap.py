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
    TruncatedResponseError,
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
    """The exception the openai SDK really raises for Azure's 400.

    Built through the SDK's own constructor path (`_make_status_error_from_response`), not by
    hand: the SDK unwraps the `error` envelope, so `exc.body` is the inner dict
    `{code, message, param, type}`. A hand-built `{"error": {...}}` body is a shape production
    never sees (the first version of these tests used it and so proved less than it claimed).
    """
    body = {"error": {"code": code, "message": message, "param": "max_tokens",
                      "type": "invalid_request_error"}}
    response = httpx.Response(400, request=httpx.Request("POST", ENDPOINT), json=body)
    client = openai.AzureOpenAI(api_key="k", azure_endpoint=ENDPOINT, api_version="2024-10-21")
    exc = client._make_status_error_from_response(response)
    assert isinstance(exc, openai.BadRequestError)
    return exc


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

    def test_the_message_is_read_from_the_body_the_sdk_really_builds(self) -> None:
        exc = _refusal()
        assert exc.body == {"code": "invalid_value", "message": REAL, "param": "max_tokens",
                            "type": "invalid_request_error"}
        assert azure_error_message(exc) == REAL

    @pytest.mark.parametrize("body", [
        {"code": "invalid_value", "message": REAL},                       # the unwrapped shape
        {"error": {"code": "invalid_value", "message": REAL}},            # the wrapped shape
    ])
    def test_the_body_wins_over_the_exception_text(self, body) -> None:
        # str(exc) carries nothing useful here, so only a body read can return the message.
        response = httpx.Response(400, request=httpx.Request("POST", ENDPOINT), json=body)
        exc = openai.BadRequestError(message="Error code: 400", response=response, body=body)
        assert azure_error_message(exc) == REAL

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

    @pytest.mark.parametrize("body", [
        {"code": "invalid_value", "message": REAL},
        {"error": {"code": "invalid_value", "message": REAL}},
    ])
    def test_the_ceiling_is_read_from_the_body_not_only_the_exception_text(self, body) -> None:
        response = httpx.Response(400, request=httpx.Request("POST", ENDPOINT), json=body)
        refusal = openai.BadRequestError(message="Error code: 400", response=response, body=body)
        create = AsyncMock(side_effect=[refusal, _reply()])
        asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert _caps(create) == [64000, 32768]

    def test_a_truncation_after_the_retry_reports_the_ceiling_not_the_default(self) -> None:
        truncated = _reply()
        truncated.choices[0].finish_reason = "length"
        create = AsyncMock(side_effect=[_refusal(), truncated])
        with pytest.raises(TruncatedResponseError) as info:
            asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert info.value.requested_max_tokens == 32768
        assert info.value.model_cap == 32768

    def test_a_retried_success_is_recorded_once(self) -> None:
        create = AsyncMock(side_effect=[_refusal(), _reply()])
        with patch.object(LLMClient, "_record_call") as record:
            asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert record.call_count == 1
        assert record.call_args.kwargs["outcome"] == "ok"

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
        assert [c.kwargs["max_tokens"] for c in create.call_args_list] == [64000, 32768]
        # The reported refusal is the RETRY's, not the first attempt's.
        assert "temperature" in (result.raw_message or "")
        assert "too large" not in (result.raw_message or "")


class TestPreflightThenRun:
    def test_what_the_preflight_learned_is_where_the_run_starts(self, monkeypatch) -> None:
        # The join the commit claims ("the run does not re-learn what the preflight learned"):
        # two clients, one process. Seeding the dict by hand would only test the read side.
        preflight = MagicMock()
        preflight.chat.completions.create.side_effect = [_refusal(), MagicMock()]
        monkeypatch.setattr(openai, "AzureOpenAI", lambda **kw: preflight)
        params = request_params("azure", DEPLOYMENT, 64000, 0.1)
        assert _validate_azure("k", ENDPOINT, DEPLOYMENT, "2024-10-21", params=params).ok

        create = AsyncMock(side_effect=[_reply()])
        asyncio.run(_client(create).analyze("sys", "usr", _Answer))
        assert _caps(create) == [32768]


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
        with patch("urllib.request.OpenerDirector.open", side_effect=fake_urlopen):
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
