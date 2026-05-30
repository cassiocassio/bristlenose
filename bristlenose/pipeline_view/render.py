"""Resolve, per stage, what Bristlenose currently uses + what it could use.

The single load-bearing claim of the Pipeline view is: the "Currently using"
column matches what `bristlenose run` would actually dispatch given the
current settings. `build_pipeline_view()` reads settings + (where needed) the
real dispatch helpers and produces a stable `PipelineView` payload.

v1.5: each stage gains `alternatives: list[BackendAvailability]`. The five
LLM stages share host-wide eligibility — rendered once as `llm_summary` at
the top of the payload, with the per-stage `alternatives` list empty. The
transcription and anonymisation stages render their own per-stage lists.

For transcription, we reuse `_resolve_backend()` from `s05_transcribe.py` —
do NOT invent a parallel resolver here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings
from bristlenose.pipeline_view.catalogue import (
    STAGES,
    PipelineStageDef,
    QualityLevel,
    QualitySource,
    quality_for,
)
from bristlenose.pipeline_view.eligibility import evaluate_backend
from bristlenose.pipeline_view.host import HostFacts, probe_host

ProviderId = Literal["anthropic", "openai", "azure", "google", "local"]

PROVIDER_DISPLAY = {
    "anthropic": "Claude",
    "openai": "ChatGPT",
    "azure": "Azure OpenAI",
    "google": "Gemini",
    "local": "Local (Ollama)",
}

# Map BristlenoseSettings.llm_provider → catalogue BackendOption.id.
_PROVIDER_TO_OPTION_ID = {
    "anthropic": "claude",
    "openai": "openai",
    "azure": "azure",
    "google": "google",
    "local": "local",
}


SCHEMA_VERSION = 3


# Sort weight for quality ratings. Untested cells (None at the catalogue
# layer) rank with `marginal` — render layer defaults the glyph the same
# way, so sort and glyph stay in agreement.
_QUALITY_SORT_WEIGHT: dict[QualityLevel | None, int] = {
    "excellent": 0,
    "good": 1,
    "marginal": 2,
    None: 2,
    "avoid": 3,
}


class BackendAvailability(BaseModel):
    """Resolved availability of one `BackendOption` against the host.

    `display` is the English label as authored in the catalogue; the React
    layer translates qualifier labels via `display_key` when set. `reason`
    is a translation key (None when available). Render layers look up the
    matching locale string.

    v1.9 additions — editorial quality layered over mechanical availability:
    - `quality`: four-glyph rating (excellent/good/marginal/avoid); None when
      the catalogue hasn't rated this cell yet (render layer shows ⚠ untested).
    - `quality_note`: translation key for the one-line editorial caveat.
    - `quality_source`: provenance of the rating (internal_bench / community /
      editorial / etc.). Ships in JSON for debug/tooling; not rendered to users.
    - `default`: True when this cell is Bristlenose's out-of-the-box pick for
      the (stage, provider-family). Orthogonal to quality — BN may default to
      a `good` cell over an `excellent` peer when the trade-off is worth it.
      Necessarily singular per stage (dispatch is singular).
    - `recommended`: True when BN actively endorses this cell as a production
      choice. Independent of `quality` AND of `default` — `default ⇒ recommended`
      (BN can't default to a cell it doesn't endorse) but `recommended` is
      plural by design (multiple cells per stage may be recommended). In the
      v1.9 initial catalogue, `recommended=True` coincides with `default=True`;
      widens as cohort signal arrives.
    """

    id: str
    display: str
    display_key: str | None = None
    available: bool
    reason: str | None = None  # translation key, None when available
    quality: QualityLevel | None = None
    quality_note: str | None = None  # translation key, None when no caveat
    quality_source: QualitySource | None = None
    default: bool = False
    recommended: bool = False


class StageSelection(BaseModel):
    """The user-visible row rendered per stage in the Pipeline view."""

    id: str
    name: str
    kind: str
    chosen: str  # human-readable e.g. "MLX Whisper large-v3-turbo"
    chosen_id: str | None = None  # catalogue option id for the chosen backend
    notes: str
    available: bool  # False when the stage is currently disabled/skipped
    alternatives: list[BackendAvailability] = []


class PipelineView(BaseModel):
    """Top-level payload returned by `bristlenose pipeline --json` and the API.

    Split into:
    - `catalogue`: per-stage rows (one per visible stage).
    - `host`: loopback-only host snapshot (excluded from any support-bundle).
    - `llm_summary`: host-wide LLM-backend availability, shared by the five
      LLM stages. v1.5 dedup: per-stage LLM rows render `alternatives=[]`;
      the React/CLI layer reads the summary instead.

    `schema_version` defaults to `SCHEMA_VERSION` (the current shipping
    version) when a view is built fresh in Python, but preserves the
    parsed value when read from JSON — round-trip fidelity is intentional,
    Pydantic does not coerce. Downstream code can branch on the field.
    No `model_validator` bumps the version on parse; that's deferred until
    there's a third schema transition (Rule of Three).
    """

    schema_version: int = SCHEMA_VERSION
    catalogue: list[StageSelection]
    llm_summary: list[BackendAvailability] = []
    host: HostFacts


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


def _resolve_llm_provider(settings: BristlenoseSettings) -> tuple[str, str | None]:
    """Format the active LLM provider + model. Returns `(label, option_id)`."""
    provider = settings.llm_provider
    display = PROVIDER_DISPLAY.get(provider, provider)
    option_id = _PROVIDER_TO_OPTION_ID.get(provider)
    if provider == "local":
        return f"{display} · {settings.local_model}", option_id
    if provider == "azure":
        deployment = settings.azure_deployment or "(deployment unset)"
        return f"{display} · {deployment}", option_id
    return f"{display} · {settings.llm_model}", option_id


def _resolve_anonymisation(settings: BristlenoseSettings) -> tuple[str, bool, str | None]:
    """Anonymisation runs Presidio only when --redact-pii / pii_enabled is set."""
    if settings.pii_enabled:
        return ("Built-in anonymiser (local)", True, "presidio")
    return ("Off (enable with --redact-pii)", False, None)


def _stage_alternatives(
    stage: PipelineStageDef,
    chosen_id: str | None,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> list[BackendAvailability]:
    """Evaluate every `BackendOption` for one stage; sort available-first.

    Deterministic ordering: chosen-id first (if present and available),
    then remaining available, then unavailable — each group preserves
    catalogue declaration order.
    """
    rows: list[BackendAvailability] = []
    for option in stage.viable_backends:
        available, reason = evaluate_backend(stage.id, option, host, settings)
        rating = quality_for(stage.id, option.id)
        rows.append(
            BackendAvailability(
                id=option.id,
                display=option.display,
                display_key=option.display_key,
                available=available,
                reason=None if available else reason,
                quality=rating.rating if rating else None,
                quality_note=rating.note_key if rating else None,
                quality_source=rating.source if rating else None,
                default=rating.default if rating else False,
                recommended=rating.recommended if rating else False,
            )
        )

    def sort_key(row: BackendAvailability) -> tuple[int, int, int]:
        is_chosen = 0 if (chosen_id is not None and row.id == chosen_id) else 1
        is_available = 0 if row.available else 1
        # Quality is a tiebreaker WITHIN the available group only. For
        # unavailable rows, all three sort fields are constant across the
        # group (is_available=1; is_chosen always 1 — chosen_id is only set
        # for an available row; quality_weight=0 below), so Python's stable
        # sort preserves catalogue declaration order.
        quality_weight = _QUALITY_SORT_WEIGHT[row.quality] if row.available else 0
        return (is_available, is_chosen, quality_weight)

    return sorted(rows, key=sort_key)


def what_does_this_stage_currently_use(
    stage: PipelineStageDef,
    host: HostFacts,
    settings: BristlenoseSettings,
) -> StageSelection:
    """Map one catalogue stage to its current-dispatch StageSelection."""
    available = True
    chosen_id: str | None = None
    if stage.kind == "transcription":
        chosen, chosen_id = _resolve_transcription(settings)
    elif stage.kind == "llm":
        chosen, chosen_id = _resolve_llm_provider(settings)
    elif stage.kind == "anonymisation":
        chosen, available, chosen_id = _resolve_anonymisation(settings)
    elif stage.kind == "apple_fm":
        chosen = "Unknown from CLI"
        available = False
    else:
        chosen = "—"
        available = False

    # Dedup: LLM stages share host-wide eligibility — surfaced once in
    # `llm_summary`, not per-stage. Transcription and anonymisation differ
    # per host (hardware/setting) so they keep their own per-stage list.
    if stage.kind == "llm":
        alternatives: list[BackendAvailability] = []
    else:
        alternatives = _stage_alternatives(stage, chosen_id, host, settings)

    return StageSelection(
        id=stage.id,
        name=stage.name,
        kind=stage.kind,
        chosen=chosen,
        chosen_id=chosen_id,
        notes=stage.notes,
        available=available,
        alternatives=alternatives,
    )


def _build_llm_summary(
    host: HostFacts,
    settings: BristlenoseSettings,
    chosen_id: str | None,
) -> list[BackendAvailability]:
    """Host-wide LLM-backend availability shared across the five LLM stages."""
    template = next((s for s in STAGES if s.id == "speaker_identification"), None)
    if template is None:
        return []
    return _stage_alternatives(template, chosen_id, host, settings)


def build_pipeline_view(settings: BristlenoseSettings) -> PipelineView:
    """Produce the full Pipeline view payload for one set of settings."""
    host = probe_host(settings)
    catalogue = [what_does_this_stage_currently_use(s, host, settings) for s in STAGES]
    _, chosen_llm_id = _resolve_llm_provider(settings)
    llm_summary = _build_llm_summary(host, settings, chosen_llm_id)
    return PipelineView(
        catalogue=catalogue,
        llm_summary=llm_summary,
        host=host,
    )
