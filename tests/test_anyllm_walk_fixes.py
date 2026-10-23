"""Fixes from the any-llm real-account walks (23 Oct 2026).

Each case was seen against a real provider: OpenRouter blaming the key for a
busy model host, a shadow warning about two identical keys, and the pipeline
table's "(current)" badge wrapping to column 0 under a provider:model id.
"""

from __future__ import annotations

import pytest

from bristlenose.llm import anyllm


class _ProviderError(Exception):
    pass


def _openrouter_429(limit_source: str) -> BaseException:
    """The shape the OpenRouter walk recorded: any-llm's error around openai's,
    whose ``body`` is OpenRouter's ``error`` object."""
    sdk = _ProviderError("Error code: 429 - Provider returned error")
    sdk.body = {  # type: ignore[attr-defined]
        "message": "Provider returned error", "code": 429,
        "metadata": {"provider_name": "Mistral", "is_byok": False, "limit_source": limit_source},
    }
    wrapped = _ProviderError("[openrouter] Provider returned error")
    wrapped.original_exception = sdk  # type: ignore[attr-defined]
    return wrapped


def test_the_host_behind_a_gateway_is_read_from_its_error() -> None:
    busy = _openrouter_429("upstream_provider_shared_pool")
    assert anyllm.upstream(busy) == ("Mistral", "upstream_provider_shared_pool")
    assert anyllm.upstream(_ProviderError("401 bad key")) is None


def test_the_same_key_twice_is_not_a_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class AnyLLM:
        @classmethod
        def get_supported_providers(cls) -> list[str]:
            return ["mistral"]

        @classmethod
        def get_provider_class(cls, provider: str) -> object:
            return types.SimpleNamespace(MISSING_PACKAGES_ERROR=None, ENV_API_KEY_NAME="MISTRAL_API_KEY")

        @classmethod
        def create(cls, provider: str, api_key: str | None = None) -> object:
            return object()

    module = types.ModuleType("any_llm")
    module.AnyLLM = AnyLLM  # type: ignore[attr-defined]
    exceptions = types.ModuleType("any_llm.exceptions")
    exceptions.MissingApiKeyError = type("MissingApiKeyError", (Exception,), {})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "any_llm", module)
    monkeypatch.setitem(sys.modules, "any_llm.exceptions", exceptions)
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-same")
    model = "mistral:mistral-large-latest"
    assert anyllm.readiness_for_model(model, api_key="sk-same").shadowed_by == ""
    assert anyllm.readiness_for_model(model, api_key="sk-other").shadowed_by == "MISTRAL_API_KEY"


def test_a_long_model_name_keeps_its_badge_indented() -> None:
    from bristlenose.pipeline_view import cli as pipeline_cli
    from bristlenose.pipeline_view.render import ModelAvailability, StageSelection

    row = ModelAvailability(
        provider_id="anyllm", provider_display="any-llm",
        model_id="mistral:mistral-small-latest", display="mistral:mistral-small-latest",
        available=True,
    )
    sel = StageSelection(
        id="quote_extraction", name="Quote extraction", kind="llm", chosen="any-llm",
        notes="", chosen_id="anyllm", chosen_model_id="mistral:mistral-small-latest",
        available=True, alternatives=[row],
    )
    name = pipeline_cli._provider_block([row], sel)[1][0]
    assert name.endswith("\n      (current)")
