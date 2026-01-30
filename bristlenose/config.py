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
    llm_provider: str = "anthropic"  # "anthropic" or "openai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.1

    # Whisper
    whisper_backend: str = "auto"  # "auto", "mlx", "faster-whisper"
    whisper_model: str = "large-v3-turbo"
    whisper_language: str = "en"
    whisper_device: str = "auto"  # "cpu", "cuda", "auto" (faster-whisper only)
    whisper_compute_type: str = "int8"  # faster-whisper only

    # PII
    pii_enabled: bool = True
    pii_llm_pass: bool = False
    pii_custom_names: list[str] = Field(default_factory=list)

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
    """Load settings with optional CLI overrides."""
    return BristlenoseSettings(**overrides)  # type: ignore[arg-type]
