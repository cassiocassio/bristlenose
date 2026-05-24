"""Load-bearing test: the 'Currently using' string matches real dispatch.

Per the plan: this is the test that matters. Parametrise over the settings
shapes researchers actually run, and for each, assert what the Pipeline view
will say for the LLM stages and for transcription.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.render import (
    PROVIDER_DISPLAY,
    PipelineView,
    build_pipeline_view,
)

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "pipeline-view-contract.json"


def _settings(**overrides: object) -> BristlenoseSettings:
    """Build a settings object that ignores env/keychain side effects."""
    defaults: dict[str, object] = {
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-20250514",
        "anthropic_api_key": "sk-test",
        "openai_api_key": "",
        "azure_api_key": "",
        "google_api_key": "",
        "whisper_backend": "auto",
        "whisper_model": "large-v3-turbo",
        "pii_enabled": False,
        "local_model": "llama3.2:3b",
        "azure_deployment": "",
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "provider,model,expected_chosen",
    [
        ("anthropic", "claude-sonnet-4-20250514", "Claude · claude-sonnet-4-20250514"),
        ("openai", "gpt-4o", "ChatGPT · gpt-4o"),
        ("google", "gemini-1.5-pro", "Gemini · gemini-1.5-pro"),
        ("local", "llama3.2:3b", "Local (Ollama) · llama3.2:3b"),
    ],
)
def test_llm_stage_chosen_matches_provider(
    provider: str, model: str, expected_chosen: str
) -> None:
    settings = _settings(
        llm_provider=provider,
        llm_model=model,
        local_model="llama3.2:3b",
    )
    view = build_pipeline_view(settings)
    quote_extraction = next(s for s in view.catalogue if s.id == "quote_extraction")
    assert quote_extraction.chosen == expected_chosen
    assert quote_extraction.available is True


def test_azure_uses_deployment_not_model_id() -> None:
    settings = _settings(
        llm_provider="azure",
        azure_api_key="key",
        azure_deployment="my-gpt-4o-deployment",
    )
    view = build_pipeline_view(settings)
    quote_extraction = next(s for s in view.catalogue if s.id == "quote_extraction")
    assert "my-gpt-4o-deployment" in quote_extraction.chosen
    assert "Azure OpenAI" in quote_extraction.chosen


def test_anonymisation_off_by_default() -> None:
    view = build_pipeline_view(_settings(pii_enabled=False))
    anon = next(s for s in view.catalogue if s.id == "anonymisation")
    assert anon.available is False
    assert "Off" in anon.chosen


def test_anonymisation_on_when_pii_enabled() -> None:
    view = build_pipeline_view(_settings(pii_enabled=True))
    anon = next(s for s in view.catalogue if s.id == "anonymisation")
    assert anon.available is True
    assert "Built-in anonymiser" in anon.chosen


def test_apple_fm_always_unknown_from_cli() -> None:
    view = build_pipeline_view(_settings())
    apple = next(s for s in view.catalogue if s.id == "apple_foundation_models")
    assert apple.available is False
    assert apple.chosen == "Unknown from CLI"
    assert view.host.apple_fm_status == "unknown"


def test_provider_display_covers_every_provider_id() -> None:
    """If we add a provider, this catches the missing display label."""
    for provider in ("anthropic", "openai", "azure", "google", "local"):
        assert provider in PROVIDER_DISPLAY


def test_contract_fixture_round_trips_through_pydantic() -> None:
    """The shared JSON fixture must validate as a PipelineView in both directions."""
    data = json.loads(_FIXTURE.read_text())
    scenario = data["scenarios"]["claude_apple_silicon_keys_present"]
    view = PipelineView.model_validate(
        {
            "schema_version": scenario["schema_version"],
            "catalogue": scenario["catalogue"],
            "llm_summary": scenario["llm_summary"],
            "host": scenario["host"],
        }
    )
    re_serialised = json.loads(view.model_dump_json())
    assert re_serialised["catalogue"] == scenario["catalogue"]
    assert re_serialised["host"] == scenario["host"]
    assert re_serialised["llm_summary"] == scenario["llm_summary"]
    assert re_serialised["schema_version"] == 2
