"""Cohort normalisation — provider/model string → (family, major) key."""

from __future__ import annotations

import pytest

from bristlenose.llm.cohort_normalise import normalise_model


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        # Anthropic
        ("anthropic", "claude-sonnet-4-20250514", ("claude-sonnet", "4")),
        ("anthropic", "claude-opus-4-7", ("claude-opus", "4")),
        ("anthropic", "claude-haiku-4-5-20251001", ("claude-haiku", "4")),
        ("anthropic", "claude-sonnet-3-5-20240620", ("claude-sonnet", "3")),
        # OpenAI
        ("openai", "gpt-4o", ("gpt-4o", "4")),
        ("openai", "gpt-4o-mini", ("gpt-4o-mini", "4")),
        ("openai", "gpt-4o-2024-08-06", ("gpt-4o", "4")),
        ("openai", "gpt-5", ("gpt-5", "5")),
        ("openai", "gpt-5-mini", ("gpt-5-mini", "5")),
        ("openai", "o1", ("o1", "1")),
        ("openai", "o3-mini", ("o3-mini", "3")),
        # Azure (deployment name passthrough)
        ("azure", "my-prod-deployment", ("my-prod-deployment", "0")),
        ("azure", "GPT4-Whatever", ("gpt4-whatever", "0")),
        # Google
        ("google", "gemini-2.5-pro", ("gemini-pro", "2")),
        ("google", "gemini-2.5-flash", ("gemini-flash", "2")),
        ("google", "gemini-1.5-pro", ("gemini-pro", "1")),
        # Local (Ollama) — quantisation/size tag is part of the cohort key
        # (token throughput differs materially between :3b and :8b)
        ("local", "llama3.2:3b", ("llama-3b", "3")),
        ("local", "llama3.1:8b", ("llama-8b", "3")),
        ("local", "llama3.2", ("llama", "3")),  # no tag → no suffix
        ("local", "mistral:7b", ("mistral-7b", "0")),
        ("local", "qwen2.5:7b", ("qwen-7b", "2")),
    ],
)
def test_normalise_known_models(
    provider: str, model: str, expected: tuple[str, str]
) -> None:
    assert normalise_model(provider, model) == expected


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        normalise_model("not-a-provider", "anything")


@pytest.mark.parametrize(
    "provider", ["anthropic", "openai", "azure", "google", "local"]
)
def test_empty_model_returns_unknown(provider: str) -> None:
    family, major = normalise_model(provider, "")
    assert family == "unknown"
    assert major == "0"


def test_unknown_anthropic_model_falls_back_to_string() -> None:
    family, major = normalise_model("anthropic", "future-claude-thing")
    assert family == "future-claude-thing"
    assert major == "0"
