"""Quality-rating invariants — behavioural, not snapshot.

v2: quality resolves at (stage, provider, model) grain for LLM stages and
(stage, provider) for transcription. Every rated cell parses as a valid
`QualityRating`, every `note_key` is a translation key, every `source` is in
the closed enum, and the LLM stages share an identical (provider, model) set.
"""

from __future__ import annotations

import pytest

from bristlenose.pipeline_view.catalogue import (
    _LLM_QUALITY,
    _TRANSCRIPTION_QUALITY,
    STAGES,
    QualityRating,
    quality_for,
)

_VALID_RATINGS = {"excellent", "good", "marginal", "avoid"}
_VALID_SOURCES = {"internal_bench", "published_bench", "community", "editorial"}

_ALL_QUALITY = list(_LLM_QUALITY.items()) + list(_TRANSCRIPTION_QUALITY.items())


def test_quality_for_unknown_cell_returns_none() -> None:
    assert quality_for("not_a_stage", "claude", "claude-sonnet-4-20250514") is None
    assert quality_for("quote_extraction", "not_a_backend", "x") is None


def test_quality_for_known_cell_returns_rating() -> None:
    """Structural: a known (stage, provider, model) cell returns a rating.
    Editorial values are covered by the parametrised enum sweep below — don't
    pin them here, they're catalogue editorial data that will shift."""
    r = quality_for("quote_extraction", "claude", "claude-sonnet-4-20250514")
    assert isinstance(r, QualityRating)


def test_quality_for_transcription_cells_resolve() -> None:
    """Structural: transcription cells resolve via the provider-grain table."""
    mlx = quality_for("transcription", "mlx")
    fw = quality_for("transcription", "faster-whisper")
    assert isinstance(mlx, QualityRating)
    assert isinstance(fw, QualityRating)


@pytest.mark.parametrize("cell", _ALL_QUALITY)
def test_every_rating_uses_closed_enums(
    cell: tuple[tuple[str, ...], QualityRating],
) -> None:
    key, r = cell
    assert r.rating in _VALID_RATINGS, f"{key} bad rating {r.rating!r}"
    assert r.source in _VALID_SOURCES, f"{key} bad source {r.source!r}"


@pytest.mark.parametrize("cell", _ALL_QUALITY)
def test_every_note_key_is_a_translation_key(
    cell: tuple[tuple[str, ...], QualityRating],
) -> None:
    """`note_key` is either None or starts with `pipeline.quality.`."""
    key, r = cell
    if r.note_key is not None:
        assert r.note_key.startswith("pipeline.quality."), (
            f"{key} note_key={r.note_key!r} is not a pipeline.quality.* key"
        )


def test_llm_quality_shares_identical_model_set_across_stages() -> None:
    """Drift catcher: if someone seeds quality for one LLM stage but forgets
    another, this fails loudly rather than letting the render layer silently
    default half a column to "untested".

    Identity is the (provider, model) pair — the v2 grain."""
    by_stage: dict[str, set[tuple[str, str]]] = {}
    for stage_id, provider_id, model_id in _LLM_QUALITY:
        by_stage.setdefault(stage_id, set()).add((provider_id, model_id))
    llm_stage_ids = {s.id for s in STAGES if s.kind == "llm"}
    assert set(by_stage) == llm_stage_ids, (
        f"_LLM_QUALITY stage coverage {set(by_stage)} != LLM stages {llm_stage_ids}"
    )
    sets = list(by_stage.values())
    first = sets[0]
    for s in sets[1:]:
        assert s == first, f"(provider, model) drift across LLM stages: {sets}"


def test_apple_fm_cells_are_unrated() -> None:
    """Apple FM stays untested until a probe ships — render layer shows ? untested."""
    for stage in STAGES:
        if stage.kind != "llm":
            continue
        assert quality_for(stage.id, "apple_fm") is None, (
            f"{stage.id}/apple_fm should be unrated until the probe ships"
        )


def test_default_flag_at_most_once_per_llm_stage() -> None:
    """`default=True` marks BN's out-of-the-box pick. At most one per LLM
    stage — multiple defaults would defeat the purpose."""
    by_stage: dict[str, list[tuple[str, str]]] = {}
    for (stage_id, provider_id, model_id), rating in _LLM_QUALITY.items():
        if rating.default:
            by_stage.setdefault(stage_id, []).append((provider_id, model_id))
    for stage_id, cells in by_stage.items():
        assert len(cells) == 1, (
            f"{stage_id} has {len(cells)} default-flagged cells: {cells}; "
            f"expected exactly one"
        )


