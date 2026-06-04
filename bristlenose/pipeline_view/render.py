"""Resolve, per stage, what Bristlenose currently uses + what it could use.

The single load-bearing claim of the Pipeline view is: the "Currently using"
column matches what `bristlenose run` would actually dispatch given the
current settings. `build_pipeline_view()` reads settings + (where needed) the
real dispatch helpers and produces a stable `PipelineView` payload.

v2: eligibility + quality resolve at **(provider, model)** grain. Each stage's
`alternatives` is a flat list of `ModelAvailability` — one row per catalogued
model, plus synthesised rows for runtime-detected models (Azure deployment,
user-pulled Ollama models, dispatched-but-uncatalogued models). The v1.5
`llm_summary` dedup is deleted: the five LLM stages no longer share one card,
because v2 surfaces per-stage quality variation (Local is `good` for
structural stages, `marginal` for synthesis). Collapse-when-uniform is a pure
render concern (CLI / React); the payload always carries per-model rows.

For transcription, we reuse `_resolve_backend()` from `s05_transcribe.py` —
do NOT invent a parallel resolver here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.catalogue import (
    _LLM_BACKENDS,
    STAGES,
    BackendOption,
    ModelOption,
    PipelineStageDef,
    QualityLevel,
    QualitySource,
    quality_for,
)
from bristlenose.pipeline_view.eligibility import evaluate_backend
from bristlenose.pipeline_view.host import HostFacts, probe_host

# Map BristlenoseSettings.llm_provider → catalogue BackendOption.id.
_PROVIDER_TO_OPTION_ID = {
    "anthropic": "claude",
    "openai": "openai",
    "azure": "azure",
    "google": "google",
    "local": "local",
}

# Provider display labels, sourced from the catalogue (single source of truth).
# Replaces v1.5's hand-maintained PROVIDER_DISPLAY dict.
_PROVIDER_DISPLAY_BY_OPTION = {b.id: b.display for b in _LLM_BACKENDS}


SCHEMA_VERSION = 4


class ModelAvailability(BaseModel):
    """Resolved availability of one (provider, model) cell. Per-model grain.

    `model_id` is None for stages without model granularity (transcription,
    anonymisation) and for collapsed-provider rows — there the row IS the
    backend. For LLM cells it's the dispatch id the provider's API accepts
    unchanged.

    `display` is composed by the render layer: the model's display when
    `model_id` is set, else the provider's display. `display_key` localises
    qualifier labels (e.g. "Local (Ollama)") — model names stay verbatim.

    `provider_display` / `provider_display_key` carry the provider's label
    (Claude, Local (Ollama), …) on every row, so consumers that render a
    provider heading above expanded model rows (React, desktop) don't have to
    re-derive it from the catalogue. Sourced from `BackendOption.display` —
    catalogue stays the single source of truth.

    `reason_key` / `action_key` are translation keys: *what's wrong* and *what
    to do about it*. Both None when available. `action_key` is None for
    structural failures (hardware, OS version) even when unavailable.

    v1.9 editorial layer (per-model in v2):
    - `quality`: four-glyph rating (excellent/good/marginal/avoid); None when
      the catalogue hasn't rated this cell (render layer shows ? untested).
    - `quality_note`: translation key for the one-line editorial caveat.
    - `quality_source`: provenance (editorial / community / internal_bench /
      published_bench). Ships in JSON for debug/tooling; not rendered to users.
    - `default`: True for the cell BN dispatches out of the box. Singular per
      stage — dispatch is singular.
    - `recommended`: True when BN actively endorses the cell. Plural by design;
      `default ⇒ recommended`. v2 is the first time `recommended ≠ default`
      fires (Opus 4, gpt-4o are recommended but not default).

    `synthesised` is True for rows the render layer composed from settings
    rather than the catalogue (the Azure deployment, user-pulled Ollama models,
    dispatched-but-uncatalogued models). Consumers render these distinctly
    (React: italic) to signal "from your settings, not our catalogue."
    """

    provider_id: str
    model_id: str | None = None
    display: str
    display_key: str | None = None
    provider_display: str
    provider_display_key: str | None = None
    publisher: str | None = None
    available: bool
    reason_key: str | None = None  # translation key, None when available
    action_key: str | None = None  # translation key for the fix, None when structural
    quality: QualityLevel | None = None
    quality_note: str | None = None  # translation key, None when no caveat
    quality_source: QualitySource | None = None
    default: bool = False
    recommended: bool = False
    synthesised: bool = False  # row composed from settings, not the catalogue


class StageSelection(BaseModel):
    """The user-visible row rendered per stage in the Pipeline view."""

    id: str
    name: str
    kind: str
    chosen: str  # human-readable e.g. "MLX Whisper large-v3-turbo"
    chosen_id: str | None = None  # catalogue option id for the chosen backend
    chosen_model_id: str | None = None  # dispatched model id (LLM/Azure); None otherwise
    notes: str
    available: bool  # False when the stage is currently disabled/skipped
    alternatives: list[ModelAvailability] = []


class PipelineView(BaseModel):
    """Top-level payload returned by `bristlenose pipeline --json` and the API.

    Split into:
    - `catalogue`: per-stage rows (one per visible stage), each carrying a flat
      `alternatives` list of per-model `ModelAvailability`.
    - `host`: loopback-only host snapshot (excluded from any support-bundle).

    v2 deleted the v1.5 `llm_summary` field (which bumped schema 3 → 4) — per-stage rendering replaces the
    shared dedup card. `schema_version` defaults to `SCHEMA_VERSION` when built
    fresh in Python but preserves the parsed value on read (round-trip
    fidelity is intentional; Pydantic does not coerce).
    """

    schema_version: int = SCHEMA_VERSION
    catalogue: list[StageSelection]
    host: HostFacts

    @model_validator(mode="before")
    @classmethod
    def _migrate_schema(cls, data: Any) -> Any:
        """Schema version normalisation. The Rule-of-Three trigger fired at
        schema v3 → v4 (third schema transition since v1); this hook exists so future
        non-additive migrations land here cleanly.

        Currently a no-op — v3 and earlier payloads parse via Pydantic's
        `extra="ignore"` default (the deleted `llm_summary` is silently
        dropped; schema 4's new `model_id` fields default). Future migrations
        dispatch on `data.get("schema_version", 1)`.
        """
        if not isinstance(data, dict):
            return data
        return data


def _resolve_transcription(settings: BristlenoseSettings) -> tuple[str, str | None]:
    """Return `(label, option_id)` for the transcription stage's current choice."""
    from bristlenose.stages.s05_transcribe import _resolve_backend
    from bristlenose.utils.hardware import detect_hardware

    try:
        hw = detect_hardware()
        backend = _resolve_backend(settings.whisper_backend, hw)
    except Exception:
        backend = settings.whisper_backend or "auto"

    option_id = backend if backend in {"mlx", "faster-whisper"} else None
    label = {
        "mlx": "MLX Whisper",
        "faster-whisper": "faster-whisper",
    }.get(backend, backend)
    return f"{label} {settings.whisper_model}", option_id


def _resolve_llm_provider(
    settings: BristlenoseSettings,
) -> tuple[str, str | None, str | None]:
    """Format the active LLM provider + model.

    Returns `(label, option_id, model_id)`. `model_id` is the dispatched model:
    `local_model` for Ollama, `azure_deployment` for Azure (None when unset),
    `llm_model` otherwise.
    """
    provider = settings.llm_provider
    option_id = _PROVIDER_TO_OPTION_ID.get(provider)
    display = _PROVIDER_DISPLAY_BY_OPTION.get(option_id or "", provider)
    if provider == "local":
        return f"{display} · {settings.local_model}", option_id, settings.local_model
    if provider == "azure":
        deployment = settings.azure_deployment or "(deployment unset)"
        return (
            f"{display} · {deployment}",
            option_id,
            settings.azure_deployment or None,
        )
    return f"{display} · {settings.llm_model}", option_id, settings.llm_model


def _resolve_anonymisation(settings: BristlenoseSettings) -> tuple[str, bool, str | None]:
    """Anonymisation runs Presidio only when --redact-pii / pii_enabled is set."""
    if settings.pii_enabled:
        return ("Built-in anonymiser (local)", True, "presidio")
    return ("Off (enable with --redact-pii)", False, None)


def _model_row(
    stage_id: str,
    backend: BackendOption,
    model: ModelOption,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> ModelAvailability:
    """Evaluate one catalogued (provider, model) cell."""
    available, reason_key, action_key = evaluate_backend(backend, model, host, settings)
    rating = quality_for(stage_id, backend.id, model.id)
    return ModelAvailability(
        provider_id=backend.id,
        model_id=model.id,
        display=model.display,
        display_key=None,  # model names are verbatim across locales
        provider_display=backend.display,
        provider_display_key=backend.display_key,
        publisher=model.publisher,
        available=available,
        reason_key=None if available else reason_key,
        action_key=None if available else action_key,
        quality=rating.rating if rating else None,
        quality_note=rating.note_key if rating else None,
        quality_source=rating.source if rating else None,
        default=rating.default if rating else False,
        recommended=rating.recommended if rating else False,
    )


def _collapsed_provider_row(
    stage_id: str,
    backend: BackendOption,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> ModelAvailability:
    """The provider rendered as a single row (no model granularity).

    Used for transcription/anonymisation backends and for providers whose
    `models` list is empty (Apple FM, unconfigured Azure). `model_id` is None.
    """
    available, reason_key, action_key = evaluate_backend(backend, None, host, settings)
    rating = quality_for(stage_id, backend.id)  # model_id None → transcription/anon table
    return ModelAvailability(
        provider_id=backend.id,
        model_id=None,
        display=backend.display,
        display_key=backend.display_key,
        provider_display=backend.display,
        provider_display_key=backend.display_key,
        publisher=None,
        available=available,
        reason_key=None if available else reason_key,
        action_key=None if available else action_key,
        quality=rating.rating if rating else None,
        quality_note=rating.note_key if rating else None,
        quality_source=rating.source if rating else None,
        default=rating.default if rating else False,
        recommended=rating.recommended if rating else False,
    )


def _synthesised_row(
    backend: BackendOption,
    model_id: str,
    display: str,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> ModelAvailability:
    """A row for a runtime-detected model BN hasn't catalogued.

    Covers the Azure deployment, user-pulled Ollama models, and the
    dispatched-model-not-in-catalogue case. Eligibility is evaluated against
    the provider's requirements only (the model carries no catalogue
    requirements); quality is always None → renders as ? untested.
    """
    available, reason_key, action_key = evaluate_backend(backend, None, host, settings)
    return ModelAvailability(
        provider_id=backend.id,
        model_id=model_id,
        display=display,
        display_key=None,
        provider_display=backend.display,
        provider_display_key=backend.display_key,
        publisher=None,
        available=available,
        reason_key=None if available else reason_key,
        action_key=None if available else action_key,
        quality=None,
        quality_note=None,
        quality_source=None,
        default=False,
        recommended=False,
        synthesised=True,
    )


def _stage_alternatives(
    stage: PipelineStageDef,
    chosen_id: str | None,
    chosen_model_id: str | None,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> list[ModelAvailability]:
    """Flat per-model availability for one stage, in catalogue declaration order.

    No global sort — providers stay in declaration order, models in declaration
    order, synthesised rows appended after their provider's catalogued models.
    Collapse-when-uniform is a render-layer concern (CLI / React); the payload
    always carries the full per-model list so consumers can filter or collapse.
    """
    rows: list[ModelAvailability] = []
    for backend in stage.viable_backends:
        if backend.models:
            seen: set[str] = set()
            for model in backend.models:
                rows.append(_model_row(stage.id, backend, model, host, settings))
                seen.add(model.id)
            # Local: surface user-pulled Ollama models BN hasn't catalogued.
            if backend.id == "local" and host.ollama_running:
                for pulled in host.ollama_models:
                    if pulled not in seen:
                        rows.append(
                            _synthesised_row(backend, pulled, pulled, host, settings)
                        )
                        seen.add(pulled)
            # Dispatched-model-not-in-catalogue: synthesise the current row so
            # researchers see what's actually running.
            if (
                chosen_id == backend.id
                and chosen_model_id is not None
                and chosen_model_id not in seen
            ):
                rows.append(
                    _synthesised_row(
                        backend, chosen_model_id, chosen_model_id, host, settings
                    )
                )
                seen.add(chosen_model_id)
        elif backend.id == "azure":
            # Azure synthesises a deployment row when fully configured; else it
            # collapses to a single failing row.
            available, _reason, _action = evaluate_backend(backend, None, host, settings)
            if available and settings.azure_deployment:
                rows.append(
                    _synthesised_row(
                        backend,
                        settings.azure_deployment,
                        settings.azure_deployment,
                        host,
                        settings,
                    )
                )
            else:
                rows.append(_collapsed_provider_row(stage.id, backend, host, settings))
        else:
            rows.append(_collapsed_provider_row(stage.id, backend, host, settings))
    return rows


def what_does_this_stage_currently_use(
    stage: PipelineStageDef,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> StageSelection:
    """Map one catalogue stage to its current-dispatch StageSelection."""
    available = True
    chosen_id: str | None = None
    chosen_model_id: str | None = None
    if stage.kind == "transcription":
        chosen, chosen_id = _resolve_transcription(settings)
    elif stage.kind == "llm":
        chosen, chosen_id, chosen_model_id = _resolve_llm_provider(settings)
    elif stage.kind == "anonymisation":
        chosen, available, chosen_id = _resolve_anonymisation(settings)
    elif stage.kind == "apple_fm":
        chosen = "Unknown from CLI"
        available = False
    else:
        chosen = "—"
        available = False

    alternatives = _stage_alternatives(
        stage, chosen_id, chosen_model_id, host, settings
    )

    return StageSelection(
        id=stage.id,
        name=stage.name,
        kind=stage.kind,
        chosen=chosen,
        chosen_id=chosen_id,
        chosen_model_id=chosen_model_id,
        notes=stage.notes,
        available=available,
        alternatives=alternatives,
    )


def build_pipeline_view(
    settings: BristlenoseSettings,
    host: HostFacts | None = None,
) -> PipelineView:
    """Produce the full Pipeline view payload for one set of settings.

    `host` is injectable for tests (synthetic `HostFacts`); falls back to a
    live `probe_host()` when omitted.
    """
    host = host or probe_host(settings)
    catalogue = [what_does_this_stage_currently_use(s, host, settings) for s in STAGES]
    return PipelineView(catalogue=catalogue, host=host)
