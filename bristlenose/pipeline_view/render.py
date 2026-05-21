"""Resolve, per stage, what Bristlenose currently uses.

The single load-bearing claim of the Pipeline view is: the "Currently using"
column matches what `bristlenose run` would actually dispatch given the
current settings. `build_pipeline_view()` reads settings + (where needed) the
real dispatch helpers and produces a stable `PipelineView` payload.

For transcription, we reuse `_resolve_backend()` from `s05_transcribe.py` —
do NOT invent a parallel resolver here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.catalogue import STAGES, PipelineStageDef
from bristlenose.pipeline_view.host import HostFacts, probe_host

ProviderId = Literal["anthropic", "openai", "azure", "google", "local"]

PROVIDER_DISPLAY = {
    "anthropic": "Claude",
    "openai": "ChatGPT",
    "azure": "Azure OpenAI",
    "google": "Gemini",
    "local": "Local (Ollama)",
}


class StageSelection(BaseModel):
    """The user-visible row rendered per stage in the Pipeline view."""

    id: str
    name: str
    kind: str
    chosen: str  # human-readable e.g. "MLX Whisper large-v3-turbo"
    notes: str
    available: bool  # False when the stage is currently disabled/skipped


class PipelineView(BaseModel):
    """Top-level payload returned by `bristlenose pipeline --json` and the API.

    Split into `catalogue` (shareable across machines) and `host` (loopback
    snapshot — excluded from any future support-bundle export).
    """

    catalogue: list[StageSelection]
    host: HostFacts


def _resolve_transcription(settings: BristlenoseSettings) -> str:
    """Return a human-readable "Currently using" string for transcription."""
    from bristlenose.stages.s05_transcribe import _resolve_backend
    from bristlenose.utils.hardware import detect_hardware

    try:
        hw = detect_hardware()
        backend = _resolve_backend(settings.whisper_backend, hw)
    except Exception:
        backend = settings.whisper_backend or "auto"

    label = {
        "mlx": "MLX Whisper",
        "faster-whisper": "faster-whisper",
    }.get(backend, backend)
    return f"{label} {settings.whisper_model}"


def _resolve_llm_provider(settings: BristlenoseSettings) -> str:
    """Format the active LLM provider + model for an LLM stage row."""
    provider = settings.llm_provider
    display = PROVIDER_DISPLAY.get(provider, provider)
    if provider == "local":
        return f"{display} · {settings.local_model}"
    if provider == "azure":
        # Azure surfaces a deployment name, not a stable public model id.
        deployment = settings.azure_deployment or "(deployment unset)"
        return f"{display} · {deployment}"
    return f"{display} · {settings.llm_model}"


def _resolve_anonymisation(settings: BristlenoseSettings) -> tuple[str, bool]:
    """Anonymisation runs Presidio only when --redact-pii / pii_enabled is set."""
    if settings.pii_enabled:
        return ("Presidio (local)", True)
    return ("Off (enable with --redact-pii)", False)


def what_does_this_stage_currently_use(
    stage: PipelineStageDef,
    settings: BristlenoseSettings,
) -> StageSelection:
    """Map one catalogue stage to its current-dispatch StageSelection."""
    available = True
    if stage.kind == "transcription":
        chosen = _resolve_transcription(settings)
    elif stage.kind == "llm":
        chosen = _resolve_llm_provider(settings)
    elif stage.kind == "anonymisation":
        chosen, available = _resolve_anonymisation(settings)
    elif stage.kind == "apple_fm":
        chosen = "Unknown from CLI"
        available = False
    else:
        chosen = "—"
        available = False

    return StageSelection(
        id=stage.id,
        name=stage.name,
        kind=stage.kind,
        chosen=chosen,
        notes=stage.notes,
        available=available,
    )


def build_pipeline_view(settings: BristlenoseSettings) -> PipelineView:
    """Produce the full Pipeline view payload for one set of settings."""
    catalogue = [what_does_this_stage_currently_use(s, settings) for s in STAGES]
    return PipelineView(catalogue=catalogue, host=probe_host(settings))
