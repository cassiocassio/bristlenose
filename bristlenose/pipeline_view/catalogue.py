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
eligibility space. Each option declares `requires: list[Requirement]` against
HostFacts + BristlenoseSettings. Pure data; eligibility resolution lives in
`bristlenose/pipeline_view/eligibility.py`.
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

    `explain_failure` is a translation key (not literal text), resolved at
    render time so non-English researchers see localised reasons. Catalogue
    is the canonical map of key → English message; locale files mirror it.
    """

    kind: RequirementKind
    value: str | int | float | bool
    explain_failure: str  # translation key, e.g. "pipeline.reasons.no_anthropic_key"


class BackendOption(BaseModel):
    """A backend that *could* run a stage. Eligible iff all `requires` pass.

    `id` is the stable identifier. `display` is the English label as it
    appears in the React/CLI surface; product names (Claude, ChatGPT, Azure
    OpenAI, Gemini, MLX Whisper, faster-whisper, Apple FM) stay verbatim
    across locales. Translation-qualifier labels (e.g. "Local (Ollama)" →
    "Lokal (Ollama)") resolve via `display_key` if set; the catalogue ships
    English and React/CLI render layers apply the key when present.
    """

    id: str
    display: str
    display_key: str | None = None  # i18n key for qualifier-localised labels


class PipelineStageDef(BaseModel):
    """Static definition of a user-visible stage."""

    id: str  # stable identifier, used by `--stage` filter and React keys
    name: str  # display name, e.g. "Transcription"
    kind: StageKind
    notes: str  # one-line "why this backend" copy
    viable_backends: list[BackendOption] = []


# ── Backend options (catalogue cells) ───────────────────────────────────────

# Shared by all five LLM stages. Render-time dedup is in `render.py`:
# LLM stages render a single host-wide summary card and no per-stage list.
_LLM_BACKENDS: list[BackendOption] = [
    BackendOption(
        id="claude",
        display="Claude",
    ),
    BackendOption(
        id="openai",
        display="ChatGPT",
    ),
    BackendOption(
        id="azure",
        display="Azure OpenAI",
    ),
    BackendOption(
        id="google",
        display="Gemini",
    ),
    BackendOption(
        id="local",
        display="Local (Ollama)",
        display_key="pipeline.backends.local_ollama",
    ),
    BackendOption(
        id="apple_fm",
        display="Apple FM",
    ),
]


def _llm_requires(option_id: str) -> list[Requirement]:
    """Return the requirement list a given LLM option imposes."""
    if option_id == "claude":
        return [
            Requirement(
                kind="api_key",
                value="anthropic",
                explain_failure="pipeline.reasons.no_anthropic_key",
            ),
        ]
    if option_id == "openai":
        return [
            Requirement(
                kind="api_key",
                value="openai",
                explain_failure="pipeline.reasons.no_openai_key",
            ),
        ]
    if option_id == "azure":
        return [
            Requirement(
                kind="api_key",
                value="azure",
                explain_failure="pipeline.reasons.no_azure_key",
            ),
            Requirement(
                kind="setting_present",
                value="azure_endpoint",
                explain_failure="pipeline.reasons.no_azure_endpoint",
            ),
            Requirement(
                kind="setting_present",
                value="azure_deployment",
                explain_failure="pipeline.reasons.no_azure_deployment",
            ),
        ]
    if option_id == "google":
        return [
            Requirement(
                kind="api_key",
                value="google",
                explain_failure="pipeline.reasons.no_google_key",
            ),
        ]
    if option_id == "local":
        return [
            Requirement(
                kind="ollama_running",
                value=True,
                explain_failure="pipeline.reasons.ollama_not_running",
            ),
        ]
    if option_id == "apple_fm":
        # Always shows ✗ on the CLI (status="unknown"); desktop app fills
        # it once the Swift-side probe ships. Single shared reason key.
        return [
            Requirement(
                kind="apple_fm_status",
                value="available",
                explain_failure="pipeline.reasons.apple_fm_check_desktop",
            ),
        ]
    return []


# ── Stage catalogue ─────────────────────────────────────────────────────────

STAGES: list[PipelineStageDef] = [
    PipelineStageDef(
        id="transcription",
        name="Transcription",
        kind="transcription",
        notes="Auto-detected from your hardware. Local, private, free.",
        viable_backends=[
            BackendOption(id="mlx", display="MLX Whisper"),
            BackendOption(id="faster-whisper", display="faster-whisper"),
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

# Per-option requirement lookup, keyed by (stage_id, option_id). The shared
# LLM backends share requirements (api_key, ollama_running, etc.) — but the
# transcription/anonymisation options each have their own requirements wired
# below. Eligibility.py consumes this view; catalogue.py is pure data.

_TRANSCRIPTION_REQUIRES: dict[str, list[Requirement]] = {
    "mlx": [
        Requirement(
            kind="hardware",
            value="apple_silicon",
            explain_failure="pipeline.reasons.requires_apple_silicon",
        ),
        Requirement(
            kind="python_package",
            value="mlx_whisper",
            explain_failure="pipeline.reasons.mlx_whisper_not_installed",
        ),
    ],
    "faster-whisper": [
        Requirement(
            kind="python_package",
            value="ctranslate2",
            explain_failure="pipeline.reasons.ctranslate2_not_installed",
        ),
    ],
}

_ANONYMISATION_REQUIRES: dict[str, list[Requirement]] = {
    "presidio": [
        Requirement(
            kind="python_package",
            value="presidio_analyzer",
            explain_failure="pipeline.reasons.presidio_not_installed",
        ),
        Requirement(
            kind="python_package",
            value="en_core_web_lg",
            explain_failure="pipeline.reasons.spacy_model_missing",
        ),
        Requirement(
            kind="setting_enabled",
            value="pii_enabled",
            explain_failure="pipeline.reasons.pii_disabled",
        ),
    ],
}


def requirements_for(stage_id: str, option_id: str) -> list[Requirement]:
    """Return the requirement list for a (stage, option) cell.

    LLM stages share `_llm_requires`. Transcription + anonymisation use their
    own tables. Stages without an option (`apple_foundation_models`) return [].
    """
    if option_id in {"claude", "openai", "azure", "google", "local", "apple_fm"}:
        return _llm_requires(option_id)
    if stage_id == "transcription":
        return _TRANSCRIPTION_REQUIRES.get(option_id, [])
    if stage_id == "anonymisation":
        return _ANONYMISATION_REQUIRES.get(option_id, [])
    return []


def all_python_packages() -> set[str]:
    """Every `python_package` requirement value across the catalogue.

    Single source of truth for what `host.installed_packages` must probe.
    Derived at module load; host.py reads this once.
    """
    packages: set[str] = set()
    for stage in STAGES:
        for option in stage.viable_backends:
            for req in requirements_for(stage.id, option.id):
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
    """Per-(stage, option) editorial judgement of fitness for purpose.

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
    cannot default to a cell it doesn't actively endorse. In the v1.9
    initial catalogue, the only `recommended=True` cells coincide with
    `default=True` (we have no evidence yet for alternative endorsements);
    as cohort data arrives — e.g. ChatGPT comparison, Local-for-structural
    confidence — we widen the recommended set one cell at a time without
    touching the default.

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


