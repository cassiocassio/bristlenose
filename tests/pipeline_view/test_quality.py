"""v1.9 quality-rating invariants — behavioural, not snapshot.

The load-bearing test for this layer: every rated cell parses as a valid
`QualityRating`, every `note_key` is a translation key, every `source` is
in the closed enum, and the LLM stages share an identical option-id set
(mirrors v1.5's _LLM_BACKENDS drift catcher, one layer up).
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
_VALID_SOURCES = {"internal_bench", "published_bench", "community", "default"}


def test_quality_for_unknown_cell_returns_none() -> None:
    assert quality_for("not_a_stage", "claude") is None
    assert quality_for("quote_extraction", "not_a_backend") is None


def test_quality_for_known_cell_returns_rating() -> None:
    r = quality_for("quote_extraction", "claude")
    assert isinstance(r, QualityRating)
    assert r.rating == "excellent"
    assert r.source == "internal_bench"


def test_quality_for_transcription_cells_resolve() -> None:
    mlx = quality_for("transcription", "mlx")
    fw = quality_for("transcription", "faster-whisper")
    assert mlx is not None and mlx.rating == "excellent"
    assert fw is not None and fw.rating == "good"


@pytest.mark.parametrize("cell", list(_LLM_QUALITY.items()) + list(_TRANSCRIPTION_QUALITY.items()))
def test_every_rating_uses_closed_enums(
    cell: tuple[tuple[str, str], QualityRating],
) -> None:
    (stage_id, option_id), r = cell
    assert r.rating in _VALID_RATINGS, f"{stage_id}/{option_id} bad rating {r.rating!r}"
    assert r.source in _VALID_SOURCES, f"{stage_id}/{option_id} bad source {r.source!r}"


@pytest.mark.parametrize("cell", list(_LLM_QUALITY.items()) + list(_TRANSCRIPTION_QUALITY.items()))
def test_every_note_key_is_a_translation_key(
    cell: tuple[tuple[str, str], QualityRating],
) -> None:
    """`note_key` is either None or starts with `pipeline.quality.`."""
    (stage_id, option_id), r = cell
    if r.note_key is not None:
        assert r.note_key.startswith("pipeline.quality."), (
            f"{stage_id}/{option_id} note_key={r.note_key!r} is not a pipeline.quality.* key"
        )


def test_llm_quality_shares_identical_option_ids_across_stages() -> None:
    """Drift catcher — one layer up from v1.5's _LLM_BACKENDS invariant.

    If someone seeds quality for one LLM stage but forgets another, this
    fails loudly rather than letting the render layer silently default
    half a column to "untested".
    """
    by_stage: dict[str, set[str]] = {}
    for (stage_id, option_id) in _LLM_QUALITY:
        by_stage.setdefault(stage_id, set()).add(option_id)
    llm_stage_ids = {s.id for s in STAGES if s.kind == "llm"}
    assert set(by_stage) == llm_stage_ids, (
        f"_LLM_QUALITY stage coverage {set(by_stage)} != LLM stages {llm_stage_ids}"
    )
    sets = list(by_stage.values())
    first = sets[0]
    for s in sets[1:]:
        assert s == first, f"option-id drift across LLM stages: {sets}"


def test_apple_fm_cells_are_unrated() -> None:
    """Apple FM stays untested until a probe ships — render layer shows ⚠."""
    for stage in STAGES:
        if stage.kind != "llm":
            continue
        assert quality_for(stage.id, "apple_fm") is None, (
            f"{stage.id}/apple_fm should be unrated until the probe ships"
        )


def test_every_rated_cell_targets_a_real_catalogue_option() -> None:
    """No quality rating for a (stage, option) pair the catalogue doesn't know."""
    valid_pairs: set[tuple[str, str]] = set()
    for stage in STAGES:
        for opt in stage.viable_backends:
            valid_pairs.add((stage.id, opt.id))
    for key in list(_LLM_QUALITY.keys()) + list(_TRANSCRIPTION_QUALITY.keys()):
        assert key in valid_pairs, f"quality entry {key} has no matching catalogue option"
