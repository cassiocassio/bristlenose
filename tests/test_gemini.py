"""Tests for Gemini provider: schema flattener, client method, doctor checks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.config import BristlenoseSettings, load_settings
from bristlenose.llm.client import LLMClient, _flatten_schema_for_gemini
from bristlenose.llm.pricing import PRICING, PRICING_URLS, estimate_cost
from bristlenose.providers import PROVIDERS, resolve_provider

# ---------------------------------------------------------------------------
# Schema flattener
# ---------------------------------------------------------------------------


class TestFlattenSchemaForGemini:
    def test_simple_schema_unchanged(self) -> None:
        """Schema with no $defs or anyOf passes through cleanly."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name", "count"],
        }
        result = _flatten_schema_for_gemini(schema)
        assert result["type"] == "object"
        assert result["properties"]["name"] == {"type": "string"}
        assert result["properties"]["count"] == {"type": "integer"}

    def test_resolves_defs_and_refs(self) -> None:
        """$defs + $ref pointers are inlined."""
        schema = {
            "$defs": {
                "Item": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}},
                    "required": ["label"],
                }
            },
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Item"},
                }
            },
            "required": ["items"],
        }
        result = _flatten_schema_for_gemini(schema)
        # $defs should be gone
        assert "$defs" not in result
        # items should be inlined
        inner = result["properties"]["items"]["items"]
        assert inner["type"] == "object"
        assert inner["properties"]["label"] == {"type": "string"}

    def test_simplifies_anyof_with_null(self) -> None:
        """anyOf [string, null] is simplified to string."""
        schema = {
            "type": "object",
            "properties": {
                "comment": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "default": None,
                }
            },
        }
        result = _flatten_schema_for_gemini(schema)
        prop = result["properties"]["comment"]
        assert "anyOf" not in prop
        assert prop["type"] == "string"
        assert "default" not in prop

    def test_strips_title_keys(self) -> None:
        """title keys are removed throughout the schema."""
        schema = {
            "title": "MyModel",
            "type": "object",
            "properties": {
                "name": {"title": "Name", "type": "string"},
            },
        }
        result = _flatten_schema_for_gemini(schema)
        assert "title" not in result
        assert "title" not in result["properties"]["name"]

    def test_does_not_mutate_original(self) -> None:
        """Original schema is not modified."""
        schema = {
            "$defs": {"Item": {"type": "object", "properties": {"x": {"type": "integer"}}}},
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/Item"}}},
        }
        original_str = json.dumps(schema)
        _flatten_schema_for_gemini(schema)
        assert json.dumps(schema) == original_str

    def test_preserves_non_null_anyof(self) -> None:
        """anyOf with >1 non-null variant is preserved."""
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "anyOf": [{"type": "string"}, {"type": "integer"}],
                }
            },
        }
        result = _flatten_schema_for_gemini(schema)
        # Should still have anyOf since both are non-null
        assert "anyOf" in result["properties"]["value"]

    def test_real_quote_extraction_schema(self) -> None:
        """Flattens the actual QuoteExtractionResult schema without errors."""
        from bristlenose.llm.structured import QuoteExtractionResult

        schema = QuoteExtractionResult.model_json_schema()
        result = _flatten_schema_for_gemini(schema)

        # $defs resolved
        assert "$defs" not in result
        # anyOf fields simplified
        items_props = result["properties"]["quotes"]["items"]["properties"]
        assert "anyOf" not in items_props.get("researcher_context", {})
        assert "anyOf" not in items_props.get("sentiment", {})
        # Core fields intact
        assert items_props["text"]["type"] == "string"
        assert items_props["start_timecode"]["type"] == "string"

    def test_all_response_models(self) -> None:
        """Every LLM response model flattens without error."""
        from bristlenose.llm.structured import (
            QuoteExtractionResult,
            ScreenClusteringResult,
            SpeakerRoleAssignment,
            ThematicGroupingResult,
            TopicSegmentationResult,
        )

        for model_cls in [
            SpeakerRoleAssignment,
            TopicSegmentationResult,
            QuoteExtractionResult,
            ScreenClusteringResult,
            ThematicGroupingResult,
        ]:
            schema = model_cls.model_json_schema()
            result = _flatten_schema_for_gemini(schema)
            assert "$defs" not in result
            assert "title" not in result
            # Should still be a valid object schema
            assert result["type"] == "object"


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


class TestGoogleProviderSpec:
    def test_google_spec(self) -> None:
        spec = PROVIDERS["google"]
        assert spec.name == "google"
        assert spec.display_name == "Gemini"
        assert "gemini" in spec.aliases
        assert spec.default_model == "gemini-2.5-flash"
        assert spec.sdk_module == "google.genai"
        assert len(spec.config_fields) == 1

    def test_resolve_gemini_alias(self) -> None:
        assert resolve_provider("gemini") == "google"
        assert resolve_provider("Gemini") == "google"
        assert resolve_provider("google") == "google"

    def test_load_settings_normalises_gemini(self) -> None:
        settings = load_settings(llm_provider="gemini")
        assert settings.llm_provider == "google"

    def test_load_settings_preserves_google(self) -> None:
        settings = load_settings(llm_provider="google")
        assert settings.llm_provider == "google"


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


class TestGeminiPricing:
    def test_gemini_flash_in_pricing_table(self) -> None:
        assert "gemini-2.5-flash" in PRICING

    def test_gemini_pro_in_pricing_table(self) -> None:
        assert "gemini-2.5-pro" in PRICING

    def test_gemini_flash_cost_estimate(self) -> None:
        cost = estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        assert cost is not None
        assert cost == 0.15 + 3.50

    def test_google_in_pricing_urls(self) -> None:
        assert "google" in PRICING_URLS


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------