def test_default_flag_never_on_marginal_or_avoid() -> None:
    """BN's default pick must be `good` or `excellent` — never marginal/avoid."""
    for cell_key, rating in _LLM_QUALITY.items():
        if rating.default:
            assert rating.rating in ("excellent", "good"), (
                f"{cell_key} is default-flagged but rated {rating.rating!r}; "
                f"BN must not default to marginal/avoid"
            )


def test_default_implies_recommended() -> None:
    """Invariant: `default ⇒ recommended`. BN cannot default to a cell it does
    not actively endorse. `recommended` is plural (multiple cells per stage may
    be recommended); `default` is singular. The implication is one-way."""
    for cell_key, rating in {**_LLM_QUALITY, **_TRANSCRIPTION_QUALITY}.items():
        if rating.default:
            assert rating.recommended, (
                f"{cell_key} is default-flagged but not recommended; "
                f"every default cell must be recommended (default ⇒ recommended)"
            )


def test_recommended_never_on_marginal_or_avoid() -> None:
    """BN's active endorsement must be `good` or `excellent` — never marginal
    or avoid. Keeps the recommended set trustworthy as it widens with cohort
    signal."""
    for cell_key, rating in {**_LLM_QUALITY, **_TRANSCRIPTION_QUALITY}.items():
        if rating.recommended:
            assert rating.rating in ("excellent", "good"), (
                f"{cell_key} is recommended but rated {rating.rating!r}; "
                f"BN must not actively endorse marginal/avoid cells"
            )


def test_unrated_available_backend_is_a_distinct_state() -> None:
    """An unrated cell (quality=None) is a third state the render layer must
    distinguish from quality="marginal". Pin the invariant at the data layer:
    a ModelAvailability can carry quality=None alongside any availability."""
    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline_view.catalogue import BackendOption, PipelineStageDef
    from bristlenose.pipeline_view.host import HostFacts
    from bristlenose.pipeline_view.render import _stage_alternatives

    synth_stage = PipelineStageDef(
        id="apple_foundation_models",  # no _LLM_QUALITY entries for any option
        name="Apple Foundation Models",
        kind="apple_fm",
        notes="probe placeholder",
        viable_backends=[
            BackendOption(id="apple_fm", display="Apple FM"),
        ],
    )
    assert quality_for(synth_stage.id, "apple_fm") is None, (
        "premise broken: apple_fm IS rated in the catalogue"
    )
    settings = BristlenoseSettings(
        anthropic_api_key="sk-test",
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-20250514",
    )  # type: ignore[arg-type]
    host = HostFacts(
        os="Darwin", arch="arm64", os_version="26.0", memory_gb=32.0,
        keys_present={"anthropic": True, "openai": False, "azure": False, "google": False},
        installed_packages={}, ollama_running=False, ollama_models=[],
        network_reachable=True, apple_fm_status="unknown",
    )
    rows = _stage_alternatives(synth_stage, None, None, host, settings)
    by_provider = {r.provider_id: r for r in rows}
    # Apple FM stays unavailable on CLI (status "unknown"), but the key
    # invariant — quality=None is a valid field state — is what's pinned here.
    assert by_provider["apple_fm"].quality is None
    assert by_provider["apple_fm"].quality_source is None
    assert by_provider["apple_fm"].default is False


def test_every_rated_cell_targets_a_real_catalogue_option() -> None:
    """No quality rating for a (stage, provider, model) tuple the catalogue
    doesn't know — LLM at model grain, transcription at provider grain."""
    valid_llm: set[tuple[str, str, str]] = set()
    valid_transcription: set[tuple[str, str]] = set()
    for stage in STAGES:
        for backend in stage.viable_backends:
            if backend.models:
                for model in backend.models:
                    valid_llm.add((stage.id, backend.id, model.id))
            else:
                valid_transcription.add((stage.id, backend.id))
    for key in _LLM_QUALITY:
        assert key in valid_llm, f"quality entry {key} has no matching catalogue model"
    for key in _TRANSCRIPTION_QUALITY:
        assert key in valid_transcription, (
            f"quality entry {key} has no matching catalogue provider"
        )
