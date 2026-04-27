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


class TestTruncationEmitsTelemetryRow:
    """Truncation must emit one JSONL row with outcome='truncated' before raising."""

    @pytest.mark.asyncio
    async def test_anthropic_truncation_records_row(self, tmp_path: object) -> None:
        from bristlenose.llm import telemetry

        settings = _make_settings()
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            stop_reason="max_tokens",
            content=[],
            usage=SimpleNamespace(input_tokens=120, output_tokens=8192),
            model="claude-sonnet-4-20250514",
        )
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._anthropic_client = mock_anthropic

        run_dir = tmp_path / ".bristlenose"  # type: ignore[operator]
        tokens = telemetry.set_run_context("run-trunc", run_dir)
        try:
            with telemetry.stage("s09_quote_extraction"):
                with pytest.raises(RuntimeError, match="truncated"):
                    await client.analyze(
                        system_prompt="sys",
                        user_prompt="usr",
                        response_model=QuoteExtractionResult,
                    )
        finally:
            telemetry.reset_run_context(tokens)

        rows = list(telemetry.iter_rows(run_dir))
        assert len(rows) == 1
        row = rows[0]
        assert row["outcome"] == "truncated"
        assert row["gen_ai.usage.output_tokens"] == 8192
        assert row["gen_ai.usage.input_tokens"] == 120
        assert row["finish_reason"] == "max_tokens"
        assert row["stage"] == "s09_quote_extraction"

    @pytest.mark.asyncio
    async def test_local_retry_summing(self, tmp_path: object) -> None:
        """Local retry path: 3 attempts with usage each → one row, summed tokens."""
        from bristlenose.llm import telemetry
        from bristlenose.llm.structured import QuoteExtractionResult

        settings = _make_settings(llm_provider="local", local_model="llama3.2:3b")
        client = LLMClient(settings)

        # Always return invalid JSON content so all retries fail with JSONDecodeError.
        bad_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content="not-valid-json"),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=50, completion_tokens=10),
            model="llama3.2:3b",
        )
        mock_local = AsyncMock()
        mock_local.chat.completions.create = AsyncMock(return_value=bad_response)
        client._local_client = mock_local

        run_dir = tmp_path / ".bristlenose"  # type: ignore[operator]
        tokens = telemetry.set_run_context("run-retry", run_dir)
        try:
            with telemetry.stage("s09_quote_extraction"):
                with pytest.raises(RuntimeError, match="failed to produce valid JSON"):
                    await client.analyze(
                        system_prompt="sys",
                        user_prompt="usr",
                        response_model=QuoteExtractionResult,
                    )
        finally:
            telemetry.reset_run_context(tokens)

        rows = list(telemetry.iter_rows(run_dir))
        assert len(rows) == 1, "should emit exactly one terminal row across retries"
        row = rows[0]
        assert row["outcome"] == "error"
        assert row["retry_count"] == 2  # max_retries=3 → retry_count = 3 - 1
        assert row["gen_ai.usage.input_tokens"] == 150  # 50 × 3 retries
        assert row["gen_ai.usage.output_tokens"] == 30  # 10 × 3 retries


class TestLocalTruncationSingleRow:
    """Local-provider truncation must emit exactly ONE row, not two.

    Regression guard: code-review on slice B suspected the truncation raise
    inside ``_analyze_local`` could be re-caught by the inner API-call
    ``except Exception`` and emit a second ``error`` row. Verify it doesn't.
    """

    @pytest.mark.asyncio
    async def test_local_truncation_emits_one_row(self, tmp_path: object) -> None:
        from bristlenose.llm import telemetry

        settings = _make_settings(llm_provider="local", local_model="llama3.2:3b")
        client = LLMClient(settings)

        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"quotes": []}'),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=80, completion_tokens=4096),
            model="llama3.2:3b",
        )
        mock_local = AsyncMock()
        mock_local.chat.completions.create = AsyncMock(return_value=mock_response)
        client._local_client = mock_local

        run_dir = tmp_path / ".bristlenose"  # type: ignore[operator]
        tokens = telemetry.set_run_context("run-local-trunc", run_dir)
        try:
            with telemetry.stage("s09_quote_extraction"):
                with pytest.raises(RuntimeError, match="truncated"):
                    await client.analyze(
                        system_prompt="sys",
                        user_prompt="usr",
                        response_model=QuoteExtractionResult,
                    )
        finally:
            telemetry.reset_run_context(tokens)

        rows = list(telemetry.iter_rows(run_dir))
        assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {rows}"
        assert rows[0]["outcome"] == "truncated"
        assert rows[0]["finish_reason"] == "length"


