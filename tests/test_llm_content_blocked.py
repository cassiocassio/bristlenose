"""A provider's content filter or refusal is named, not 'rejected' or 'unknown' (N168).

Sensitive interviews (health, especially on Azure) can be blocked by the provider. Each
provider said it differently ("No structured output found", "Empty response from OpenAI",
"Empty response from Gemini", a bare 400 "BadRequestError on azure"), so the failure read as
"the provider rejected the request" or "unknown". Owner ruling 1 Nov 2026: name the cause in
the existing message, under the existing category, no new locale key. The session still
retries on the next Analyse (stopping that is a separate, worded decision).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.events import CauseCategoryEnum
from bristlenose.llm.client import ContentBlockedError, LLMClient, is_content_blocked
from bristlenose.llm.structured import QuoteExtractionResult
from bristlenose.run_lifecycle import _build_cause


def _settings(**kw: object) -> BristlenoseSettings:
    base: dict[str, object] = {
        "llm_provider": "anthropic", "anthropic_api_key": "sk-ant-test",
        "llm_model": "claude-sonnet-4-6", "llm_max_tokens": 8192, "llm_temperature": 0.1,
    }
    base.update(kw)
    return BristlenoseSettings(**base)  # type: ignore[arg-type]


async def _ask(client: LLMClient) -> None:
    await client.analyze(system_prompt="s", user_prompt="u", response_model=QuoteExtractionResult)


class TestEachProviderNamesAnBlock:
    @pytest.mark.asyncio
    async def test_claude_refusal_stop_reason(self) -> None:
        client = LLMClient(_settings())
        client._anthropic_client = AsyncMock()
        client._anthropic_client.messages.create = AsyncMock(return_value=SimpleNamespace(
            stop_reason="refusal", content=[],
            usage=SimpleNamespace(input_tokens=10, output_tokens=0),
        ))
        with pytest.raises(ContentBlockedError):
            await _ask(client)

    @pytest.mark.asyncio
    async def test_chatgpt_content_filter_finish_reason(self) -> None:
        client = LLMClient(_settings(
            llm_provider="openai", openai_api_key="sk-test", llm_model="gpt-5.6-terra"))
        client._openai_client = AsyncMock()
        client._openai_client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="content_filter", message=SimpleNamespace(content=None, refusal=None),
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0), model="gpt",
        ))
        with pytest.raises(ContentBlockedError):
            await _ask(client)

    @pytest.mark.asyncio
    async def test_chatgpt_strict_mode_refusal_text(self) -> None:
        client = LLMClient(_settings(
            llm_provider="openai", openai_api_key="sk-test", llm_model="gpt-5.6-terra"))
        client._openai_client = AsyncMock()
        client._openai_client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=None, refusal="I can't help with that."),
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5), model="gpt",
        ))
        with pytest.raises(ContentBlockedError):
            await _ask(client)

    @pytest.mark.asyncio
    async def test_an_empty_chatgpt_reply_with_no_refusal_is_still_just_empty(self) -> None:
        client = LLMClient(_settings(
            llm_provider="openai", openai_api_key="sk-test", llm_model="gpt-5.6-terra"))
        client._openai_client = AsyncMock()
        client._openai_client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(content=None, refusal=None),
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0), model="gpt",
        ))
        with pytest.raises(RuntimeError, match="Empty response") as err:
            await _ask(client)
        assert not isinstance(err.value, ContentBlockedError)

    @pytest.mark.asyncio
    async def test_azure_content_filter_finish_reason(self) -> None:
        client = LLMClient(_settings(
            llm_provider="azure", azure_api_key="k", azure_endpoint="https://x.openai.azure.com/",
            azure_deployment="d", llm_model="d"))
        client._azure_client = AsyncMock()
        client._azure_client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="content_filter", message=SimpleNamespace(content=None, refusal=None),
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0), model="d",
        ))
        with pytest.raises(ContentBlockedError):
            await _ask(client)

    @pytest.mark.asyncio
    async def test_gemini_safety_block(self) -> None:
        client = LLMClient(_settings(
            llm_provider="google", google_api_key="g", llm_model="gemini-3.8-flash"))
        client._google_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(
            generate_content=AsyncMock(return_value=SimpleNamespace(
                text=None,
                candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="SAFETY"))],
                prompt_feedback=None,
                usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=0),
            )),
        )))
        with pytest.raises(ContentBlockedError):
            await _ask(client)

    @pytest.mark.asyncio
    async def test_gemini_blocked_prompt(self) -> None:
        client = LLMClient(_settings(
            llm_provider="google", google_api_key="g", llm_model="gemini-3.8-flash"))
        client._google_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(
            generate_content=AsyncMock(return_value=SimpleNamespace(
                text=None, candidates=[],
                prompt_feedback=SimpleNamespace(block_reason=SimpleNamespace(name="PROHIBITED_CONTENT")),
                usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=0),
            )),
        )))
        with pytest.raises(ContentBlockedError):
            await _ask(client)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("reason", ["MODEL_ARMOR", "JAILBREAK"])
    async def test_gemini_filters_that_block_a_prompt_are_named_too(self, reason: str) -> None:
        # BlockedReason also has MODEL_ARMOR and JAILBREAK: filters, so a refusal, not an
        # "Empty response". RECITATION (a copy of a source) and OTHER are deliberately not.
        client = LLMClient(_settings(
            llm_provider="google", google_api_key="g", llm_model="gemini-3.8-flash"))
        client._google_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(
            generate_content=AsyncMock(return_value=SimpleNamespace(
                text=None, candidates=[],
                prompt_feedback=SimpleNamespace(block_reason=SimpleNamespace(name=reason)),
                usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=0),
            )),
        )))
        with pytest.raises(ContentBlockedError):
            await _ask(client)


async def _ask_result(client: LLMClient) -> object:
    return await client.analyze(
        system_prompt="s", user_prompt="u", response_model=QuoteExtractionResult)


def _recording(client: LLMClient) -> list[str]:
    """Outcomes ``client`` hands to telemetry, in order."""
    outcomes: list[str] = []

    def record(**kw: object) -> None:
        outcomes.append(str(kw["outcome"]))

    client._record_call = record  # type: ignore[method-assign]
    return outcomes


def _claude(stop_reason: str, content: list[object]) -> LLMClient:
    client = LLMClient(_settings())
    client._anthropic_client = AsyncMock()
    client._anthropic_client.messages.create = AsyncMock(return_value=SimpleNamespace(
        stop_reason=stop_reason, content=content,
        usage=SimpleNamespace(input_tokens=10, output_tokens=0),
    ))
    return client


def _openai_shaped(provider: str, finish: str, content: str | None, refusal: str | None) -> LLMClient:
    if provider == "openai":
        client = LLMClient(_settings(
            llm_provider="openai", openai_api_key="sk-test", llm_model="gpt-5.6-terra"))
        client._openai_client = AsyncMock()
        create = client._openai_client.chat.completions
    else:
        client = LLMClient(_settings(
            llm_provider="azure", azure_api_key="k", azure_endpoint="https://x.openai.azure.com/",
            azure_deployment="d", llm_model="d"))
        client._azure_client = AsyncMock()
        create = client._azure_client.chat.completions
    create.create = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(
            finish_reason=finish, message=SimpleNamespace(content=content, refusal=refusal),
        )],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0), model="m",
    ))
    return client


def _gemini(text: str | None, finish: str) -> LLMClient:
    client = LLMClient(_settings(
        llm_provider="google", google_api_key="g", llm_model="gemini-3.8-flash"))
    client._google_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(
        generate_content=AsyncMock(return_value=SimpleNamespace(
            text=text,
            candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
            prompt_feedback=None,
            usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=0),
        )),
    )))
    return client


class TestARefusedCallIsRecordedAsAnError:
    """A call the provider declined is not a successful call (100days: refused-call telemetry).

    Four providers wrote the call row before checking whether the reply was a refusal, so a
    declined session (cheap, no output) landed as ``outcome="ok"`` and
    ``regenerate-cohort-baselines.py``, which keeps only ``ok`` rows, took its cost as a
    typical one. any-llm already recorded ``error``.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("make", [
        pytest.param(lambda: _claude("refusal", []), id="claude"),
        pytest.param(lambda: _openai_shaped("openai", "content_filter", None, None),
                     id="chatgpt-filter"),
        pytest.param(lambda: _openai_shaped("openai", "stop", None, "I can't help."),
                     id="chatgpt-refusal-text"),
        pytest.param(lambda: _openai_shaped("azure", "content_filter", None, None), id="azure"),
        pytest.param(lambda: _gemini(None, "SAFETY"), id="gemini"),
    ])
    async def test_the_row_says_error(self, make: object) -> None:
        client = make()  # type: ignore[operator]
        outcomes = _recording(client)
        with pytest.raises(ContentBlockedError):
            await _ask(client)
        assert outcomes == ["error"]

    @pytest.mark.asyncio
    async def test_a_claude_reply_that_carries_its_answer_is_still_ok(self) -> None:
        """A refusal stop_reason with the tool answer present is read as the answer, as before."""
        answer = SimpleNamespace(type="tool_use", name="structured_output", input={"quotes": []})
        client = _claude("refusal", [answer])
        outcomes = _recording(client)
        result = await _ask_result(client)
        assert result is not None
        assert outcomes == ["ok"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("make", [
        pytest.param(lambda: _openai_shaped("openai", "stop", None, None), id="chatgpt-empty"),
        pytest.param(lambda: _openai_shaped("azure", "stop", None, None), id="azure-empty"),
        pytest.param(lambda: _gemini(None, "STOP"), id="gemini-empty"),
    ])
    async def test_an_empty_reply_with_no_refusal_keeps_its_row(self, make: object) -> None:
        """Not part of this change: an empty reply is still recorded as it was (``ok``)."""
        client = make()  # type: ignore[operator]
        outcomes = _recording(client)
        with pytest.raises(RuntimeError, match="Empty response"):
            await _ask(client)
        assert outcomes == ["ok"]


def _azure_400(code: str, inner_code: str | None = None) -> Exception:
    """A real ``openai.BadRequestError`` as the SDK builds one from Azure's content-filter 400.

    Azure sends ``{"error": {"code": ..., "innererror": {"code": ...}}}``; the SDK's
    ``_make_status_error`` unwraps ``error`` first (openai 3.26), so ``exc.body`` is the inner
    dict and ``exc.code`` is read from it. A fake that kept the ``error`` wrapper pinned a
    branch no real error reaches and left the one that fires unpinned.
    """
    import httpx
    import openai

    body: dict[str, object] = {"code": code, "message": "filtered"}
    if inner_code is not None:
        body["innererror"] = {"code": inner_code, "content_filter_result": {}}
    response = httpx.Response(400, request=httpx.Request("POST", "https://x.openai.azure.com/"))
    exc = openai.BadRequestError(
        "Error code: 400 - the response was filtered", response=response, body=body)
    assert exc.body is body and exc.code == code  # the shape the test relies on
    return exc


class TestTheCauseNamesIt:
    def test_a_blocked_session_says_so_under_the_existing_category(self) -> None:
        cause = _build_cause(
            ContentBlockedError("x"), stage="quote_extraction", provider="openai")
        assert cause.category is CauseCategoryEnum.API_REQUEST
        assert "declined" in cause.message and "quote_extraction" in cause.message

    def test_azures_own_400_with_the_content_filter_code_says_so(self) -> None:
        exc = _azure_400("content_filter", inner_code="ResponsibleAIPolicyViolation")
        assert is_content_blocked(exc)
        cause = _build_cause(exc, stage="quote_extraction", provider="azure", http_status=400)
        assert cause.category is CauseCategoryEnum.API_REQUEST
        assert "declined" in cause.message
        assert cause.code == "400"

    def test_a_400_whose_only_filter_signal_is_the_inner_error_still_says_so(self) -> None:
        # The policy name lives in `innererror`, under the unwrapped body the SDK hands over.
        assert is_content_blocked(_azure_400("BadRequest", inner_code="ResponsibleAIPolicyViolation"))

    def test_any_other_400_still_reads_as_a_plain_failure(self) -> None:
        exc = _azure_400("invalid_request_error")
        assert not is_content_blocked(exc)
        cause = _build_cause(exc, stage="quote_extraction", provider="azure", http_status=400)
        assert "declined" not in cause.message

    def test_the_message_is_a_constant_never_the_providers_words(self) -> None:
        # A provider body can echo the prompt; Cause.message is persisted in the events log.
        exc = ContentBlockedError("participant Jane Roe said the filter fired")
        cause = _build_cause(exc, stage="quote_extraction", provider="openai")
        assert "Jane" not in cause.message
