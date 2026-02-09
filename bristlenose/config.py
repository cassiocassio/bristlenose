"""Application settings loaded from environment variables, .env, or bristlenose.toml."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_files() -> list[Path]:
    """Find .env files to load, searching upward from CWD and in the package dir.

    Checks (in priority order, last wins in pydantic-settings):
    1. The bristlenose package directory (next to this file)
    2. The current working directory
    3. Parent directories up to the filesystem root

    This means ``bristlenose`` finds its .env whether you run it from the
    project root, a trial-runs subfolder, or anywhere on your system.
    """
    candidates: list[Path] = []

    # Package directory (where bristlenose is installed / editable-linked)
    pkg_env = Path(__file__).resolve().parent.parent / ".env"
    if pkg_env.is_file():
        candidates.append(pkg_env)

    # Walk up from CWD to find .env files
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        env_path = parent / ".env"
        if env_path.is_file() and env_path not in candidates:
            candidates.append(env_path)
            break  # stop at first match going upward

    return candidates


class BristlenoseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BRISTLENOSE_",
        env_file=_find_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project
    project_name: str = "User Research"

    # LLM
    llm_provider: str = "anthropic"  # "anthropic", "openai", "azure", "google", or "local"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.1

    # Azure OpenAI
    azure_api_key: str = ""
    azure_endpoint: str = ""  # e.g. https://my-resource.openai.azure.com/
    azure_deployment: str = ""  # Deployment name from Azure portal
    azure_api_version: str = "2024-10-21"

    # Google (Gemini)
    google_api_key: str = ""

    # Local LLM (Ollama)
    local_url: str = "http://localhost:11434/v1"
    local_model: str = "llama3.2:3b"

    # Whisper
    whisper_backend: str = "auto"  # "auto", "mlx", "faster-whisper"
    whisper_model: str = "large-v3-turbo"
    whisper_language: str = "en"
    whisper_device: str = "auto"  # "cpu", "cuda", "auto" (faster-whisper only)
    whisper_compute_type: str = "int8"  # faster-whisper only

    # PII
    pii_enabled: bool = False
    pii_llm_pass: bool = False
    pii_custom_names: list[str] = Field(default_factory=list)

    # Theme
    color_scheme: str = "auto"  # "auto", "light", or "dark"

    # Pipeline
    skip_transcription: bool = False
    write_intermediate: bool = True
    output_dir: Path = Path("output")
    input_dir: Path = Path("input")

    # Quote extraction
    min_quote_words: int = 5
    merge_speaker_gap_seconds: float = 2.0

    # Concurrency
    llm_concurrency: int = 3


def load_settings(**overrides: object) -> BristlenoseSettings:
    """Load settings with optional CLI overrides.

    Normalises LLM provider aliases (claude → anthropic, chatgpt/gpt → openai,
    ollama → local).

    Also populates API keys from the system keychain if not already set
    from environment variables or .env file.
    """
    # Import here to avoid circular import at module load time
    from bristlenose.providers import get_provider_aliases

    # Normalise LLM provider aliases
    if "llm_provider" in overrides and isinstance(overrides["llm_provider"], str):
        provider = overrides["llm_provider"].lower()
        aliases = get_provider_aliases()
        overrides["llm_provider"] = aliases.get(provider, provider)

    settings = BristlenoseSettings(**overrides)  # type: ignore[arg-type]

    # Populate API keys from keychain if not set from env/.env
    settings = _populate_keys_from_keychain(settings)

    return settings


def _populate_keys_from_keychain(settings: BristlenoseSettings) -> BristlenoseSettings:
    """Check keychain for API keys not already set from env vars.

    Returns a new settings object with keys populated from keychain.
    """
    from bristlenose.credentials import get_credential_store

    store = get_credential_store()
    updates: dict[str, str] = {}

    # Only check keychain if the key isn't already set
    if not settings.anthropic_api_key:
        key = store.get("anthropic")
        if key:
            updates["anthropic_api_key"] = key

    if not settings.openai_api_key:
        key = store.get("openai")
        if key:
            updates["openai_api_key"] = key

    if not settings.azure_api_key:
        key = store.get("azure")
        if key:
            updates["azure_api_key"] = key

    if not settings.google_api_key:
        key = store.get("google")
        if key:
            updates["google_api_key"] = key

    if not updates:
        return settings

    # Create new settings with keychain values
    # We need to merge the original values with keychain values
    return settings.model_copy(update=updates)