class TestPromptPathRepoRelative:
    """The prompt_path field in telemetry rows must be repo-relative (no /Users/...)."""

    @pytest.mark.asyncio
    async def test_prompt_path_is_repo_relative(self, tmp_path: object) -> None:
        from bristlenose.llm import telemetry
        from bristlenose.llm.prompts import get_prompt_template

        settings = _make_settings()
        client = LLMClient(settings)

        tmpl = get_prompt_template("quote-extraction")

        tool_block = SimpleNamespace(
            type="tool_use",
            name="structured_output",
            input={"quotes": []},
        )
        mock_response = SimpleNamespace(
            stop_reason="end_turn",
            content=[tool_block],
            usage=SimpleNamespace(input_tokens=100, output_tokens=5),
            model="claude-sonnet-4-20250514",
        )
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._anthropic_client = mock_anthropic

        run_dir = tmp_path / ".bristlenose"  # type: ignore[operator]
        tokens = telemetry.set_run_context("run-pp", run_dir)
        try:
            with telemetry.stage("s09_quote_extraction"):
                await client.analyze(
                    system_prompt="sys",
                    user_prompt="usr",
                    response_model=QuoteExtractionResult,
                    prompt_template=tmpl,
                )
        finally:
            telemetry.reset_run_context(tokens)

        rows = list(telemetry.iter_rows(run_dir))
        assert len(rows) == 1
        path = rows[0]["prompt_path"]
        assert isinstance(path, str)
        assert path.startswith("bristlenose/llm/prompts/")
        assert "/Users/" not in path
        assert path.endswith(".md")


class TestContextvarLeakBetweenRuns:
    """run_lifecycle reset_run_context must clear contextvars so consecutive runs don't leak."""

    @pytest.mark.asyncio
    async def test_contextvars_reset_after_run(self, tmp_path: object) -> None:
        from bristlenose.llm import telemetry

        run_dir_a = tmp_path / "a" / ".bristlenose"  # type: ignore[operator]
        run_dir_b = tmp_path / "b" / ".bristlenose"  # type: ignore[operator]

        # Run A: emit a row.
        tokens_a = telemetry.set_run_context("run-a", run_dir_a)
        try:
            with telemetry.stage("s09_quote_extraction"):
                telemetry.record_call(
                    provider="anthropic",
                    request_model="claude-sonnet-4-20250514",
                    response_model="claude-sonnet-4-20250514",
                    input_chars=10,
                    elapsed_ms=1,
                    outcome="ok",
                    price_table_version="2026-04-25",
                )
        finally:
            telemetry.reset_run_context(tokens_a)

        # After reset, no run context — record_call must no-op.
        telemetry.record_call(
            provider="anthropic",
            request_model="x",
            response_model="x",
            input_chars=1,
            elapsed_ms=1,
            outcome="ok",
            price_table_version="2026-04-25",
            stage_override="s09_quote_extraction",
        )
        # The post-reset call should not have written anywhere — verify by
        # confirming run_dir_a is unchanged (still 1 row) and run_dir_b doesn't exist.
        assert len(list(telemetry.iter_rows(run_dir_a))) == 1
        assert not run_dir_b.exists()

        # Run B: emit a row, must land in run_dir_b only.
        tokens_b = telemetry.set_run_context("run-b", run_dir_b)
        try:
            with telemetry.stage("s09_quote_extraction"):
                telemetry.record_call(
                    provider="anthropic",
                    request_model="claude-sonnet-4-20250514",
                    response_model="claude-sonnet-4-20250514",
                    input_chars=10,
                    elapsed_ms=1,
                    outcome="ok",
                    price_table_version="2026-04-25",
                )
        finally:
            telemetry.reset_run_context(tokens_b)

        assert len(list(telemetry.iter_rows(run_dir_a))) == 1
        assert len(list(telemetry.iter_rows(run_dir_b))) == 1


class TestDefaultMaxTokens:
    def test_default_is_64000(self) -> None:
        """Default llm_max_tokens should be 64000 — headroom for dense 1-hour transcripts.

        Raised from 32768 on 17 Apr 2026 after FOSSDA baseline hit truncation on s5
        (quote extraction). Anthropic's claude-sonnet-4-20250514 hard-caps output at
        64000 tokens (decimal, not 65536). GPT-5 allows 128K and Gemini 2.5 Pro allows
        65K, so 64000 is the portable ceiling across all three providers.
        """
        settings = BristlenoseSettings()
        assert settings.llm_max_tokens == 64000
