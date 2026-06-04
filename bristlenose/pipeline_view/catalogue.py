"""Static catalogue of user-visible pipeline stages.

This is the "what Bristlenose runs" inventory the Pipeline view renders. Only
stages where the chosen backend is interesting to a researcher appear here —
deterministic ingest/audio/parse/merge/render stages are omitted (they don't
participate in the mixture-of-models story).

The Apple Foundation Models entry is a placeholder kind=`apple_fm` that the
renderer fills with `unknown` on the CLI; the desktop app's Pipeline view will
fill it once a Swift-side probe binary ships (deferred, see
`docs/design-cli-improvements.md` §Captured design).

v1.5: each stage gains a `viable_backends` list of `BackendOption` — the full
eligibility space. Each option declares eligibility against HostFacts +
BristlenoseSettings.

v2: the catalogue gains a **provider → model** hierarchy. `BackendOption` is a
provider endpoint that holds `models: list[ModelOption]` (the actual dispatch
unit) plus provider-level `requires`. Quality is re-keyed from `(stage,
provider)` to `(stage, provider, model)`. Pure data; eligibility resolution
lives in `bristlenose/pipeline_view/eligibility.py`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

StageKind = Literal["transcription", "llm", "anonymisation", "apple_fm"]

RequirementKind = Literal[
    "api_key",          # value: provider id ("anthropic"/"openai"/"azure"/"google")
    "setting_present",  # value: BristlenoseSettings field name (truthy check)
    "setting_enabled",  # value: BristlenoseSettings field name (bool True)
    "hardware",         # value: AcceleratorType ("apple_silicon"/"cuda")
    "os",               # value: platform.system() result ("Darwin"/"Linux"/"Windows")
    "min_ram_gb",       # value: float
    "ollama_running",   # value: True (bool sentinel)
    "python_package",   # value: package name (find_spec presence)
    "min_os_version",   # value: float (e.g. 26.0 for Apple FM)
    "apple_fm_status",  # value: required AppleFmStatus string ("available")
]


class Requirement(BaseModel):
    """A single predicate against (HostFacts, BristlenoseSettings).

    `reason_key` (renamed from v1.5's `explain_failure`) is a translation key
    for *what's wrong now* — resolved at render time so non-English researchers
    see localised reasons. Catalogue is the canonical map of key → English
    message; locale files mirror it.

    `action_key` is a translation key for *what to do about it*. None when the
    failure is structural (no user action available — hardware, min_ram_gb,
    apple_fm_status pre-OS-26). Set for fixable failures (api_key,
    setting_present, python_package, ollama_running, etc.). Two namespaces,
    two purposes — the render layer composes whatever surface it needs from
    these keys without prescribing UX shape.
    """

    kind: RequirementKind
    value: str | int | float | bool
    reason_key: str  # translation key, e.g. "pipeline.reasons.no_anthropic_key"
    action_key: str | None = None  # translation key for the fix, None when structural


class ModelOption(BaseModel):
    """One specific model within a provider — the actual dispatch unit.

    `id` is the string the provider's API accepts unchanged
    ("claude-sonnet-4-20250514", "gpt-4o", "llama3.2:3b"). BN treats it as
    opaque — provider-specific id conventions differ; we don't normalise.

    `publisher` names who *made* the model when distinct from the provider that
    serves it (Meta publishes Llama, served via Ollama). Omit when provider ==
    publisher (Claude, gpt-4o, Gemini). Data-only in v4; not rendered yet.

    `requires` adds model-level eligibility on top of the provider's (e.g. a
    paid-tier requirement for Opus, RAM threshold for llama-70b). Empty for
    most cells today.

    `default` flags the provider's out-of-the-box default model. At most one
    model per provider with default=True — dispatch is singular.
    """

    id: str
    display: str
    publisher: str | None = None
    requires: list[Requirement] = []
    default: bool = False


class BackendOption(BaseModel):
    """A provider endpoint — an API namespace. Holds models.

    `id` is the stable identifier. `display` is the English label as it appears
    in the React/CLI surface; product names (Claude, ChatGPT, Azure OpenAI,
    Gemini, MLX Whisper, faster-whisper, Apple FM) stay verbatim across locales.
    Translation-qualifier labels (e.g. "Local (Ollama)" → "Lokal (Ollama)")
    resolve via `display_key` if set.

    `requires` (v2) carries provider-level eligibility (api key, ollama
    running, OS version, python package). Cells under this provider inherit
    these. Absorbs the v1.5 `_llm_requires()` function which is deleted.

    `models` (v2) is the provider's catalogued models. Empty means BN doesn't
    treat this provider as having model-level granularity (anonymisation;
    transcription today; Apple FM until WWDC; Azure until configured at render
    time).
    """

    id: str
    display: str
    display_key: str | None = None  # i18n key for qualifier-localised labels
    requires: list[Requirement] = []  # v2 — provider-level eligibility
    models: list[ModelOption] = []  # v2 — catalogued models


class PipelineStageDef(BaseModel):
    """Static definition of a user-visible stage."""

    id: str  # stable identifier, used by `--stage` filter and React keys
    name: str  # display name, e.g. "Transcription"
    kind: StageKind
    notes: str  # one-line "why this backend" copy
    viable_backends: list[BackendOption] = []


# ── Backend options (catalogue cells) ───────────────────────────────────────

# Shared by all five LLM stages. v2: each provider carries its own `requires`
# (provider-level eligibility) and `models` (the dispatch unit). Quality is
# re-keyed to (stage, provider, model) in `_LLM_QUALITY` below.
_LLM_BACKENDS: list[BackendOption] = [
    BackendOption(
        id="claude",
        display="Claude",
        requires=[
            Requirement(
                kind="api_key",
                value="anthropic",
                reason_key="pipeline.reasons.no_anthropic_key",
                action_key="pipeline.actions.obtain_anthropic_key",
            ),
        ],
        models=[
            ModelOption(id="claude-sonnet-4-20250514", display="Sonnet 4", default=True),
            ModelOption(id="claude-opus-4-20250514", display="Opus 4"),
        ],
    ),
    BackendOption(
        id="openai",
        display="ChatGPT",
        requires=[
            Requirement(
                kind="api_key",
                value="openai",
                reason_key="pipeline.reasons.no_openai_key",
                action_key="pipeline.actions.obtain_openai_key",
            ),
        ],
        models=[ModelOption(id="gpt-4o", display="gpt-4o", default=True)],
    ),
    BackendOption(
        id="azure",
        display="Azure OpenAI",
        requires=[
            Requirement(
                kind="api_key",
                value="azure",
                reason_key="pipeline.reasons.no_azure_key",
                action_key="pipeline.actions.configure_azure",
            ),
            Requirement(
                kind="setting_present",
                value="azure_endpoint",
                reason_key="pipeline.reasons.no_azure_endpoint",
                action_key="pipeline.actions.configure_azure",
            ),
            Requirement(
                kind="setting_present",
                value="azure_deployment",
                reason_key="pipeline.reasons.no_azure_deployment",
                action_key="pipeline.actions.configure_azure",
            ),
        ],
        models=[],  # synthesised at render time from settings.azure_deployment
    ),
    BackendOption(
        id="google",
        display="Gemini",
        requires=[
            Requirement(
                kind="api_key",
                value="google",
                reason_key="pipeline.reasons.no_google_key",
                action_key="pipeline.actions.obtain_google_key",
            ),
        ],
        models=[ModelOption(id="gemini-2.5-pro", display="2.5 Pro", default=True)],
    ),
    BackendOption(
        id="local",
        display="Local (Ollama)",
        display_key="pipeline.backends.local_ollama",
        requires=[
            Requirement(
                kind="ollama_running",
                value=True,
                reason_key="pipeline.reasons.ollama_not_running",
                action_key="pipeline.actions.start_ollama",
            ),
        ],
        models=[
            ModelOption(
                id="llama3.2:3b", display="llama3.2 3B", publisher="Meta", default=True
            ),
        ],
    ),
    BackendOption(
        id="apple_fm",
        display="Apple FM",
        requires=[
            # Always shows ✗/— on the CLI (status="unknown"); desktop app fills
            # it once the Swift-side probe ships. Structural until OS 26 ships,
            # so action_key=None.
            Requirement(
                kind="apple_fm_status",
                value="available",
                reason_key="pipeline.reasons.apple_fm_check_desktop",
                action_key=None,
            ),
        ],
        models=[],  # post-WWDC
    ),
]


# ── Stage catalogue ─────────────────────────────────────────────────────────

STAGES: list[PipelineStageDef] = [
    PipelineStageDef(
        id="transcription",
        name="Transcription",
        kind="transcription",
        notes="Auto-detected from your hardware. Local, private, free.",
        viable_backends=[
            BackendOption(
                id="mlx",
                display="MLX Whisper",
                requires=[
                    Requirement(
                        kind="hardware",
                        value="apple_silicon",
                        reason_key="pipeline.reasons.requires_apple_silicon",
                        action_key=None,  # structural
                    ),
                    Requirement(
                        kind="python_package",
                        value="mlx_whisper",
                        reason_key="pipeline.reasons.mlx_whisper_not_installed",
                        action_key="pipeline.actions.install_mlx_whisper",
                    ),
                ],
                models=[],  # transcription stays flat in v2
            ),
            BackendOption(
                id="faster-whisper",
                display="faster-whisper",
                requires=[
                    Requirement(
                        kind="python_package",
                        value="ctranslate2",
                        reason_key="pipeline.reasons.ctranslate2_not_installed",
                        action_key="pipeline.actions.install_ctranslate2",
                    ),
                ],
                models=[],
            ),
        ],
    ),
    PipelineStageDef(
        id="speaker_identification",
        name="Speaker identification",
        kind="llm",
        notes="Set by your provider choice.",
        viable_backends=_LLM_BACKENDS,
    ),
    PipelineStageDef(
        id="anonymisation",
        name="Anonymisation",
        kind="anonymisation",
        notes="Presidio runs locally when --redact-pii is enabled.",
        viable_backends=[
            BackendOption(
                id="presidio",
                display="Built-in anonymiser",
                display_key="pipeline.backends.builtin_anonymiser",
                requires=[
                    Requirement(
                        kind="python_package",
                        value="presidio_analyzer",
                        reason_key="pipeline.reasons.presidio_not_installed",
                        action_key="pipeline.actions.install_presidio",
                    ),
                    Requirement(
                        kind="python_package",
                        value="en_core_web_lg",
                        reason_key="pipeline.reasons.spacy_model_missing",
                        action_key="pipeline.actions.install_presidio",
                    ),
                    Requirement(
                        kind="setting_enabled",
                        value="pii_enabled",
                        reason_key="pipeline.reasons.pii_disabled",
                        action_key="pipeline.actions.enable_pii_redaction",
                    ),
                ],
                models=[],
            ),
        ],
    ),
    PipelineStageDef(
        id="topic_segmentation",
        name="Topic segmentation",
        kind="llm",
        notes="Set by your provider choice.",
        viable_backends=_LLM_BACKENDS,
    ),
    PipelineStageDef(
        id="quote_extraction",
        name="Quote extraction",
        kind="llm",
        notes="Set by your provider choice. Typically the largest LLM cost.",
        viable_backends=_LLM_BACKENDS,
    ),
    PipelineStageDef(
        id="quote_clustering",
        name="Quote clustering",
        kind="llm",
        notes="Set by your provider choice.",
        viable_backends=_LLM_BACKENDS,
    ),
    PipelineStageDef(
        id="thematic_grouping",
        name="Thematic grouping",
        kind="llm",
        notes="Set by your provider choice.",
        viable_backends=_LLM_BACKENDS,
    ),
    PipelineStageDef(
        id="apple_foundation_models",
        name="Apple Foundation Models",
        kind="apple_fm",
        notes=(
            "Availability not detected from CLI; see the desktop app's "
            "Pipeline view for status. A CLI probe is planned."
        ),
        viable_backends=[],
    ),
]


# ── Requirement aggregation ─────────────────────────────────────────────────


def requirements_for(
    backend: BackendOption,
    model: ModelOption | None = None,
) -> list[Requirement]:
    """Combined provider + model requirements for one (backend, model) cell.

    Pass model=None for cells without model granularity (transcription today,
    anonymisation, apple_fm pre-WWDC, and the provider-collapse path).
    """
    if model is None:
        return list(backend.requires)
    return [*backend.requires, *model.requires]


def all_python_packages() -> set[str]:
    """Every `python_package` requirement value across the catalogue.

    Single source of truth for what `host.installed_packages` must probe.
    Walks both provider-level and model-level requirements. Derived at module
    load; host.py reads this once.
    """
    packages: set[str] = set()
    for stage in STAGES:
        for option in stage.viable_backends:
            reqs = list(option.requires)
            for model in option.models:
                reqs.extend(model.requires)
            for req in reqs:
                if req.kind == "python_package" and isinstance(req.value, str):
                    packages.add(req.value)
    return packages


def find_stage(stage_id: str) -> PipelineStageDef | None:
    """Look up a stage definition by id; returns None if no match."""
    for stage in STAGES:
        if stage.id == stage_id:
            return stage
    return None


# ── v1.9 quality ratings (editorial layer over v1.5 eligibility) ────────────


QualityLevel = Literal["excellent", "good", "marginal", "avoid"]
QualitySource = Literal["internal_bench", "published_bench", "community", "editorial"]


# Translation key referenced by the render layer for cells without a
# catalogue rating (apple_fm today; any future unrated cell). Module-level
# constant so it's grep-discoverable and importable — not just a docstring.
UNTESTED_NOTE_KEY = "pipeline.quality.untested"


class QualityRating(BaseModel):
    """Per-(stage, provider, model) editorial judgement of fitness for purpose.

    Quality and "is this the default" are intentionally orthogonal axes:
    quality measures fitness; `default` flags Bristlenose's out-of-the-box
    pick. The default is usually `excellent` or `good`, never `marginal`
    or `avoid` — but BN may default to a `good` cell over an `excellent`
    one when the extra quality isn't worth a cost / speed / locality
    trade-off. Researchers who go off-piste are free to; the default flag
    is the breadcrumb showing where BN's recommendation would have landed.

    `rating` is a four-glyph closed enum:
        "excellent" (●) — top of measured quality for this stage
        "good"      (○) — production-usable; no known issues. May be the
                         default over an `excellent` peer when the
                         trade-off is worth it
        "marginal"  (⚠) — borderline. The minimum that will sustain the
                         work — the 65th parallel where crops still grow
                         but harvests are thin, the Sahel where rain still
                         falls but you plan around drought. Acceptable if
                         you have no alternative, are prioritising speed /
                         cost over quality, or are testing other parts of
                         the pipeline and want to spend the fewest
                         resources here
        "avoid"     (✗) — known-bad for this stage; use only if no
                         alternative

    `default` flags the cell Bristlenose ships as default. At most one cell
    per (stage, provider-family) should be flagged. Used by the render
    layer to mark "this is what runs if you don't change anything."
    Necessarily singular — dispatch is singular.

    `recommended` flags a cell BN actively endorses as a production choice.
    **Independent of quality**: an `excellent` cell isn't automatically
    recommended if BN thinks the cost / speed / locality trade-off favours
    a peer; a `good` cell can be recommended over an `excellent` peer when
    the trade-off is worth it. **Plural by design** — multiple cells may
    be recommended per stage. **Invariant: `default ⇒ recommended`** — BN
    cannot default to a cell it doesn't actively endorse. v2 is the first
    time `recommended ≠ default` fires (Opus 4, gpt-4o are recommended but
    not default).

    `note_key` is a translation key for the one-line editorial caveat
    (e.g. "pipeline.quality.local_quote_extraction_miss_rate"). Locale
    files mirror it; English is the source.

    `source` documents where the rating came from:
        "internal_bench"  — measured on a Bristlenose trial run
        "published_bench" — third-party benchmark (cite in note)
        "community"       — aggregated researcher feedback
        "editorial"       — Bristlenose's subjective opinion, no measurement.
                            Shipped as a starting point; refines as data
                            arrives. Honest about being unmeasured
    """

    rating: QualityLevel
    note_key: str | None = None
    source: QualitySource
    default: bool = False
    recommended: bool = False


# Shared LLM cells, keyed (stage, provider, model). Same (provider, model)
# keyset across all five LLM stages — `test_quality.py` enforces parity.
# Azure + Apple FM omitted by design: Azure's model is synthesised at render
# time from settings.azure_deployment (no catalogue model to rate); Apple FM
# stays untested (renders as ?) until the probe ships. Editorial judgements
# only; refine from cohort signal as it arrives.
#
# Structural stages (speaker_identification, topic_segmentation) rate Local as
# `good`; synthesis stages (quote_extraction, quote_clustering,
# thematic_grouping) rate it `marginal` — the per-stage variation v2 exists to
# surface. claude/openai/google ratings are uniform across all five stages.
_LLM_QUALITY: dict[tuple[str, str, str], QualityRating] = {
    # ── speaker_identification — structural; most LLMs handle it well ──
    ("speaker_identification", "claude", "claude-sonnet-4-20250514"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("speaker_identification", "claude", "claude-opus-4-20250514"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("speaker_identification", "openai", "gpt-4o"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("speaker_identification", "google", "gemini-2.5-pro"): QualityRating(
        rating="good", source="editorial"
    ),
    ("speaker_identification", "local", "llama3.2:3b"): QualityRating(
        rating="good",
        note_key="pipeline.quality.local_speaker_id_acceptable",
        source="community",
    ),
    # ── topic_segmentation — structural; similar profile to speaker_id ──
    ("topic_segmentation", "claude", "claude-sonnet-4-20250514"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("topic_segmentation", "claude", "claude-opus-4-20250514"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("topic_segmentation", "openai", "gpt-4o"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("topic_segmentation", "google", "gemini-2.5-pro"): QualityRating(
        rating="good", source="editorial"
    ),
    ("topic_segmentation", "local", "llama3.2:3b"): QualityRating(
        rating="good",
        note_key="pipeline.quality.local_topic_segmentation_acceptable",
        source="community",
    ),
    # ── quote_extraction — high-stakes; longest prompts, smallest-model risk ──
    ("quote_extraction", "claude", "claude-sonnet-4-20250514"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("quote_extraction", "claude", "claude-opus-4-20250514"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("quote_extraction", "openai", "gpt-4o"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("quote_extraction", "google", "gemini-2.5-pro"): QualityRating(
        rating="good", source="editorial"
    ),
    ("quote_extraction", "local", "llama3.2:3b"): QualityRating(
        rating="marginal",
        note_key="pipeline.quality.local_quote_extraction_miss_rate",
        source="community",
    ),
    # ── quote_clustering — high-stakes; nuance matters ──
    ("quote_clustering", "claude", "claude-sonnet-4-20250514"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("quote_clustering", "claude", "claude-opus-4-20250514"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("quote_clustering", "openai", "gpt-4o"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("quote_clustering", "google", "gemini-2.5-pro"): QualityRating(
        rating="good", source="editorial"
    ),
    ("quote_clustering", "local", "llama3.2:3b"): QualityRating(
        rating="marginal",
        note_key="pipeline.quality.local_quote_clustering_drift",
        source="community",
    ),
    # ── thematic_grouping — high-stakes synthesis; small-model drift highest ──
    ("thematic_grouping", "claude", "claude-sonnet-4-20250514"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("thematic_grouping", "claude", "claude-opus-4-20250514"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("thematic_grouping", "openai", "gpt-4o"): QualityRating(
        rating="excellent", source="editorial", recommended=True
    ),
    ("thematic_grouping", "google", "gemini-2.5-pro"): QualityRating(
        rating="good", source="editorial"
    ),
    ("thematic_grouping", "local", "llama3.2:3b"): QualityRating(
        rating="marginal",
        note_key="pipeline.quality.local_thematic_grouping_drift",
        source="community",
    ),
}


# Transcription cells deliberately omit `default=True`: the host-aware
# resolver in s05_transcribe._resolve_backend() already picks based on
# hardware (MLX on Apple Silicon, faster-whisper elsewhere). A static
# catalogue flag would conflict with that dynamic choice. Keyed (stage,
# provider) — transcription has no model granularity in v2.
_TRANSCRIPTION_QUALITY: dict[tuple[str, str], QualityRating] = {
    ("transcription", "mlx"): QualityRating(
        rating="excellent",
        note_key="pipeline.quality.mlx_whisper_apple_silicon_optimal",
        source="editorial",
    ),
    ("transcription", "faster-whisper"): QualityRating(
        rating="good",
        note_key="pipeline.quality.faster_whisper_cpu_baseline",
        source="editorial",
    ),
}


def quality_for(
    stage_id: str,
    provider_id: str,
    model_id: str | None = None,
) -> QualityRating | None:
    """Editorial quality rating for a (stage, provider, model) cell.

    `model_id` is required for LLM stages (model granularity); None falls
    through to the provider-level transcription/anonymisation table. Returns
    None when unrated — render layer shows ? "untested". Catalogue stays
    explicit about what's measured vs guessed; absence is information.
    """
    if model_id is not None:
        rating = _LLM_QUALITY.get((stage_id, provider_id, model_id))
        if rating is not None:
            return rating
    return _TRANSCRIPTION_QUALITY.get((stage_id, provider_id))