# Shared LLM cells. Same option-id set across all five LLM stages —
# `test_quality.py` enforces parity (mirrors v1.5's _LLM_BACKENDS invariant).
# Apple FM omitted by design: stays untested (renders as ⚠) until the probe
# ships. Editorial judgements only; refine from cohort signal as it arrives.
_LLM_QUALITY: dict[tuple[str, str], QualityRating] = {
    # Claude is BN's default LLM provider (matches BristlenoseSettings.
    # llm_provider="anthropic"); flagged default=True across LLM stages so
    # the render layer can mark the BN-recommended pick. All 25 LLM cells
    # currently `source="editorial"` — these are BN's subjective opinion,
    # honest about being unmeasured until benchmark data lands.
    # speaker_identification — structural task; most LLMs handle it well.
    ("speaker_identification", "claude"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("speaker_identification", "openai"): QualityRating(rating="excellent", source="editorial"),
    ("speaker_identification", "google"): QualityRating(rating="good", source="editorial"),
    ("speaker_identification", "azure"): QualityRating(rating="good", source="editorial"),
    ("speaker_identification", "local"): QualityRating(
        rating="good",
        note_key="pipeline.quality.local_speaker_id_acceptable",
        source="community",
    ),
    # topic_segmentation — structural; similar profile to speaker_id.
    ("topic_segmentation", "claude"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("topic_segmentation", "openai"): QualityRating(rating="excellent", source="editorial"),
    ("topic_segmentation", "google"): QualityRating(rating="good", source="editorial"),
    ("topic_segmentation", "azure"): QualityRating(rating="good", source="editorial"),
    ("topic_segmentation", "local"): QualityRating(
        rating="good",
        note_key="pipeline.quality.local_topic_segmentation_acceptable",
        source="community",
    ),
    # quote_extraction — high-stakes; longest prompts, smallest-model risk.
    ("quote_extraction", "claude"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("quote_extraction", "openai"): QualityRating(rating="excellent", source="editorial"),
    ("quote_extraction", "google"): QualityRating(rating="good", source="editorial"),
    ("quote_extraction", "azure"): QualityRating(rating="good", source="editorial"),
    ("quote_extraction", "local"): QualityRating(
        rating="marginal",
        note_key="pipeline.quality.local_quote_extraction_miss_rate",
        source="community",
    ),
    # quote_clustering — high-stakes; nuance matters.
    ("quote_clustering", "claude"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("quote_clustering", "openai"): QualityRating(rating="excellent", source="editorial"),
    ("quote_clustering", "google"): QualityRating(rating="good", source="editorial"),
    ("quote_clustering", "azure"): QualityRating(rating="good", source="editorial"),
    ("quote_clustering", "local"): QualityRating(
        rating="marginal",
        note_key="pipeline.quality.local_quote_clustering_drift",
        source="community",
    ),
    # thematic_grouping — high-stakes synthesis; small-model drift highest here.
    ("thematic_grouping", "claude"): QualityRating(
        rating="excellent", source="editorial", default=True, recommended=True
    ),
    ("thematic_grouping", "openai"): QualityRating(rating="excellent", source="editorial"),
    ("thematic_grouping", "google"): QualityRating(rating="good", source="editorial"),
    ("thematic_grouping", "azure"): QualityRating(rating="good", source="editorial"),
    ("thematic_grouping", "local"): QualityRating(
        rating="marginal",
        note_key="pipeline.quality.local_thematic_grouping_drift",
        source="community",
    ),
}


# Transcription cells deliberately omit `default=True`: the host-aware
# resolver in s05_transcribe._resolve_backend() already picks based on
# hardware (MLX on Apple Silicon, faster-whisper elsewhere). A static
# catalogue flag would conflict with that dynamic choice.
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


def quality_for(stage_id: str, option_id: str) -> QualityRating | None:
    """Return the editorial quality rating for a (stage, option) cell.

    None when the cell is not yet rated — render layer defaults this to
    ⚠ "untested" (pipeline.quality.untested). Catalogue stays explicit
    about what's measured vs guessed; absence is information.
    """
    llm = _LLM_QUALITY.get((stage_id, option_id))
    if llm is not None:
        return llm
    return _TRANSCRIPTION_QUALITY.get((stage_id, option_id))
