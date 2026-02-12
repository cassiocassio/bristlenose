"""Tests for LLM response truncation detection across providers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.llm.client import LLMClient
from bristlenose.llm.structured import QuoteExtractionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: object) -> BristlenoseSettings:
    """Build minimal settings for testing (no real API key needed)."""
    defaults: dict[str, object] = {
        "llm_provider": "anthropic",
        "anthropic_api_key": "sk-ant-test-key",
        "llm_model": "claude-sonnet-4-20250514",
        "llm_max_tokens": 8192,
        "llm_temperature": 0.1,
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Anthropic truncation
# ---------------------------------------------------------------------------


class TestAnthropicTruncation:
    @pytest.mark.asyncio
    async def test_raises_on_max_tokens_stop_reason(self) -> None:
        """When Anthropic returns stop_reason='max_tokens', raise RuntimeError."""
        settings = _make_settings()
        client = LLMClient(settings)

        # Mock response with truncated output
        mock_response = SimpleNamespace(
            stop_reason="max_tokens",
            content=[],
            usage=SimpleNamespace(input_tokens=100, output_tokens=8192),
        )
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._anthropic_client = mock_anthropic

        with pytest.raises(RuntimeError, match="truncated"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )

    @pytest.mark.asyncio
    async def test_error_mentions_max_tokens_value(self) -> None:
        """Error message should include the max_tokens value for debugging."""
        settings = _make_settings(llm_max_tokens=4096)
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            stop_reason="max_tokens",
            content=[],
            usage=SimpleNamespace(input_tokens=100, output_tokens=4096),
        )
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._anthropic_client = mock_anthropic

        with pytest.raises(RuntimeError, match="max_tokens=4096"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )

    @pytest.mark.asyncio
    async def test_error_mentions_env_var(self) -> None:
        """Error message should tell the user how to fix it."""
        settings = _make_settings()
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            stop_reason="max_tokens",
            content=[],
            usage=SimpleNamespace(input_tokens=100, output_tokens=8192),
        )
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._anthropic_client = mock_anthropic

        with pytest.raises(RuntimeError, match=r"BRISTLENOSE_LLM_MAX_TOKENS=65536 in your \.env"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )

    @pytest.mark.asyncio
    async def test_normal_response_not_affected(self) -> None:
        """A normal tool_use response should parse successfully."""
        settings = _make_settings()
        client = LLMClient(settings)

        tool_block = SimpleNamespace(
            type="tool_use",
            name="structured_output",
            input={"quotes": []},
        )
        mock_response = SimpleNamespace(
            stop_reason="tool_use",
            content=[tool_block],
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._anthropic_client = mock_anthropic

        result = await client.analyze(
            system_prompt="test",
            user_prompt="test",
            response_model=QuoteExtractionResult,
        )
        assert result.quotes == []


# ---------------------------------------------------------------------------
# OpenAI truncation
# ---------------------------------------------------------------------------


class TestOpenAITruncation:
    @pytest.mark.asyncio
    async def test_raises_on_length_finish_reason(self) -> None:
        """When OpenAI returns finish_reason='length', raise RuntimeError."""
        settings = _make_settings(
            llm_provider="openai",
            openai_api_key="sk-test-key",
        )
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"quotes": []}'),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=8192),
        )
        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
        client._openai_client = mock_openai

        with pytest.raises(RuntimeError, match="truncated"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )


# ---------------------------------------------------------------------------
# Azure truncation
# ---------------------------------------------------------------------------


class TestAzureTruncation:
    @pytest.mark.asyncio
    async def test_raises_on_length_finish_reason(self) -> None:
        """When Azure returns finish_reason='length', raise RuntimeError."""
        settings = _make_settings(
            llm_provider="azure",
            azure_api_key="test-key",
            azure_endpoint="https://test.openai.azure.com/",
            azure_deployment="test-deployment",
        )
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"quotes": []}'),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=8192),
        )
        mock_azure = AsyncMock()
        mock_azure.chat.completions.create = AsyncMock(return_value=mock_response)
        client._azure_client = mock_azure

        with pytest.raises(RuntimeError, match="truncated"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )


# ---------------------------------------------------------------------------
# Gemini truncation
# ---------------------------------------------------------------------------


class TestGeminiTruncation:
    @pytest.mark.asyncio
    async def test_raises_on_max_tokens_finish_reason(self) -> None:
        """When Gemini returns finish_reason MAX_TOKENS, raise RuntimeError."""
        settings = _make_settings(
            llm_provider="google",
            google_api_key="test-key",
        )
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            candidates=[
                SimpleNamespace(finish_reason="MAX_TOKENS")
            ],
            text='{"quotes": []}',
            usage_metadata=SimpleNamespace(
                prompt_token_count=100,
                candidates_token_count=8192,
            ),
        )
        mock_client = SimpleNamespace(
            models=AsyncMock(
                generate_content=AsyncMock(return_value=mock_response)
            ),
        )
        mock_google = SimpleNamespace(aio=mock_client)
        client._google_client = mock_google

        with pytest.raises(RuntimeError, match="truncated"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )


# ---------------------------------------------------------------------------
# Local (Ollama) truncation
# ---------------------------------------------------------------------------


class TestLocalTruncation:
    @pytest.mark.asyncio
    async def test_raises_on_length_finish_reason(self) -> None:
        """When local model returns finish_reason='length', raise RuntimeError."""
        settings = _make_settings(llm_provider="local")
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"quotes": []}'),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=8192),
        )
        mock_local = AsyncMock()
        mock_local.chat.completions.create = AsyncMock(return_value=mock_response)
        client._local_client = mock_local

        with pytest.raises(RuntimeError, match="truncated"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=QuoteExtractionResult,
            )


# ---------------------------------------------------------------------------
# Default max_tokens value
# ---------------------------------------------------------------------------


class TestDefaultMaxTokens:
    def test_default_is_32768(self) -> None:
        """Default llm_max_tokens should be 32768 — enough for 1-hour transcripts."""
        settings = BristlenoseSettings()
        assert settings.llm_max_tokens == 32768