def _google_settings(**overrides: object) -> BristlenoseSettings:
    """Create settings configured for Google provider."""
    defaults: dict[str, object] = {
        "llm_provider": "google",
        "google_api_key": "AIzaSyTest123456789",
        "llm_model": "gemini-2.5-flash",
        "output_dir": Path("/tmp/bristlenose-test-output"),
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


class TestLLMClientGoogleValidation:
    def test_missing_google_key_raises(self) -> None:
        settings = _google_settings(google_api_key="")
        with pytest.raises(ValueError, match="Gemini API key not set"):
            LLMClient(settings)

    def test_present_google_key_ok(self) -> None:
        settings = _google_settings()
        client = LLMClient(settings)
        assert client.provider == "google"


class TestLLMClientAnalyzeGoogle:
    @pytest.mark.asyncio
    async def test_analyze_google_structured_output(self) -> None:
        """Mock Gemini SDK and verify structured output parsing."""
        from pydantic import BaseModel, Field

        class SimpleResult(BaseModel):
            answer: str = Field(description="The answer")

        settings = _google_settings()
        client = LLMClient(settings)

        # Build a mock response
        mock_response = MagicMock()
        mock_response.text = '{"answer": "hello"}'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50

        # Mock the genai module
        mock_genai_client = MagicMock()
        mock_aio = MagicMock()
        mock_aio.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai_client.aio = mock_aio

        client._google_client = mock_genai_client

        # Make the mock coroutine

        async def mock_generate(*args, **kwargs):
            return mock_response

        mock_aio.models.generate_content = mock_generate

        result = await client.analyze(
            system_prompt="You are helpful.",
            user_prompt="Say hello.",
            response_model=SimpleResult,
        )

        assert isinstance(result, SimpleResult)
        assert result.answer == "hello"
        assert client.tracker.input_tokens == 100
        assert client.tracker.output_tokens == 50
        assert client.tracker.calls == 1

    @pytest.mark.asyncio
    async def test_analyze_google_empty_response(self) -> None:
        """Empty response raises RuntimeError."""
        from pydantic import BaseModel, Field

        class SimpleResult(BaseModel):
            answer: str = Field(description="The answer")

        settings = _google_settings()
        client = LLMClient(settings)

        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.usage_metadata = None

        mock_genai_client = MagicMock()
        mock_aio = MagicMock()
        mock_genai_client.aio = mock_aio

        client._google_client = mock_genai_client

        async def mock_generate(*args, **kwargs):
            return mock_response

        mock_aio.models.generate_content = mock_generate

        with pytest.raises(RuntimeError, match="Empty response from Gemini"):
            await client.analyze(
                system_prompt="test",
                user_prompt="test",
                response_model=SimpleResult,
            )


# ---------------------------------------------------------------------------
# Doctor checks
# ---------------------------------------------------------------------------


def _doctor_settings(**overrides: object) -> BristlenoseSettings:
    defaults: dict[str, object] = {
        "llm_provider": "google",
        "google_api_key": "AIzaSyTest123456789",
        "output_dir": Path("/tmp/bristlenose-test-output"),
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


class TestDoctorGoogleProvider:
    def test_google_key_present_and_valid(self) -> None:
        from bristlenose.doctor import CheckStatus, check_api_key

        settings = _doctor_settings()
        with patch("bristlenose.doctor._validate_google_key", return_value=(True, "")):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK
        assert "Gemini" in result.detail

    def test_google_key_missing(self) -> None:
        from bristlenose.doctor import CheckStatus, check_api_key

        settings = _doctor_settings(google_api_key="")
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_google"

    def test_google_key_invalid(self) -> None:
        from bristlenose.doctor import CheckStatus, check_api_key

        settings = _doctor_settings()
        with patch(
            "bristlenose.doctor._validate_google_key",
            return_value=(False, "403 Forbidden"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_invalid_google"

    def test_google_key_network_error(self) -> None:
        """Network error during validation → still OK (key is present)."""
        from bristlenose.doctor import CheckStatus, check_api_key

        settings = _doctor_settings()
        with patch(
            "bristlenose.doctor._validate_google_key",
            return_value=(None, "Connection refused"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK
        assert "could not validate" in result.detail

    def test_google_network_check(self) -> None:
        from bristlenose.doctor import CheckStatus, check_network

        settings = _doctor_settings()
        with patch("urllib.request.urlopen"):
            result = check_network(settings)

        assert result.status == CheckStatus.OK
        assert "generativelanguage.googleapis.com" in result.detail


class TestDoctorFixesGoogle:
    def test_fix_api_key_missing_google(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        fix = get_fix("api_key_missing_google", "pip")
        assert "aistudio.google.com" in fix
        assert "bristlenose configure gemini" in fix
        assert "Claude" in fix or "claude" in fix

    def test_fix_api_key_invalid_google(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        fix = get_fix("api_key_invalid_google", "pip")
        assert "aistudio.google.com" in fix
        assert "bristlenose configure gemini" in fix

    def test_cloud_fallback_includes_gemini(self) -> None:
        """When user has Google key, cloud fallback suggests --llm gemini."""
        from bristlenose.doctor_fixes import get_fix

        with patch(
            "bristlenose.config.load_settings",
            return_value=MagicMock(
                anthropic_api_key="",
                openai_api_key="",
                azure_api_key="",
                azure_endpoint="",
                google_api_key="AIzaSyXXX",
            ),
        ):
            fix = get_fix("ollama_not_running", "pip")
            assert "--llm gemini" in fix
