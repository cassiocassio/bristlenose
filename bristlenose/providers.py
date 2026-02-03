"""LLM provider registry and specifications.

Centralises provider metadata, aliases, and configuration requirements.
Used by config.py, llm/client.py, doctor.py, and cli.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfigField:
    """A configuration field required by a provider."""

    name: str  # e.g. "api_key", "endpoint"
    env_var: str  # e.g. "BRISTLENOSE_ANTHROPIC_API_KEY"
    prompt: str  # e.g. "Claude API key"
    secret: bool = True  # Mask input when prompting
    required: bool = True
    default: str = ""


@dataclass
class ProviderSpec:
    """Specification for an LLM provider."""

    name: str  # Internal name: "anthropic", "openai", "local"
    display_name: str  # User-facing: "Claude", "ChatGPT", "Local (Ollama)"
    aliases: list[str] = field(default_factory=list)  # CLI aliases: ["claude"], ["ollama"]
    config_fields: list[ConfigField] = field(default_factory=list)
    default_model: str = ""
    sdk_module: str = ""  # e.g. "anthropic", "openai"
    pricing_url: str = ""


# Provider registry — single source of truth for all provider metadata.
PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        name="anthropic",
        display_name="Claude",
        aliases=["claude"],
        config_fields=[
            ConfigField(
                "api_key",
                "BRISTLENOSE_ANTHROPIC_API_KEY",
                "Claude API key",
            ),
        ],
        default_model="claude-sonnet-4-20250514",
        sdk_module="anthropic",
        pricing_url="https://docs.anthropic.com/en/docs/about-claude/models",
    ),
    "openai": ProviderSpec(
        name="openai",
        display_name="ChatGPT",
        aliases=["chatgpt", "gpt"],
        config_fields=[
            ConfigField(
                "api_key",
                "BRISTLENOSE_OPENAI_API_KEY",
                "ChatGPT API key",
            ),
        ],
        default_model="gpt-4o",
        sdk_module="openai",
        pricing_url="https://platform.openai.com/docs/pricing",
    ),
    "local": ProviderSpec(
        name="local",
        display_name="Local (Ollama)",
        aliases=["ollama"],
        config_fields=[
            ConfigField(
                "url",
                "BRISTLENOSE_LOCAL_URL",
                "Ollama URL",
                secret=False,
                required=False,
                default="http://localhost:11434/v1",
            ),
            ConfigField(
                "model",
                "BRISTLENOSE_LOCAL_MODEL",
                "Model name",
                secret=False,
                required=False,
                default="llama3.2:3b",
            ),
        ],
        default_model="llama3.2:3b",
        sdk_module="openai",  # Ollama is OpenAI-compatible
        pricing_url="",  # Free
    ),
}


def resolve_provider(name: str) -> str:
    """Resolve a provider alias to its canonical name.

    Args:
        name: Provider name or alias (case-insensitive).

    Returns:
        Canonical provider name.

    Raises:
        ValueError: If the provider is not recognised.
    """
    name = name.lower()
    if name in PROVIDERS:
        return name
    for provider_name, spec in PROVIDERS.items():
        if name in spec.aliases:
            return provider_name
    valid = sorted(PROVIDERS.keys())
    aliases = [a for spec in PROVIDERS.values() for a in spec.aliases]
    raise ValueError(
        f"Unknown LLM provider: {name}. "
        f"Valid providers: {', '.join(valid + aliases)}"
    )


def get_provider_aliases() -> dict[str, str]:
    """Return a dict mapping all aliases to canonical provider names.

    Used by config.py for normalisation.
    """
    aliases: dict[str, str] = {}
    for provider_name, spec in PROVIDERS.items():
        for alias in spec.aliases:
            aliases[alias] = provider_name
    return aliases
